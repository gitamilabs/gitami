import { Hono } from "hono";
import { eq, and, desc } from "drizzle-orm";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import {
  getProjectForUser,
  getProjectDetails,
  updateProject,
  deleteProject,
  attachRepositoryToProject,
  detachRepositoryFromProject,
  startProjectBuild,
  formatBuildWithStages,
} from "./projects.service";
import { db } from "../../db";
import { indexJobs, connectedRepositories } from "../../db/schema";
import { env } from "../../configs/env";
import { listPullRequestsForProject } from "../pr/pr.service";

const projectsRouter = new Hono<{ Variables: AuthContextVariables }>();

projectsRouter.use("*", authMiddleware);

/**
 * GET /:projectIdOrSlug
 * Returns project details including its connected repositories and recent builds.
 */
projectsRouter.get("/:projectIdOrSlug", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");

  const details = await getProjectDetails(user, projectIdOrSlug);
  if (!details) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  return c.json(details);
});

/**
 * PATCH /:projectIdOrSlug
 * Updates project name, description, and/or slug.
 */
projectsRouter.patch("/:projectIdOrSlug", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const body = await c.req.json().catch(() => ({}));

  try {
    const project = await updateProject(user, projectIdOrSlug, {
      name: body.name,
      description: body.description,
      slug: body.slug,
    });
    return c.json({ project });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to update project" }, 400);
  }
});

/**
 * DELETE /:projectIdOrSlug
 * Deletes project, disassociating repositories and deleting index jobs.
 */
projectsRouter.delete("/:projectIdOrSlug", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");

  try {
    await deleteProject(user, projectIdOrSlug);
    return c.json({ success: true, message: "Project deleted successfully" });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to delete project" }, 400);
  }
});

/**
 * POST /:projectIdOrSlug/repositories
 * Attaches an existing connected repository to this project.
 */
projectsRouter.post("/:projectIdOrSlug/repositories", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const body = await c.req.json().catch(() => ({}));
  const repositoryId = body.repositoryId;

  if (!repositoryId) {
    return c.json({ error: "repositoryId is required" }, 400);
  }

  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  const attached = await attachRepositoryToProject(
    result.project.id,
    repositoryId,
    user.id
  );

  if (!attached) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  return c.json({ success: true, repository: attached });
});

/**
 * DELETE /:projectIdOrSlug/repositories/:repoId
 * Detaches a repository from this project.
 */
projectsRouter.delete("/:projectIdOrSlug/repositories/:repoId", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const repoId = c.req.param("repoId");

  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  const success = await detachRepositoryFromProject(
    result.project.id,
    repoId,
    user.id
  );

  if (!success) {
    return c.json({ error: "Repository not found or access denied" }, 404);
  }

  return c.json({ success: true, message: "Repository detached from project" });
});

/**
 * GET /:projectIdOrSlug/builds
 * Returns all builds for this project.
 */
projectsRouter.get("/:projectIdOrSlug/builds", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");

  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  const builds = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.projectId, result.project.id));

  return c.json({ builds: builds.map(formatBuildWithStages) });
});

/**
 * POST /:projectIdOrSlug/builds
 * Starts a build for a repository in this project.
 * Returns immediately (non-blocking) with the initial build status.
 */
projectsRouter.post("/:projectIdOrSlug/builds", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const body = await c.req.json().catch(() => ({}));
  const repositoryId = body.repositoryId;
  const branch = body.branch;

  if (!repositoryId) {
    return c.json({ error: "repositoryId is required" }, 400);
  }

  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  try {
    const build = await startProjectBuild(
      user,
      result.project,
      repositoryId,
      branch
    );
    return c.json({ success: true, build }, 202);
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to start build" }, 400);
  }
});

/**
 * GET /:projectIdOrSlug/graph
 * Returns actual Neo4j knowledge graph nodes and edges for the project's repository.
 * Returns truthful state when no build has completed, when a build is running, or when it failed.
 */
