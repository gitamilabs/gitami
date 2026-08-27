import { Hono } from "hono";
import {
  listPullRequests,
  getPullRequestDetails,
  evaluatePRWithAIService,
  fixSelectedPRIssues,
} from "./pr.service";

const prRouter = new Hono();

/**
 * GET /api/prs
 * Public/Protected. Lists PRs in the system.
 */
const getPrListHandler = async (c: any) => {
  const repoFullName = c.req.query("repoFullName");
  const prs = await listPullRequests(repoFullName);
  return c.json({ pullRequests: prs });
};

prRouter.get("/", getPrListHandler);
prRouter.get("", getPrListHandler);

/**
 * GET /api/prs/:id
 * Fetch details of a single PR with review and checklist.
 */
prRouter.get("/:id", async (c) => {
  const prId = c.req.param("id");
  const pr = await getPullRequestDetails(prId);
  if (!pr) return c.json({ error: "PR not found" }, 404);
  return c.json({ pullRequest: pr });
});

/**
 * POST /api/prs/:id/review
 * Manually trigger/re-run AI PR evaluation.
 */
prRouter.post("/:id/review", async (c) => {
  const prId = c.req.param("id");
  try {
    const result = await evaluatePRWithAIService(prId);
    return c.json({ success: true, pullRequest: result });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to evaluate PR" }, 500);
  }
});

/**
 * POST /api/prs/:id/fix
 * Trigger AI Agent to generate fix patch & raise PR on GitHub for selected issues.
 */
prRouter.post("/:id/fix", async (c) => {
  const prId = c.req.param("id");
  try {
    const body = await c.req.json();
    const issueIds: string[] = body.issueIds || [];
    if (!issueIds || issueIds.length === 0) {
      return c.json({ error: "No issues selected for fixing" }, 400);
    }

    const result = await fixSelectedPRIssues(prId, issueIds);
    return c.json({ success: true, ...result });
  } catch (err: any) {
    const isPermissionErr =
      err.message?.includes("Permission Denied") ||
      err.message?.includes("GITHUB_TOKEN") ||
      err.message?.includes("permission");
    return c.json({ error: err.message || "Failed to launch AI fix" }, isPermissionErr ? 403 : 400);
  }
});

/**
 * POST /api/prs/ingest-link
 * Trigger repository ingestion in AI Service using GitHub Repo URL / repoFullName.
 */
prRouter.post("/ingest-link", async (c) => {
  try {
    const body = await c.req.json();
    const { repoUrl, repoFullName } = body;
    const targetRepo = repoFullName || repoUrl;
    if (!targetRepo) {
      return c.json({ error: "Missing repoUrl or repoFullName" }, 400);
    }

    const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
    const res = await fetch(`${AI_SERVICE_URL}/api/ingest-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_url: repoUrl || `https://github.com/${repoFullName}`,
        repo_id: repoFullName || repoUrl.replace("https://github.com/", ""),
        branch: body.branch || "main",
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      return c.json({ error: `AI Ingest failed: ${err}` }, 500);
    }

    const data = await res.json();
    return c.json({ success: true, data });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to trigger ingestion" }, 500);
  }
});

export default prRouter;
