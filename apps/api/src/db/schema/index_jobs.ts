import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  timestamp,
  jsonb,
} from "drizzle-orm/pg-core";

export const indexJobs = pgTable("index_jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: varchar("project_id", { length: 128 }).notNull().default("default"),
  repositoryId: varchar("repository_id", { length: 255 }).notNull(),
  type: varchar("type", { length: 32 }).notNull().default("INITIAL"), // INITIAL, PUSH, MANUAL, REINDEX
  baseCommitSha: varchar("base_commit_sha", { length: 128 }),
  targetCommitSha: varchar("target_commit_sha", { length: 128 }).notNull(),
  branch: varchar("branch", { length: 255 }).notNull().default("main"),
  status: varchar("status", { length: 32 }).notNull().default("QUEUED"), // QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
  progress: integer("progress").notNull().default(0),
  stage: varchar("stage", { length: 64 }).notNull().default("PENDING"),
  stats: jsonb("stats").$type<Record<string, unknown>>().default({}),
  error: text("error"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  startedAt: timestamp("started_at", { withTimezone: true }),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

export type IndexJob = typeof indexJobs.$inferSelect;
export type NewIndexJob = typeof indexJobs.$inferInsert;
