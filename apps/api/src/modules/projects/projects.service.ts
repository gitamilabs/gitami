import { eq, and, desc, or, sql } from "drizzle-orm";
import { db } from "../../db";
import {
  projects,
  organizations,
  organizationMembers,
  connectedRepositories,
  indexJobs,
  githubInstallations,
  type Project,
  type User,
  type IndexJob,
  type ConnectedRepository,
} from "../../db/schema";
import { env } from "../../configs/env";
import { getInstallationAccessToken, getInstallationTokenForRepo } from "../github/github-app.service";
import { generateSlug } from "../teams/teams.service";

/**
 * Standard build pipeline stages in canonical order.
 */
export const PIPELINE_STAGES = [
  { key: "SNAPSHOT", name: "Repository snapshot" },
  { key: "DISCOVERY", name: "File discovery" },
  { key: "AST_ANALYSIS", name: "Code analysis" },
  { key: "GRAPH_INDEXING", name: "Graph indexing" },
  { key: "SEMANTIC_INDEXING", name: "Semantic indexing" },
  { key: "VALIDATION", name: "Validation" },
] as const;

/**
 * Verifies that the user has membership in the project's organization.
 */
export async function getProjectForUser(
  user: User,
  projectIdOrSlug: string
): Promise<{ project: Project; organization: typeof organizations.$inferSelect } | null> {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(projectIdOrSlug);
  const projectCondition = isUuid
    ? or(eq(projects.id, projectIdOrSlug), eq(projects.slug, projectIdOrSlug))
    : eq(projects.slug, projectIdOrSlug);

  const [row] = await db
    .select({
      project: projects,
      organization: organizations,
    })
    .from(projects)
    .innerJoin(organizations, sql`${projects.organizationId}::text = ${organizations.id}::text`)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(projectCondition)
    .limit(1);

  return row || null;
}

/**
 * Fetches project repositories and recent builds.
 */
export async function getProjectDetails(user: User, projectIdOrSlug: string) {
  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) return null;

  const { project, organization } = result;

  const repositories = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.projectId, project.id),
        eq(connectedRepositories.isActive, true)
      )
    )
    .orderBy(desc(connectedRepositories.createdAt));

  const builds = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.projectId, project.id))
    .orderBy(desc(indexJobs.createdAt))
    .limit(20);

  return {
    project,
    organization,
    repositories,
    builds: builds.map(formatBuildWithStages),
  };
}

/**
 * Updates a project's name, description, and/or slug.
 */
export async function updateProject(
  user: User,
  projectIdOrSlug: string,
  updates: { name?: string; description?: string; slug?: string }
): Promise<Project> {
  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    throw new Error("Project not found or access denied");
  }

  const setValues: Partial<typeof projects.$inferInsert> = {};

  if (updates.name && updates.name.trim()) {
    setValues.name = updates.name.trim();
  }

  if (updates.description !== undefined) {
    setValues.description = updates.description.trim();
  }

  if (updates.slug && updates.slug.trim()) {
    const nextSlug = generateSlug(updates.slug);
    if (nextSlug !== result.project.slug) {
      const [existing] = await db
        .select()
        .from(projects)
        .where(eq(projects.slug, nextSlug))
        .limit(1);

      if (existing) {
        throw new Error(`Project slug "${nextSlug}" is already taken`);
      }
      setValues.slug = nextSlug;
    }
  }

  if (Object.keys(setValues).length === 0) {
    return result.project;
  }

  const [updated] = await db
    .update(projects)
    .set(setValues)
    .where(eq(projects.id, result.project.id))
    .returning();

  if (!updated) {
    throw new Error("Failed to update project");
  }

  return updated;
}

/**
 * Deletes a project, disassociating repositories and deleting index jobs.
 */
export async function deleteProject(
  user: User,
  projectIdOrSlug: string
): Promise<boolean> {
  const result = await getProjectForUser(user, projectIdOrSlug);
  if (!result) {
    throw new Error("Project not found or access denied");
  }

  const projectId = result.project.id;

  // Detach connected repositories
  await db
    .update(connectedRepositories)
    .set({ projectId: null })
    .where(eq(connectedRepositories.projectId, projectId));

  // Delete associated index jobs
  await db.delete(indexJobs).where(eq(indexJobs.projectId, projectId));

  // Delete project
  await db.delete(projects).where(eq(projects.id, projectId));

  return true;
}

/**
 * Attaches a repository to a project.

 */
