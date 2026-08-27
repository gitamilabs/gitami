import {
  pgTable,
  uuid,
  varchar,
  text,
  real,
  timestamp,
  jsonb,
} from "drizzle-orm/pg-core";
import { pullRequests } from "./pull_requests";

export const prReviews = pgTable("pr_reviews", {
  id: uuid("id").primaryKey().defaultRandom(),
  pullRequestId: uuid("pull_request_id")
    .notNull()
    .references(() => pullRequests.id, { onDelete: "cascade" }),
  verdict: varchar("verdict", { length: 32 }).notNull(), // ACCEPT, SUGGEST, REJECT
  riskScore: real("risk_score").notNull().default(0.0),
  summary: text("summary").notNull(),
  agentRationale: text("agent_rationale"),
  rawReviewJson: jsonb("raw_review_json"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export type PRReview = typeof prReviews.$inferSelect;
export type NewPRReview = typeof prReviews.$inferInsert;
