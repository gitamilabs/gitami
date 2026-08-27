import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  timestamp,
} from "drizzle-orm/pg-core";
import { connectedRepositories } from "./connected_repositories";

export const pullRequests = pgTable("pull_requests", {
  id: uuid("id").primaryKey().defaultRandom(),
  repositoryId: uuid("repository_id")
    .references(() => connectedRepositories.id, { onDelete: "cascade" }),
  repoFullName: varchar("repo_full_name", { length: 512 }).notNull(),
  prNumber: integer("pr_number").notNull(),
  title: text("title").notNull(),
  body: text("body"),
  state: varchar("state", { length: 64 }).notNull().default("open"), // open, closed, merged
  status: varchar("status", { length: 64 }).notNull().default("pending"), // pending, reviewed, skipped_ai_fix, error
  baseBranch: varchar("base_branch", { length: 255 }).notNull().default("main"),
  headBranch: varchar("head_branch", { length: 255 }).notNull(),
  baseSha: varchar("base_sha", { length: 128 }),
  headSha: varchar("head_sha", { length: 128 }),
  authorLogin: varchar("author_login", { length: 255 }),
  htmlUrl: text("html_url"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type PullRequest = typeof pullRequests.$inferSelect;
export type NewPullRequest = typeof pullRequests.$inferInsert;