export async function attachRepositoryToProject(
  projectId: string,
  repositoryId: string,
  userId: string,
  rootDirectory?: string | null
): Promise<ConnectedRepository | null> {
  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.id, repositoryId),
        eq(connectedRepositories.userId, userId)
      )
    )
    .limit(1);

  if (!repo) return null;

  const [updated] = await db
    .update(connectedRepositories)
    .set({
      projectId,
      isActive: true,
      rootDirectory: rootDirectory?.trim() || null,
    })
    .where(eq(connectedRepositories.id, repositoryId))
    .returning();

  return updated || null;
}

/**
 * Detaches a repository from a project.
 */
export async function detachRepositoryFromProject(
  projectId: string,
  repositoryId: string,
  userId: string
): Promise<boolean> {
  const [updated] = await db
    .update(connectedRepositories)
    .set({ projectId: null })
    .where(
      and(
        eq(connectedRepositories.id, repositoryId),
        eq(connectedRepositories.projectId, projectId),
        eq(connectedRepositories.userId, userId)
      )
    )
    .returning();

  if (updated) {
    // Clean up associated index jobs for this project-repo association
    await db
      .delete(indexJobs)
      .where(
        and(
          eq(indexJobs.projectId, projectId),
          eq(indexJobs.repositoryId, repositoryId)
        )
      );
  }

  return !!updated;
}

/**
 * Formats an index job with structured pipeline stages and honest metrics.
 */
export function formatBuildWithStages(job: IndexJob) {
  const currentStage = job.stage || "SNAPSHOT";
  const status = job.status; // QUEUED, RUNNING, COMPLETED, FAILED

  const stageKeys = PIPELINE_STAGES.map((s) => s.key);
  const currentIndex = stageKeys.indexOf(currentStage as any);

  const stages = PIPELINE_STAGES.map((stageDef, idx) => {
    let stageStatus: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" = "QUEUED";

    if (status === "COMPLETED") {
      stageStatus = "COMPLETED";
    } else if (status === "FAILED") {
      if (idx < currentIndex) stageStatus = "COMPLETED";
      else if (idx === currentIndex) stageStatus = "FAILED";
      else stageStatus = "QUEUED";
    } else if (status === "RUNNING") {
      if (idx < currentIndex) stageStatus = "COMPLETED";
      else if (idx === currentIndex) stageStatus = "RUNNING";
      else stageStatus = "QUEUED";
    } else {
      stageStatus = "QUEUED";
    }

    return {
      key: stageDef.key,
      name: stageDef.name,
      status: stageStatus,
    };
  });

  return {
    ...job,
    currentStage,
    stages,
  };
}

/**
 * Triggers a durable background build for a project repository.
 * Returns the created IndexJob immediately without blocking.
 */
export async function startProjectBuild(
  user: User,
  project: Project,
  repositoryId: string,
  branch?: string
): Promise<ReturnType<typeof formatBuildWithStages>> {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(repositoryId);
  const repoCondition = isUuid
    ? and(
        eq(connectedRepositories.id, repositoryId),
        eq(connectedRepositories.projectId, project.id),
        eq(connectedRepositories.userId, user.id)
      )
    : and(
        or(
          eq(connectedRepositories.fullName, repositoryId),
          eq(connectedRepositories.name, repositoryId)
        ),
        eq(connectedRepositories.projectId, project.id),
        eq(connectedRepositories.userId, user.id)
      );

  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(repoCondition)
    .limit(1);

  if (!repo) {
    throw new Error("Repository not found in project or access denied");
  }

  const targetBranch = branch || repo.defaultBranch || "main";

  // Create initial durable IndexJob in PostgreSQL
  const [job] = await db
    .insert(indexJobs)
    .values({
      projectId: project.id,
      repositoryId: repo.fullName,
      targetCommitSha: "HEAD",
      branch: targetBranch,
      status: "RUNNING",
      stage: "SNAPSHOT",
      progress: 0,
      startedAt: new Date(),
    })
    .returning();

  if (!job) {
    throw new Error("Failed to create index job");
  }

  // Run durable processing asynchronously in the background
  executeBackgroundBuild(job.id, repo, targetBranch).catch((err) => {
    console.error(`Background build execution error for job ${job.id}:`, err);
  });

  return formatBuildWithStages(job);
}

/**
 * Asynchronous background worker for executing repository indexing and recording real stages.
 */