projectsRouter.get("/:projectIdOrSlug/graph", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const repoIdParam = c.req.query("repoId");
  const branchParam = c.req.query("branch");
  const maxNodes = c.req.query("maxNodes") || "400";

  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    return c.json({ error: "Project not found or access denied" }, 404);
  }

  // Find target connected repository
  let targetRepo;
  if (repoIdParam) {
    const [found] = await db
      .select()
      .from(connectedRepositories)
      .where(
        and(
          eq(connectedRepositories.id, repoIdParam),
          eq(connectedRepositories.projectId, result.project.id)
        )
      )
      .limit(1);
    targetRepo = found;
  } else {
    const [found] = await db
      .select()
      .from(connectedRepositories)
      .where(
        and(
          eq(connectedRepositories.projectId, result.project.id),
          eq(connectedRepositories.isActive, true)
        )
      )
      .limit(1);
    targetRepo = found;
  }

  if (!targetRepo) {
    return c.json({
      status: "NO_REPOSITORY",
      message: "No connected repositories in this project yet.",
      nodes: [],
      edges: [],
    });
  }

  const branch = branchParam || targetRepo.defaultBranch || "main";

  // Check latest build for this repository
  const [latestBuild] = await db
    .select()
    .from(indexJobs)
    .where(
      and(
        eq(indexJobs.projectId, result.project.id),
        eq(indexJobs.repositoryId, targetRepo.fullName)
      )
    )
    .orderBy(desc(indexJobs.createdAt))
    .limit(1);

  if (!latestBuild) {
    return c.json({
      status: "NOT_INDEXED",
      repository: targetRepo,
      message: "Your project isn't indexed yet.",
      nodes: [],
      edges: [],
    });
  }

  if (latestBuild.status === "RUNNING" || latestBuild.status === "QUEUED") {
    return c.json({
      status: "BUILDING",
      build: formatBuildWithStages(latestBuild),
      repository: targetRepo,
      message: "Your project intelligence is being prepared.",
      nodes: [],
      edges: [],
    });
  }

  if (latestBuild.status === "FAILED") {
    return c.json({
      status: "FAILED",
      build: formatBuildWithStages(latestBuild),
      repository: targetRepo,
      message: `Intelligence couldn't be built: ${latestBuild.error || "Build failed"}`,
      nodes: [],
      edges: [],
    });
  }

  // Fetch actual graph data from AI service
  let aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";
  const repoKey = encodeURIComponent(targetRepo.fullName);

  try {
    const effectiveProjectId = targetRepo.projectId || result.project.id;
    const res = await fetch(
      `${aiServiceUrl}/api/graph/${repoKey}?branch=${encodeURIComponent(branch)}&max_nodes=${maxNodes}&project_id=${encodeURIComponent(effectiveProjectId)}`
    );

    if (!res.ok) {
      // If AI service has not indexed or returned 404/500
      return c.json({
        status: "NOT_INDEXED",
        repository: targetRepo,
        build: formatBuildWithStages(latestBuild),
        message: "No graph records found in Neo4j for this repository.",
        nodes: [],
        edges: [],
      });
    }

    const data = (await res.json()) as any;
    return c.json({
      status: "READY",
      repository: targetRepo,
      build: formatBuildWithStages(latestBuild),
      nodes: data.nodes || [],
      edges: data.edges || [],
      communities: data.communities || [],
      stats: data.stats || {
        nodeCount: data.total_nodes || (data.nodes || []).length,
        edgeCount: data.total_edges || (data.edges || []).length,
        communityCount: (data.communities || []).length,
      },
      totalNodes: data.total_nodes || (data.nodes || []).length,
      totalEdges: data.total_edges || (data.edges || []).length,
    });
  } catch (err: any) {
    console.warn("Could not reach AI Service graph endpoint:", err);
    return c.json({
      status: "NOT_INDEXED",
      repository: targetRepo,
      build: formatBuildWithStages(latestBuild),
      message: "Could not retrieve knowledge graph from intelligence service.",
      nodes: [],
      edges: [],
    });
  }
});

/**
 * GET /:projectIdOrSlug/prs
 * Lists PRs strictly scoped to repositories attached to this project.
 */
projectsRouter.get("/:projectIdOrSlug/prs", async (c) => {
  const user = c.get("user");
  const projectIdOrSlug = c.req.param("projectIdOrSlug");
  const repoFullName = c.req.query("repoFullName");

  const prs = await listPullRequestsForProject(user, projectIdOrSlug, repoFullName);
  return c.json({ pullRequests: prs });
});

export default projectsRouter;
