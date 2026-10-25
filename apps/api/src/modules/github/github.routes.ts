import { Hono } from "hono";
import { eq, and } from "drizzle-orm";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import {
  getAppInstallationUrl,
  getInstallationAccessToken,
  syncInstallationRepositories,
  syncUserInstallations,
  syncPullRequestsForRepo,
  getIngestedRepoNames,
} from "./github-app.service";
import { verifySignature, handleEvent } from "./webhook.service";
import { db } from "../../db";
import { githubInstallations, connectedRepositories, indexJobs } from "../../db/schema";
import { env } from "../../configs/env";

const githubRouter = new Hono<{ Variables: AuthContextVariables }>();

/**
 * Shared webhook handler for GitHub webhook intake.
 */
export async function processWebhook(c: any) {
  const signature = c.req.header("x-hub-signature-256") || "";
  const eventName = c.req.header("x-github-event") || "pull_request";

  const rawBody = await c.req.text();

  // Verify HMAC signature in production
  const isValid = await verifySignature(rawBody, signature);
  if (!isValid && env.NODE_ENV === "production") {
    return c.json({ error: "Invalid webhook signature" }, 401);
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return c.json({ error: "Invalid JSON payload" }, 400);
  }

  const result = await handleEvent(eventName, payload);
  return c.json({ received: true, ...result });
}

import { SignJWT, jwtVerify } from "jose";
import { verifySessionToken } from "../auth/auth.service";

const jwtSecret = new TextEncoder().encode(env.JWT_SECRET);

/**
 * GET /install-url
 * Protected. Returns the GitHub App installation URL for the current user.
 * Encodes target team and project context into a cryptographically signed state token.
 */
githubRouter.get("/install-url", authMiddleware, async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.query("teamSlug");
  const projectSlug = c.req.query("projectSlug");
  const nonce = crypto.randomUUID();

  // Sign state token server-side without exposing raw userId in plaintext
  const state = await new SignJWT({
    sub: user.id,
    teamSlug: teamSlug || undefined,
    projectSlug: projectSlug || undefined,
    nonce,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("2h")
    .sign(jwtSecret);

  const installUrl = getAppInstallationUrl(state);
  return c.json({ installUrl });
});

/**
 * GET /callback
 * Public/Protected. GitHub App installation callback - syncs repos and redirects to GitAmi.
 */
githubRouter.get("/callback", async (c) => {
  const installationId = c.req.query("installation_id");
  const setupAction = c.req.query("setup_action");
  const state = c.req.query("state");
  const baseUrl = (env.FRONTEND_URL || "http://localhost:3000").replace(/\/+$/, "");

  if (!installationId) {
    return c.redirect(`${baseUrl}?error=missing_installation_id`);
  }

  let verifiedUserId: string | null = null;
  let teamSlug: string | undefined;
  let projectSlug: string | undefined;

  if (state) {
    try {
      const { payload } = await jwtVerify(state, jwtSecret);
      if (typeof payload.sub === "string") {
        verifiedUserId = payload.sub;
      }
      teamSlug = payload.teamSlug as string | undefined;
      projectSlug = payload.projectSlug as string | undefined;
    } catch (err) {
      console.warn("Invalid GitHub installation callback state token:", err);
    }
  }

  // If state was not present or expired, try bearer token from headers/query
  if (!verifiedUserId) {
    const authHeader = c.req.header("authorization") || c.req.header("Authorization");
    let token: string | null = null;
    if (authHeader?.startsWith("Bearer ")) token = authHeader.substring(7).trim();
    if (!token) token = c.req.query("token") || null;
    if (token) {
      verifiedUserId = await verifySessionToken(token);
    }
  }

  if (verifiedUserId) {
    try {
      await syncInstallationRepositories(installationId, verifiedUserId);
    } catch (err) {
      console.error("Error syncing installation repositories during callback:", err);
    }
  }

  // Redirect user cleanly back to their originating project repositories page
  if (teamSlug && projectSlug) {
    return c.redirect(
      `${baseUrl}/${teamSlug}/${projectSlug}/repositories?installed=true`
    );
  }

  return c.redirect(
    `${baseUrl}/github/callback?installation_id=${installationId}${
      state ? `&state=${encodeURIComponent(state)}` : ""
    }`
  );
});

/**
 * GET /installations
 * Protected. Lists the current user's GitHub App installations.
 */
githubRouter.get("/installations", authMiddleware, async (c) => {
  const user = c.get("user");

  let installations = await db
    .select()
    .from(githubInstallations)
    .where(eq(githubInstallations.userId, user.id));

  if (installations.length === 0) {
    await syncUserInstallations(user.id, user.githubId, user.username);
    installations = await db
      .select()
      .from(githubInstallations)
      .where(eq(githubInstallations.userId, user.id));
  }

  return c.json({ installations });
});

/**
 * GET /repositories
 * Protected. Lists active connected repositories for the current user.
 * Supports ?force=true or ?sync=true to immediately pull newly selected repos from GitHub.
 */
githubRouter.get("/repositories", authMiddleware, async (c) => {
  const user = c.get("user");
  const forceSync = c.req.query("force") === "true" || c.req.query("sync") === "true";

  let repositories = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.userId, user.id),
        eq(connectedRepositories.isActive, true),
      ),
    );

  if (forceSync || repositories.length === 0) {
    await syncUserInstallations(user.id, user.githubId, user.username);
    repositories = await db
      .select()
      .from(connectedRepositories)
      .where(
        and(
          eq(connectedRepositories.userId, user.id),
          eq(connectedRepositories.isActive, true),
        ),
      );
  }

  return c.json({ repositories });
});

