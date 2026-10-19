import { Hono } from "hono";
import { eq, and, sql } from "drizzle-orm";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import { db } from "../../db";
import { indexJobs, projects, organizationMembers } from "../../db/schema";
import { formatBuildWithStages } from "../projects/projects.service";

const buildsRouter = new Hono<{ Variables: AuthContextVariables }>();

buildsRouter.use("*", authMiddleware);

/**
 * GET /:buildId
 * Returns the status, stages, and metrics of a single build.
 */
buildsRouter.get("/:buildId", async (c) => {
  const user = c.get("user");
  const buildId = c.req.param("buildId");

  const [job] = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.id, buildId))
    .limit(1);

  if (!job) {
    return c.json({ error: "Build not found" }, 404);
  }

  // Verify access via project organization membership
  const [proj] = await db
    .select()
    .from(projects)
    .innerJoin(
      organizationMembers,
      and(
        sql`${organizationMembers.organizationId}::text = ${projects.organizationId}::text`,
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(sql`${projects.id}::text = ${job.projectId}::text`)
    .limit(1);

  if (!proj) {
    return c.json({ error: "Access denied to this build" }, 403);
  }

  return c.json({ build: formatBuildWithStages(job) });
});

/**
 * POST /:buildId/cancel
 * Cancels or forces termination of an active or stuck build.
 */
buildsRouter.post("/:buildId/cancel", async (c) => {
  const user = c.get("user");
  const buildId = c.req.param("buildId");

  const [job] = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.id, buildId))
    .limit(1);

  if (!job) {
    return c.json({ error: "Build not found" }, 404);
  }

  // Verify access via project organization membership
  const [proj] = await db
    .select()
    .from(projects)
    .innerJoin(
      organizationMembers,
      and(
        sql`${organizationMembers.organizationId}::text = ${projects.organizationId}::text`,
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(sql`${projects.id}::text = ${job.projectId}::text`)
    .limit(1);

  if (!proj) {
    return c.json({ error: "Access denied to this build" }, 403);
  }

  const [updated] = await db
    .update(indexJobs)
    .set({
      status: "FAILED",
      error: "Build cancelled by user",
      completedAt: new Date(),
    })
    .where(eq(indexJobs.id, buildId))
    .returning();

  if (!updated) {
    return c.json({ error: "Failed to cancel build" }, 500);
  }

  return c.json({ success: true, build: formatBuildWithStages(updated) });
});

/**
 * PATCH /:buildId
 * Updates build status, stage, or error message.
 */
buildsRouter.patch("/:buildId", async (c) => {
  const user = c.get("user");
  const buildId = c.req.param("buildId");
  const body = await c.req.json().catch(() => ({}));

  const [job] = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.id, buildId))
    .limit(1);

  if (!job) {
    return c.json({ error: "Build not found" }, 404);
  }

  // Verify access via project organization membership
  const [proj] = await db
    .select()
    .from(projects)
    .innerJoin(
      organizationMembers,
      and(
        sql`${organizationMembers.organizationId}::text = ${projects.organizationId}::text`,
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(sql`${projects.id}::text = ${job.projectId}::text`)
    .limit(1);

  if (!proj) {
    return c.json({ error: "Access denied to this build" }, 403);
  }

  const setValues: Partial<typeof indexJobs.$inferInsert> = {};
  if (body.status) setValues.status = body.status;
  if (body.stage) setValues.stage = body.stage;
  if (body.error !== undefined) setValues.error = body.error;

  const [updated] = await db
    .update(indexJobs)
    .set(setValues)
    .where(eq(indexJobs.id, buildId))
    .returning();

  if (!updated) {
    return c.json({ error: "Failed to update build" }, 500);
  }

  return c.json({ success: true, build: formatBuildWithStages(updated) });
});

/**
 * DELETE /:buildId
 * Deletes a build record.
 */
buildsRouter.delete("/:buildId", async (c) => {
  const user = c.get("user");
  const buildId = c.req.param("buildId");

  const [job] = await db
    .select()
    .from(indexJobs)
    .where(eq(indexJobs.id, buildId))
    .limit(1);

  if (!job) {
    return c.json({ error: "Build not found" }, 404);
  }

  // Verify access via project organization membership
  const [proj] = await db
    .select()
    .from(projects)
    .innerJoin(
      organizationMembers,
      and(
        sql`${organizationMembers.organizationId}::text = ${projects.organizationId}::text`,
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(sql`${projects.id}::text = ${job.projectId}::text`)
    .limit(1);

  if (!proj) {
    return c.json({ error: "Access denied to this build" }, 403);
  }

  await db.delete(indexJobs).where(eq(indexJobs.id, buildId));

  return c.json({ success: true, message: "Build deleted successfully" });
});

export default buildsRouter;

