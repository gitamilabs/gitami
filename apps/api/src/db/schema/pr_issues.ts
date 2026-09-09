import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  boolean,
  timestamp,
} from "drizzle-orm/pg-core";
import { prReviews } from "./pr_reviews";

export const prIssues = pgTable("pr_issues", {
  id: uuid("id").primaryKey().defaultRandom(),
  reviewId: uuid("review_id")
    .notNull()
    .references(() => prReviews.id, { onDelete: "cascade" }),
  title: varchar("title", { length: 512 }).notNull(),
  description: text("description").notNull(),
  category: varchar("category", { length: 64 }).notNull(), // bug, security, logical_error, convention, blast_radius
  severity: varchar("severity", { length: 32 }).notNull().default("warning"), // error, warning, info
  filePath: text("file_path").notNull(),
  line: integer("line").default(1),
  suggestedFix: text("suggested_fix"),
  isFixed: boolean("is_fixed").notNull().default(false),
  fixPrUrl: text("fix_pr_url"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export type PRIssue = typeof prIssues.$inferSelect;
export type NewPRIssue = typeof prIssues.$inferInsert;