/**
 * POST /repositories/sync
 * Protected. Forces an on-demand re-synchronization of all installations and repositories from GitHub.
 */
githubRouter.post("/repositories/sync", authMiddleware, async (c) => {
  const user = c.get("user");
  await syncUserInstallations(user.id, user.githubId, user.username);
  const repositories = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.userId, user.id),
        eq(connectedRepositories.isActive, true),
      ),
    );
  return c.json({ success: true, count: repositories.length, repositories });
});

/**
 * GET /repositories/:id
 * Protected. Gets single repository details.
 */
githubRouter.get("/repositories/:id", authMiddleware, async (c) => {
  const user = c.get("user");
  const repoId = c.req.param("id");

  if (!repoId) {
    return c.json({ error: "Missing repository id" }, 400);
  }

  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.id, repoId),
        eq(connectedRepositories.userId, user.id)
      )
    )
    .limit(1);

  if (!repo) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  return c.json({ repository: repo });
});

/**
 * PATCH /repositories/:id
 * Protected. Updates repository settings like defaultBranch or isActive status.
 */
githubRouter.patch("/repositories/:id", authMiddleware, async (c) => {
  const user = c.get("user");
  const repoId = c.req.param("id");
  const body = await c.req.json().catch(() => ({}));

  if (!repoId) {
    return c.json({ error: "Missing repository id" }, 400);
  }

  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.id, repoId),
        eq(connectedRepositories.userId, user.id)
      )
    )
    .limit(1);

  if (!repo) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  const setValues: Partial<typeof connectedRepositories.$inferInsert> = {};

  if (body.defaultBranch && typeof body.defaultBranch === "string") {
    setValues.defaultBranch = body.defaultBranch.trim();
  }
  if (typeof body.isActive === "boolean") {
    setValues.isActive = body.isActive;
  }
  if (body.name && typeof body.name === "string") {
    setValues.name = body.name.trim();
  }

  if (Object.keys(setValues).length === 0) {
    return c.json({ repository: repo });
  }

  const [updated] = await db
    .update(connectedRepositories)
    .set(setValues)
    .where(eq(connectedRepositories.id, repoId))
    .returning();

  return c.json({ repository: updated });
});

/**
 * POST /sync
 * Protected. Manually triggers syncing installations and repositories from GitHub App.
 */
githubRouter.post("/sync", authMiddleware, async (c) => {
  const user = c.get("user");
  const repos = await syncUserInstallations(user.id, user.githubId, user.username);
  return c.json({ success: true, repositories: repos });
});

/**
 * POST /repositories/:id/ingest
 * Protected. Ingests a connected repository into Neo4j and ChromaDB using in-memory streaming.
 */
githubRouter.post("/repositories/:id/ingest", authMiddleware, async (c) => {
  const user = c.get("user");
  const repoId = c.req.param("id");
  const body = (await c.req.json().catch(() => ({}))) as { branch?: string };
  const targetBranch = body?.branch;

  if (!repoId) {
    return c.json({ error: "Missing repository id" }, 400);
  }

  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.id, repoId),
        eq(connectedRepositories.userId, user.id),
        eq(connectedRepositories.isActive, true),
      ),
    )
    .limit(1);

  if (!repo) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  const [inst] = await db
    .select()
    .from(githubInstallations)
    .where(eq(githubInstallations.id, repo.installationId))
    .limit(1);

  let token: string | undefined;
  if (inst?.installationId) {
    try {
      token = await getInstallationAccessToken(inst.installationId);
    } catch (err) {
      console.warn("Could not obtain GitHub installation access token:", err);
    }
  }

  const branch = targetBranch || repo.defaultBranch || "main";
  let aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";

  // Use the fully-qualified "owner/repo" as the KB tenant key — the AI
  // service's multi-tenant isolation is keyed purely on this string, so a
  // bare repo name would let two different users' same-named repos collide
  // into the same knowledge base.
  const payload = {
    repo_id: repo.fullName,
    full_name: repo.fullName,
    access_token: token,
    branch,
    project_id: repo.projectId || "default",
    team_id: repo.userId,
  };

  try {
    let res: Response;
    try {
      res = await fetch(`${aiServiceUrl}/api/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch (netErr: any) {
      // If remote URL fails to connect and is not localhost, try localhost:8000 fallback
      if (aiServiceUrl !== "http://localhost:8000" && aiServiceUrl !== "http://127.0.0.1:8000") {
        console.warn(`Primary AI Service at ${aiServiceUrl} unreachable, falling back to http://localhost:8000`);
        aiServiceUrl = "http://localhost:8000";
        res = await fetch(`${aiServiceUrl}/api/ingest`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
      } else {
        throw netErr;
      }
    }

    // If remote returned 502/503 (e.g. cold start / sleeping instance), try localhost if available
    if ((res.status === 502 || res.status === 503) && aiServiceUrl !== "http://localhost:8000") {
      try {
        console.warn(`AI Service at ${aiServiceUrl} returned ${res.status}, attempting http://localhost:8000 fallback...`);
        const fallbackRes = await fetch(`http://localhost:8000/api/ingest`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        if (fallbackRes.ok) {
          res = fallbackRes;
        }
      } catch {
        // keep original response
      }
    }

    if (!res.ok) {
      const errData = (await res.json().catch(() => ({}))) as any;
      throw new Error(errData.detail || errData.error || `AI Service (${aiServiceUrl}) returned status ${res.status}`);
    }

    const data = await res.json();

    // Trigger background PR synchronization for this newly ingested repository
    syncPullRequestsForRepo(repo.fullName, repo.id).catch((err) => {
      console.warn(`PR sync error after ingestion for ${repo.fullName}:`, err);
    });

    return c.json({
      success: true,
      repository: repo,
      ingestResult: data,
    });
  } catch (err: any) {
    console.error("In-memory repository ingestion error:", err);
    return c.json({ error: err.message || "Failed to complete repository ingestion" }, 500);
  }
});