async function executeBackgroundBuild(
  jobId: string,
  repo: ConnectedRepository,
  branch: string
) {
  let aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";

  // Resolve GitHub App token if available
  let token: string | undefined;
  if (repo.installationId && !repo.githubRepoId.startsWith("local:")) {
    try {
      const [inst] = await db
        .select()
        .from(githubInstallations)
        .where(eq(githubInstallations.id, repo.installationId))
        .limit(1);

      if (inst?.installationId) {
        token = await getInstallationAccessToken(inst.installationId);
      }
    } catch (err) {
      console.warn("Could not get installation access token for build:", err);
    }
  }

  // Fallback: If token was not resolved via installationId, query GitHub App API by repo full name
  if (!token && repo.fullName && repo.fullName.includes("/") && !repo.githubRepoId.startsWith("local:")) {
    const parts = repo.fullName.split("/");
    const owner = parts[0];
    const name = parts[1];
    if (owner && name) {
      try {
        const resolved = await getInstallationTokenForRepo(owner, name);
        if (resolved) token = resolved;
      } catch (err) {
        console.warn("Fallback getInstallationTokenForRepo failed for build:", err);
      }
    }
  }

  const cleanRootDir = repo.rootDirectory?.trim() || undefined;
  const isLocal = repo.githubRepoId.startsWith("local:");
  const payload = isLocal
    ? {
        repo_id: repo.name,
        repo_dir: repo.fullName,
        branch,
        project_id: repo.projectId || "default",
        team_id: repo.userId,
        root_directory: cleanRootDir,
      }
    : {
        repo_id: repo.fullName,
        full_name: repo.fullName,
        access_token: token,
        branch,
        project_id: repo.projectId || "default",
        team_id: repo.userId,
        root_directory: cleanRootDir,
      };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000); // 10 minute timeout

  try {
    // Connect to AI Service with timeout
    let res = await fetch(`${aiServiceUrl}/api/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!res.ok && (res.status === 502 || res.status === 503) && aiServiceUrl !== "http://localhost:8000") {
      aiServiceUrl = "http://localhost:8000";
      res = await fetch(`${aiServiceUrl}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    }

    if (!res.ok) {
      clearTimeout(timeoutId);
      const errData = (await res.json().catch(() => ({}))) as any;
      const errorMsg = errData.detail || errData.error || `AI service returned status ${res.status}`;
      await db
        .update(indexJobs)
        .set({
          status: "FAILED",
          error: errorMsg,
          completedAt: new Date(),
        })
        .where(eq(indexJobs.id, jobId));
      return;
    }

    // Check if response is streaming ndjson or standard json
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("ndjson") && res.body) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let lastStatus = "RUNNING";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.status) {
              lastStatus = event.status;
            }
            if (event.stage) {
              await db
                .update(indexJobs)
                .set({
                  stage: event.stage,
                  stats: event.stats || {},
                  error: event.error || null,
                  status: event.status || "RUNNING",
                  completedAt: event.status === "COMPLETED" || event.status === "FAILED" ? new Date() : undefined,
                })
                .where(eq(indexJobs.id, jobId));
            }
          } catch {
            // ignore malformed line
          }
        }
      }

      // Check if build actually reached a terminal state
      if (lastStatus !== "COMPLETED" && lastStatus !== "FAILED") {
        console.warn(`Build stream ended unexpectedly without completion for job ${jobId}`);
        await db
          .update(indexJobs)
          .set({
            status: "FAILED",
            error: "Build stream disconnected unexpectedly before completion",
            completedAt: new Date(),
          })
          .where(eq(indexJobs.id, jobId));
      }
    } else {
      const data = (await res.json()) as any;
      await db
        .update(indexJobs)
        .set({
          status: "COMPLETED",
          stage: "COMPLETED",
          progress: 100,
          stats: {
            symbols_parsed: data.symbols_parsed,
            files_parsed: data.files_parsed,
            packages: data.packages,
            edges_count: data.edges_count,
            duration_seconds: data.duration_seconds,
          },
          completedAt: new Date(),
        })
        .where(eq(indexJobs.id, jobId));
    }
  } catch (err: any) {
    console.error(`Build execution error for job ${jobId}:`, err);
    const errorMsg =
      err.name === "AbortError"
        ? "Indexing build timed out after 10 minutes"
        : err.message || "Failed to complete indexing build";
    await db
      .update(indexJobs)
      .set({
        status: "FAILED",
        error: errorMsg,
        completedAt: new Date(),
      })
      .where(eq(indexJobs.id, jobId));
  } finally {
    clearTimeout(timeoutId);
  }
}
