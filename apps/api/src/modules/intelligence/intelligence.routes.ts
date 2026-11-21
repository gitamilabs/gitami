import { Hono, type Context } from "hono";
import { HTTPException } from "hono/http-exception";
import { eq } from "drizzle-orm";
import { db } from "../../db";
import { connectedRepositories, type User } from "../../db/schema";
import { env } from "../../configs/env";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import { getProjectForUser } from "../projects/projects.service";

export interface EnrichedTenancyPayload {
  repo_id: string;
  project_id: string;
  team_id: string;
  user_id: string;
  root_directory: string;
  [key: string]: any;
}

const intelligenceRouter = new Hono<{ Variables: AuthContextVariables }>();

const AI_SERVICE_URL = (
  process.env.AI_SERVICE_URL ||
  env.AI_SERVICE_URL ||
  "http://127.0.0.1:8000"
).replace("localhost", "127.0.0.1");

/**
 * Verifies repository tenancy and user project membership, rejecting unauthenticated
 * callers with 401 and unauthorized or unmapped repository records with 403 Forbidden.
 * Injects validated project_id, team_id, user_id, and root_directory into the payload.
 */
export async function verifyAndEnrichTenancy(
  body: Record<string, any>,
  user?: User | any,
): Promise<EnrichedTenancyPayload> {
  if (!user || !user.id) {
    throw new HTTPException(401, {
      res: Response.json(
        { error: "Unauthorized: User session required" },
        { status: 401 },
      ),
    });
  }

  const repoId = body?.repo_id;
  if (!repoId || typeof repoId !== "string" || !repoId.trim()) {
    throw new HTTPException(403, {
      res: Response.json(
        { error: "Forbidden: Missing required repository identifier (repo_id)" },
        { status: 403 },
      ),
    });
  }

  const [repo] = await db
    .select({
      projectId: connectedRepositories.projectId,
      userId: connectedRepositories.userId,
      rootDirectory: connectedRepositories.rootDirectory,
    })
    .from(connectedRepositories)
    .where(eq(connectedRepositories.fullName, repoId))
    .limit(1);

  if (!repo) {
    throw new HTTPException(403, {
      res: Response.json(
        {
          error: `Forbidden: Repository "${repoId}" not found or access denied`,
        },
        { status: 403 },
      ),
    });
  }

  if (!repo.projectId) {
    throw new HTTPException(403, {
      res: Response.json(
        {
          error: `Forbidden: Repository "${repoId}" is not mapped to any project`,
        },
        { status: 403 },
      ),
    });
  }

  if (body.project_id && body.project_id !== repo.projectId) {
    throw new HTTPException(403, {
      res: Response.json(
        {
          error: "Forbidden: project_id does not match repository's assigned project",
        },
        { status: 403 },
      ),
    });
  }

  const projectDetails = await getProjectForUser(user, repo.projectId);
  if (!projectDetails) {
    throw new HTTPException(403, {
      res: Response.json(
        { error: "Forbidden: User does not have access to this project" },
        { status: 403 },
      ),
    });
  }

  const enriched: EnrichedTenancyPayload = {
    ...body,
    repo_id: repoId,
    project_id: projectDetails.project.id,
    team_id: projectDetails.organization.id || repo.userId || user.id,
    user_id: user.id,
    root_directory: repo.rootDirectory || "",
  };

  return enriched;
}

/**
 * Standard forwarder for JSON POST requests with verified tenancy.
 */
async function forwardTenancyPost(
  c: Context<{ Variables: AuthContextVariables }>,
  path: string,
) {
  const body = await c.req.json().catch(() => ({}));
  const payload = await verifyAndEnrichTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
}

/**
 * Health check proxy (public, no auth required)
 */
intelligenceRouter.get("/health", async (c) => {
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/health`);
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ status: "error", error: err.message }, 502);
  }
});

/**
 * Require valid session authentication on all functional intelligence endpoints.
 */
intelligenceRouter.use("*", authMiddleware);

/**
 * List indexed repositories proxy
 */
intelligenceRouter.get("/repos", async (c) => {
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/repos`);
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ repos: [], error: err.message }, 502);
  }
});

/**
 * AI Service configuration proxy
 */
intelligenceRouter.get("/config", async (c) => {
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/config`);
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * List AI system prompts
 */
intelligenceRouter.get("/prompts", async (c) => {
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/prompts`);
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Get AI system prompt
 */
intelligenceRouter.get("/prompts/:key", async (c) => {
  const key = c.req.param("key");
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/prompts/${key}`);
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Update AI system prompt
 */
intelligenceRouter.put("/prompts/:key", async (c) => {
  const key = c.req.param("key");
  const body = await c.req.json().catch(() => ({}));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/prompts/${key}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Reset AI system prompt
 */
intelligenceRouter.post("/prompts/:key/reset", async (c) => {
  const key = c.req.param("key");
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/prompts/${key}/reset`, {
      method: "POST",
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Architectural Graph report proxy
 */
intelligenceRouter.get("/graph-report/:repoId{.+}", async (c) => {
  const repoId = c.req.param("repoId");
  const branch = c.req.query("branch") || "main";
  const tenancy = await verifyAndEnrichTenancy({ repo_id: repoId }, c.get("user"));
  try {
    const res = await fetch(
      `${AI_SERVICE_URL}/api/graph-report/${encodeURIComponent(repoId)}?branch=${encodeURIComponent(branch)}&project_id=${encodeURIComponent(tenancy.project_id)}&team_id=${encodeURIComponent(tenancy.team_id)}`,
    );
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * POST /chat
 * Standard non-streaming RAG chat response
 */
intelligenceRouter.post("/chat", (c) => forwardTenancyPost(c, "/api/chat"));

/**
 * POST /chat/stream
 * Server-Sent Events (SSE) streaming chat proxy
 */
intelligenceRouter.post("/chat/stream", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await verifyAndEnrichTenancy(body, c.get("user"));

  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok || !res.body) {
      return c.json(
        { error: `AI service returned ${res.status}` },
        res.status as any,
      );
    }

    return c.body(res.body, 200, {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    });
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Investigation Agent
 */
intelligenceRouter.post("/investigate", (c) =>
  forwardTenancyPost(c, "/api/investigate"),
);

/**
 * Curated Issue Agent
 */
intelligenceRouter.post("/issue/analyze", (c) =>
  forwardTenancyPost(c, "/api/issue/analyze"),
);

/**
 * Curated Doc Agent
 */
intelligenceRouter.post("/doc/generate", (c) =>
  forwardTenancyPost(c, "/api/doc/generate"),
);

/**
 * Curated Code Agent Stage 1: Plan
 */
intelligenceRouter.post("/code/plan", (c) =>
  forwardTenancyPost(c, "/api/code/plan"),
);

/**
 * Curated Code Agent Stage 2: Execute
 */
intelligenceRouter.post("/code/execute", (c) =>
  forwardTenancyPost(c, "/api/code/execute"),
);

export default intelligenceRouter;
