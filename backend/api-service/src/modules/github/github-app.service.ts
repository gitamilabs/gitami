import { eq } from "drizzle-orm";
import { env } from "../../configs/env";
import { db } from "../../db";
import {
  githubInstallations,
  connectedRepositories,
  type ConnectedRepository,
} from "../../db/schema";
import { SignJWT, importPKCS8 } from "jose";

import fs from "fs";
import path from "path";
import { createPrivateKey } from "crypto";

/**
 * Retrieves private key from raw PEM string or file path and converts it to PKCS#8 if needed.
 */
function getPrivateKey(): string {
  let raw = env.GITHUB_APP_PRIVATE_KEY || "";
  if (!raw) return "";

  if (!raw.includes("-----BEGIN")) {
    const resolvedPath = path.isAbsolute(raw)
      ? raw
      : path.resolve(process.cwd(), raw);
    if (fs.existsSync(resolvedPath)) {
      raw = fs.readFileSync(resolvedPath, "utf-8");
    }
  }

  // Normalize literal \n
  let cleanKey = raw.replace(/\\n/g, "\n").trim();

  // Ensure newlines after header and before footer if pasted as single string
  cleanKey = cleanKey
    .replace(/-----BEGIN ([A-Z ]+)-----/g, "-----BEGIN $1-----\n")
    .replace(/-----END ([A-Z ]+)-----/g, "\n-----END $1-----");

  try {
    const pk = createPrivateKey(cleanKey);
    return pk.export({ type: "pkcs8", format: "pem" }).toString();
  } catch (err) {
    console.error("Error parsing GITHUB_APP_PRIVATE_KEY with createPrivateKey:", err);
    return cleanKey;
  }
}

/**
 * Generates a GitHub App JWT.
 */
async function getAppJwt(): Promise<string> {
  const formattedKey = getPrivateKey();
  const privateKey = await importPKCS8(formattedKey, "RS256");
  return new SignJWT({
    iss: env.GITHUB_APP_ID,
  })
    .setProtectedHeader({ alg: "RS256" })
    .setIssuedAt(Math.floor(Date.now() / 1000) - 60)
    .setExpirationTime(Math.floor(Date.now() / 1000) + 9 * 60)
    .sign(privateKey);
}

/**
 * Creates an Installation Access Token for a given GitHub App Installation ID.
 */
export async function getInstallationAccessToken(
  installationId: string,
): Promise<string> {
  const appJwt = await getAppJwt();
  const tokenRes = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${appJwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Sentinel-API",
      },
    },
  );
  if (!tokenRes.ok) {
    throw new Error(`Failed to create installation access token: ${tokenRes.statusText}`);
  }
  const tokenData = (await tokenRes.json()) as any;
  return tokenData.token;
}


/**
 * Generates the URL for a user to install the Platform GitHub App.
 */
export function getAppInstallationUrl(state?: string): string {
  const params = new URLSearchParams();
  if (state) params.append("state", state);

  const queryString = params.toString();
  return `https://github.com/apps/${env.GITHUB_APP_SLUG}/installations/new${queryString ? `?${queryString}` : ""}`;
}

/**
 * Auto-discovers and syncs installations belonging to a user from GitHub App API.
 */
export async function syncUserInstallations(
  userId: string,
  userGithubId?: string,
  username?: string,
): Promise<ConnectedRepository[]> {
  try {
    const appJwt = await getAppJwt();
    const res = await fetch("https://api.github.com/app/installations", {
      headers: {
        Authorization: `Bearer ${appJwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Sentinel-API",
      },
    });

    if (!res.ok) {
      console.warn("Failed to fetch app installations from GitHub:", res.statusText);
      return [];
    }

    const installations = (await res.json()) as any[];
    if (!Array.isArray(installations)) return [];

    const allSynced: ConnectedRepository[] = [];

    for (const inst of installations) {
      const account = inst.account;
      const matchesGithubId = userGithubId && String(account?.id) === String(userGithubId);
      const matchesUsername = username && account?.login?.toLowerCase() === username.toLowerCase();

      // If user matched or there is only 1 user installation
      if (matchesGithubId || matchesUsername || installations.length === 1) {
        const repos = await syncInstallationRepositories(String(inst.id), userId);
        allSynced.push(...repos);
      }
    }

    return allSynced;
  } catch (err) {
    console.error("Auto-sync user installations error:", err);
    return [];
  }
}

/**
 * Fetches repositories from a GitHub App installation and syncs them to the database.
 * - Upserts the installation record.
 * - Upserts each accessible repository.
 */
export async function syncInstallationRepositories(
  installationId: string,
  userId: string,
): Promise<ConnectedRepository[]> {
  const appJwt = await getAppJwt();

  // Fetch installation metadata
  const instRes = await fetch(
    `https://api.github.com/app/installations/${installationId}`,
    {
      headers: {
        Authorization: `Bearer ${appJwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Sentinel-API",
      },
    }
  );
  if (!instRes.ok) {
    throw new Error(`Failed to fetch installation metadata: ${instRes.statusText}`);
  }
  const installationData = (await instRes.json()) as any;
  const account = installationData.account as
    | { login: string; id: number }
    | null;

  // Upsert installation record
  const [savedInst] = await db
    .insert(githubInstallations)
    .values({
      userId,
      installationId: String(installationData.id),
      accountLogin: account?.login ?? "unknown",
      accountId: account ? String(account.id) : "0",
      targetType: installationData.target_type ?? "User",
    })
    .onConflictDoUpdate({
      target: githubInstallations.installationId,
      set: {
        accountLogin: account?.login ?? "unknown",
        accountId: account ? String(account.id) : "0",
        targetType: installationData.target_type ?? "User",
      },
    })
    .returning();

  // Create Installation Access Token
  const tokenRes = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${appJwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Sentinel-API",
      },
    }
  );
  if (!tokenRes.ok) {
    throw new Error(`Failed to create installation access token: ${tokenRes.statusText}`);
  }
  const tokenData = (await tokenRes.json()) as any;
  const installationToken = tokenData.token;

  // Fetch accessible repositories
  const reposRes = await fetch(
    `https://api.github.com/installation/repositories`,
    {
      headers: {
        Authorization: `Bearer ${installationToken}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Sentinel-API",
      },
    }
  );
  if (!reposRes.ok) {
    throw new Error(`Failed to fetch accessible repositories: ${reposRes.statusText}`);
  }
  const reposData = (await reposRes.json()) as any;

  const syncedRepos: ConnectedRepository[] = [];

  for (const repo of reposData.repositories) {
    const [savedRepo] = await db
      .insert(connectedRepositories)
      .values({
        installationId: savedInst!.id,
        userId,
        githubRepoId: String(repo.id),
        name: repo.name,
        fullName: repo.full_name,
        isPrivate: repo.private,
        htmlUrl: repo.html_url,
        defaultBranch: repo.default_branch ?? "main",
        isActive: true,
      })
      .onConflictDoUpdate({
        target: connectedRepositories.githubRepoId,
        set: {
          name: repo.name,
          fullName: repo.full_name,
          isPrivate: repo.private,
          htmlUrl: repo.html_url,
          defaultBranch: repo.default_branch ?? "main",
          isActive: true,
        },
      })
      .returning();

    syncedRepos.push(savedRepo!);
  }

  return syncedRepos;
}