/**
 * DELETE /repositories/:id
 * Protected. Soft-disconnects a repository (sets isActive = false).
 */
githubRouter.delete("/repositories/:id", authMiddleware, async (c) => {
  const user = c.get("user");
  const repoId = c.req.param("id");

  if (!repoId) {
    return c.json({ error: "Missing repository id" }, 400);
  }

  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.id, repoId),
        eq(connectedRepositories.userId, user.id),
      ),
    )
    .limit(1);

  if (!repo) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  // 1. Delete associated index jobs
  await db.delete(indexJobs).where(eq(indexJobs.repositoryId, repoId));

  // 2. Disconnect repository in database
  await db
    .update(connectedRepositories)
    .set({ isActive: false, projectId: null })
    .where(eq(connectedRepositories.id, repoId));

  // 3. Purge repository knowledge base from AI Service (Neo4j graph & ChromaDB vectors)
  const aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";
  try {
    const purgeRes = await fetch(`${aiServiceUrl}/api/repos/${encodeURIComponent(repo.fullName)}`, {
      method: "DELETE",
    });
    if (!purgeRes.ok) {
      console.warn(`AI Service purge warning for ${repo.fullName}:`, await purgeRes.text().catch(() => ""));
    }
  } catch (purgeErr) {
    console.warn(`Could not reach AI Service to purge repository ${repo.fullName}:`, purgeErr);
  }

  return c.json({
    success: true,
    message: "Repository disconnected and purged from knowledge base successfully",
  });
});


/**
 * POST /ingest-local
 * Deprecated. Local repository ingestion has been removed in favor of GitHub App connections.
 */
githubRouter.post("/ingest-local", authMiddleware, async (c) => {
  return c.json(
    { error: "Local repository ingestion has been disabled. Repositories must be connected via GitHub App installations." },
    400
  );
});

/**
 * GET /indexed-repos
 * Protected. Lists Knowledge Base repo names scoped to repositories this
 * user actually owns in `connectedRepositories` — cross-referenced against
 * the AI service's raw (otherwise global, unauthenticated) index. This is
 * the only safe way to surface "indexed" status without leaking every
 * other user's ingested repos into this user's view.
 */
githubRouter.get("/indexed-repos", authMiddleware, async (c) => {
  const user = c.get("user");

  const repos = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.userId, user.id),
        eq(connectedRepositories.isActive, true),
      ),
    );

  const owned = new Set<string>();
  for (const r of repos) {
    owned.add(r.name);
    owned.add(r.fullName);
  }

  const aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";
  let globalRepos: string[] = [];
  let vectorCount = 0;

  try {
    const res = await fetch(`${aiServiceUrl}/api/repos`);
    if (res.ok) {
      const data = (await res.json()) as any;
      globalRepos = Array.isArray(data.repos) ? data.repos : [];
      vectorCount = data.vector_count || 0;
    }
  } catch (err) {
    console.warn("Could not reach AI service for indexed repos:", err);
  }

  const scoped = owned.size > 0
    ? globalRepos.filter((name) => {
        if (owned.has(name)) return true;
        const shortName = name.includes("/") ? name.split("/")[1] ?? name : name;
        if (owned.has(shortName)) return true;
        if (user?.username && name.toLowerCase().startsWith(`${user.username.toLowerCase()}/`)) return true;
        return false;
      })
    : globalRepos;

  return c.json({ repos: scoped, vector_count: vectorCount });

});

/**
 * Webhook route aliases
 */
githubRouter.post("/webhooks", processWebhook);
githubRouter.post("/", processWebhook);

export default githubRouter;
