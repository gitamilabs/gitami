import { eq, and } from "drizzle-orm";
import { env } from "../../configs/env";
import { db } from "../../db";
import {
  githubInstallations,
  connectedRepositories,
  pullRequests,
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
 * Dynamically resolves a GitHub App Installation Access Token for a given owner/repo.
 * First checks DB records, then falls back to GitHub App API lookup.
 */
export async function getInstallationTokenForRepo(
  owner: string,
  repo: string,
): Promise<string | null> {
  const fullName = `${owner}/${repo}`;

  // 1. Try DB lookup
  try {
    const [repoRecord] = await db
      .select()
      .from(connectedRepositories)
      .where(eq(connectedRepositories.fullName, fullName))
      .limit(1);

    if (repoRecord) {
      const [instRecord] = await db
        .select()
        .from(githubInstallations)
        .where(eq(githubInstallations.id, repoRecord.installationId))
        .limit(1);

      if (instRecord && instRecord.installationId) {
        return await getInstallationAccessToken(instRecord.installationId);
      }
    }
  } catch (e) {
    console.warn("DB lookup notice in getInstallationTokenForRepo:", e);
  }

  // 2. Query GitHub App API directly using App JWT
  try {
    const appJwt = await getAppJwt();
    const instRes = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/installation`,
      {
        headers: {
          Authorization: `Bearer ${appJwt}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "Sentinel-API",
        },
      },
    );

    if (instRes.ok) {
      const instData = (await instRes.json()) as any;
      if (instData && instData.id) {
        return await getInstallationAccessToken(String(instData.id));
      }
    }
  } catch (err: any) {
    console.warn(
      `Could not resolve GitHub App installation for ${fullName}:`,
      err.message || err,
    );
  }

  return null;
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

    // Immediately trigger background pull request synchronization for this repo
    syncPullRequestsForRepo(repo.full_name, savedRepo!.id).catch((err) => {
      console.warn(`Initial PR sync error for ${repo.full_name}:`, err);
    });
  }

  return syncedRepos;
}

/**
 * Fetches pull requests from GitHub REST API for a repository and syncs them to database.
 */
export async function syncPullRequestsForRepo(
  repoFullName: string,
  repositoryId?: string,
): Promise<any[]> {
  if (!repoFullName) return [];

  let targetFullName = repoFullName.trim();
  let targetRepoId = repositoryId;

  // 1. If repoFullName is just "repo" without owner (no "/"), look up in connectedRepositories
  if (!targetFullName.includes("/")) {
    const [found] = await db
      .select()
      .from(connectedRepositories)
      .where(eq(connectedRepositories.name, targetFullName))
      .limit(1);

    if (found) {
      targetFullName = found.fullName;
      targetRepoId = targetRepoId || found.id;
    } else {
      // Look up in githubInstallations for account login
      const [inst] = await db.select().from(githubInstallations).limit(1);
      if (inst && inst.accountLogin) {
        targetFullName = `${inst.accountLogin}/${targetFullName}`;
      }
    }
  }

  const [owner, repo] = (targetFullName || "").split("/");
  if (!owner || !repo) {
    console.warn(`Could not resolve owner/repo for PR sync: '${repoFullName}'`);
    return [];
  }

  // 2. Resolve token: GitHub App Installation Token -> PAT / env token
  let token: string | null = null;
  try {
    token = await getInstallationTokenForRepo(owner, repo);
  } catch (err) {
    console.warn(`Could not get installation token for ${targetFullName}:`, err);
  }

  if (!token) {
    token = (process.env.GITHUB_TOKEN || process.env.GITHUB_PAT || env.GITHUB_TOKEN || "").trim() || null;
  }

  // 3. Fetch pull requests from GitHub API
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "User-Agent": "Sentinel-API",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const res = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/pulls?state=all&per_page=30&sort=updated&direction=desc`,
      { headers },
    );

    if (!res.ok) {
      console.warn(`GitHub PR fetch returned status ${res.status} for ${targetFullName}`);
      return [];
    }

    const prs = (await res.json()) as any[];
    if (!Array.isArray(prs)) return [];

    const syncedPRs = [];

    for (const pr of prs) {
      const headBranch = pr.head?.ref || "unknown";
      const baseBranch = pr.base?.ref || "main";
      const title = pr.title || `PR #${pr.number}`;
      const isAiFix = headBranch.startsWith("ai-fix/") || title.toLowerCase().startsWith("[ai fix]");

      // Check if PR already exists in DB (match by either targetFullName or repoFullName)
      const [existing] = await db
        .select()
        .from(pullRequests)
        .where(
          and(
            eq(pullRequests.prNumber, pr.number),
            eq(pullRequests.repoFullName, targetFullName),
          ),
        )
        .limit(1);

      let savedPR;
      if (existing) {
        // Update PR fields, keep existing review status
        [savedPR] = await db
          .update(pullRequests)
          .set({
            title,
            body: pr.body || "",
            state: pr.state || "open",
            baseBranch,
            headBranch,
            baseSha: pr.base?.sha || "",
            headSha: pr.head?.sha || "",
            authorLogin: pr.user?.login || "user",
            htmlUrl: pr.html_url || `https://github.com/${targetFullName}/pull/${pr.number}`,
          })
          .where(eq(pullRequests.id, existing.id))
          .returning();
      } else {
        [savedPR] = await db
          .insert(pullRequests)
          .values({
            repositoryId: targetRepoId || null,
            repoFullName: targetFullName,
            prNumber: pr.number,
            title,
            body: pr.body || "",
            state: pr.state || "open",
            status: isAiFix ? "skipped_ai_fix" : "pending",
            baseBranch,
            headBranch,
            baseSha: pr.base?.sha || "",
            headSha: pr.head?.sha || "",
            authorLogin: pr.user?.login || "user",
            htmlUrl: pr.html_url || `https://github.com/${targetFullName}/pull/${pr.number}`,
          })
          .returning();
      }

      if (savedPR) syncedPRs.push(savedPR);
    }

    console.log(`✅ Synced ${syncedPRs.length} pull requests from GitHub for ${targetFullName}`);
    return syncedPRs;
  } catch (err) {
    console.error(`Error syncing PRs for ${targetFullName}:`, err);
    return [];
  }
}

/**
 * Syncs pull requests for all connected repositories for a user or system-wide.
 */
export async function syncAllConnectedPullRequests(userId?: string): Promise<void> {
  try {
    let repos = userId
      ? await db
          .select()
          .from(connectedRepositories)
          .where(
            and(
              eq(connectedRepositories.userId, userId),
              eq(connectedRepositories.isActive, true),
            ),
          )
      : await db
          .select()
          .from(connectedRepositories)
          .where(eq(connectedRepositories.isActive, true));

    if (repos.length === 0 && userId) {
      repos = await db
        .select()
        .from(connectedRepositories)
        .where(eq(connectedRepositories.isActive, true));
    }

    // Parallelize PR syncing across connected repositories in batches of 6
    const batchSize = 6;
    for (let i = 0; i < repos.length; i += batchSize) {
      const batch = repos.slice(i, i + batchSize);
      await Promise.allSettled(
        batch.map((repo) => syncPullRequestsForRepo(repo.fullName, repo.id)),
      );
    }
  } catch (err) {
    console.error("Error in syncAllConnectedPullRequests:", err);
  }
}

