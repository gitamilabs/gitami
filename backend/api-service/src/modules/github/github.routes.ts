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
} from "./github-app.service";
import { verifySignature, handleEvent } from "./webhook.service";
import { db } from "../../db";
import { githubInstallations, connectedRepositories } from "../../db/schema";
import { env } from "../../configs/env";

const githubRouter = new Hono<{ Variables: AuthContextVariables }>();

/**
 * GET /install-url
 * Protected. Returns the GitHub App installation URL for the current user.
 */
githubRouter.get("/install-url", authMiddleware, (c) => {
  const user = c.get("user");
  const installUrl = getAppInstallationUrl(user.id);
  return c.json({ installUrl });
});

/**
 * GET /callback
 * Protected. GitHub App installation callback - syncs repos.
 */
githubRouter.get("/callback", authMiddleware, async (c) => {
  const user = c.get("user");
  const installationId = c.req.query("installation_id");
  const setupAction = c.req.query("setup_action");

  if (!installationId) {
    return c.json({ error: "Missing installation_id" }, 400);
  }

  try {
    const repos = await syncInstallationRepositories(installationId, user.id);

    return c.json({
      success: true,
      setupAction,
      installationId,
      connectedRepositories: repos,
    });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Failed to sync installation";
    console.error("Error processing GitHub App installation callback:", err);
    return c.json({ error: message }, 500);
  }
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
 */
githubRouter.get("/repositories", authMiddleware, async (c) => {
  const user = c.get("user");

  let repositories = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.userId, user.id),
        eq(connectedRepositories.isActive, true),
      ),
    );

  if (repositories.length === 0) {
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

  const payload = {
    repo_id: repo.name,
    full_name: repo.fullName,
    access_token: token,
    branch,
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

  await db
    .update(connectedRepositories)
    .set({ isActive: false })
    .where(eq(connectedRepositories.id, repoId));

  return c.json({
    success: true,
    message: "Repository disconnected successfully",
  });
});


/**
 * POST /webhooks
 * Public. Ingestion endpoint for GitHub App webhooks.
 */
githubRouter.post("/webhooks", async (c) => {
  const signature = c.req.header("x-hub-signature-256") || "";
  const eventName = c.req.header("x-github-event") || "";

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
});

export default githubRouter;
