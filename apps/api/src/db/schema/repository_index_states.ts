import {
  pgTable,
  uuid,
  varchar,
  timestamp,
  jsonb,
} from "drizzle-orm/pg-core";

export const repositoryIndexStates = pgTable("repository_index_states", {
  id: uuid("id").primaryKey().defaultRandom(),
  repositoryId: varchar("repository_id", { length: 255 }).notNull(),
  branch: varchar("branch", { length: 255 }).notNull().default("main"),
  indexedCommitSha: varchar("indexed_commit_sha", { length: 128 }).notNull(),
  indexVersion: varchar("index_version", { length: 32 }).notNull().default("v1"),
  schemaVersion: varchar("schema_version", { length: 32 }).notNull().default("v1"),
  parserVersion: varchar("parser_version", { length: 32 }).notNull().default("1.0.0"),
  status: varchar("status", { length: 32 }).notNull().default("INITIALIZING"), // INITIALIZING, READY, STALE, FAILED
  stats: jsonb("stats").$type<Record<string, unknown>>().default({}),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type RepositoryIndexState = typeof repositoryIndexStates.$inferSelect;
export type NewRepositoryIndexState = typeof repositoryIndexStates.$inferInsert;
