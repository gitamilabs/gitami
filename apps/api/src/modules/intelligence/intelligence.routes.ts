import { Hono } from "hono";
import { stream } from "hono/streaming";
import { eq } from "drizzle-orm";
import { db } from "../../db";
import { connectedRepositories } from "../../db/schema";
import { env } from "../../configs/env";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";

const intelligenceRouter = new Hono<{ Variables: AuthContextVariables }>();

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";

async function enrichPayloadWithTenancy(body: any, user?: any): Promise<any> {
  const enriched = { ...body };
  if (!enriched.project_id && enriched.repo_id) {
    try {
      const [repo] = await db
        .select({ projectId: connectedRepositories.projectId, userId: connectedRepositories.userId })
        .from(connectedRepositories)
        .where(eq(connectedRepositories.fullName, enriched.repo_id))
        .limit(1);
      if (repo) {
        enriched.project_id = repo.projectId || "default";
        if (!enriched.team_id && repo.userId) {
          enriched.team_id = repo.userId;
        }
      }
    } catch {
      // Graceful fallback to default if DB lookup is unavailable
    }
  }
  if (!enriched.project_id) {
    enriched.project_id = "default";
  }
  if (!enriched.team_id && user?.id) {
    enriched.team_id = user.id;
  }
  return enriched;
}

/**
 * Health check proxy
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
intelligenceRouter.get("/graph-report/:repoId", async (c) => {
  const repoId = c.req.param("repoId");
  const branch = c.req.query("branch") || "main";
  try {
    const res = await fetch(
      `${AI_SERVICE_URL}/api/graph-report/${encodeURIComponent(repoId)}?branch=${encodeURIComponent(branch)}`
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
intelligenceRouter.post("/chat", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * POST /chat/stream
 * Server-Sent Events (SSE) streaming chat proxy
 */
intelligenceRouter.post("/chat/stream", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));

  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok || !res.body) {
      return c.json({ error: `AI service returned ${res.status}` }, res.status as any);
    }

    c.header("Content-Type", "text/event-stream");
    c.header("Cache-Control", "no-cache");
    c.header("Connection", "keep-alive");

    return stream(c, async (s) => {
      const reader = res.body!.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          await s.write(value);
        }
      } finally {
        reader.releaseLock();
      }
    });
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Investigation Agent
 */
intelligenceRouter.post("/investigate", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Issue Agent
 */
intelligenceRouter.post("/issue/analyze", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/issue/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Doc Agent
 */
intelligenceRouter.post("/doc/generate", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/doc/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Code Agent Stage 1: Plan
 */
intelligenceRouter.post("/code/plan", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/code/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

/**
 * Curated Code Agent Stage 2: Execute
 */
intelligenceRouter.post("/code/execute", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const payload = await enrichPayloadWithTenancy(body, c.get("user"));
  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/code/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return c.json(data, res.status as any);
  } catch (err: any) {
    return c.json({ error: err.message }, 502);
  }
});

export default intelligenceRouter;
