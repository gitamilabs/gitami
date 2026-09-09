import { SignJWT, jwtVerify } from "jose";
import { eq } from "drizzle-orm";
import { env } from "../../configs/env";
import { db } from "../../db";
import { users, type User } from "../../db/schema";

const jwtSecret = new TextEncoder().encode(env.JWT_SECRET);

/**
 * Builds the GitHub OAuth authorization URL.
 */
export function getOAuthAuthorizeUrl(state?: string): string {
  const params = new URLSearchParams({
    client_id: env.GITHUB_CLIENT_ID,
    redirect_uri: env.GITHUB_OAUTH_REDIRECT_URI,
    scope: "read:user user:email",
    ...(state && { state }),
  });

  return `https://github.com/login/oauth/authorize?${params.toString()}`;
}

/**
 * Exchanges an OAuth authorization code for a GitHub access token.
 */
export async function exchangeCodeForToken(code: string): Promise<string> {
  const response = await fetch(
    "https://github.com/login/oauth/access_token",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        client_id: env.GITHUB_CLIENT_ID,
        client_secret: env.GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: env.GITHUB_OAUTH_REDIRECT_URI,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to exchange GitHub code: ${response.statusText}`,
    );
  }

  const data = (await response.json()) as {
    access_token?: string;
    error?: string;
    error_description?: string;
  };

  if (data.error || !data.access_token) {
    throw new Error(
      data.error_description ||
        data.error ||
        "No access token returned from GitHub",
    );
  }

  return data.access_token;
}

/**
 * Fetches the authenticated user's profile and primary email from GitHub.
 */
export async function fetchGitHubUserProfile(accessToken: string): Promise<{
  githubId: string;
  username: string;
  avatarUrl: string;
  email?: string;
}> {
  const headers = {
    Authorization: `Bearer ${accessToken}`,
    "User-Agent": "Sentinel-API-Service",
    Accept: "application/vnd.github.v3+json",
  };

  const userRes = await fetch("https://api.github.com/user", { headers });

  if (!userRes.ok) {
    throw new Error(
      `Failed to fetch user profile from GitHub: ${userRes.statusText}`,
    );
  }

  const githubUser = (await userRes.json()) as {
    id: number;
    login: string;
    avatar_url: string;
    email?: string;
  };

  let email = githubUser.email;

  // If public email is not set, try the /user/emails endpoint
  if (!email) {
    try {
      const emailsRes = await fetch("https://api.github.com/user/emails", {
        headers,
      });

      if (emailsRes.ok) {
        const emails = (await emailsRes.json()) as Array<{
          email: string;
          primary: boolean;
        }>;
        const primary = emails.find((e) => e.primary) || emails[0];
        if (primary) email = primary.email;
      }
    } catch {
      // Non-fatal — proceed without email
    }
  }

  return {
    githubId: String(githubUser.id),
    username: githubUser.login,
    avatarUrl: githubUser.avatar_url,
    email: email || undefined,
  };
}

/**
 * Upserts a user record in the database.
 * Returns the existing (updated) or newly created user.
 */
export async function upsertUser(profile: {
  githubId: string;
  username: string;
  avatarUrl: string;
  email?: string;
}): Promise<User> {
  const [existing] = await db
    .select()
    .from(users)
    .where(eq(users.githubId, profile.githubId))
    .limit(1);

  if (existing) {
    const [updated] = await db
      .update(users)
      .set({
        username: profile.username,
        avatarUrl: profile.avatarUrl,
        email: profile.email ?? existing.email,
      })
      .where(eq(users.id, existing.id))
      .returning();

    return updated!;
  }

  const [created] = await db
    .insert(users)
    .values({
      githubId: profile.githubId,
      username: profile.username,
      avatarUrl: profile.avatarUrl,
      email: profile.email,
    })
    .returning();

  return created!;
}

/**
 * Handles the full OAuth callback flow:
 * exchange code → fetch profile → upsert user → sign JWT.
 */
export async function handleCallback(
  code: string,
): Promise<{ user: User; token: string }> {
  const accessToken = await exchangeCodeForToken(code);
  const profile = await fetchGitHubUserProfile(accessToken);
  const user = await upsertUser(profile);
  const token = await signSessionToken(user.id);

  return { user, token };
}

/**
 * Signs a JWT session token for a given user ID.
 */
export async function signSessionToken(userId: string): Promise<string> {
  return new SignJWT({ sub: userId })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(jwtSecret);
}

/**
 * Verifies a JWT session token and extracts the user ID.
 * Returns null if the token is invalid or expired.
 */
export async function verifySessionToken(
  token: string,
): Promise<string | null> {
  try {
    const { payload } = await jwtVerify(token, jwtSecret);
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

/**
 * Fetches a user by their primary key.
 */
export async function getUserById(id: string): Promise<User | undefined> {
  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, id))
    .limit(1);

  return user;
}

/**
 * Fetches a user by their GitHub ID.
 */
export async function getUserByGithubId(
  githubId: string,
): Promise<User | undefined> {
  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.githubId, githubId))
    .limit(1);

  return user;
}
