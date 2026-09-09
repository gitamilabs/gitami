import { db } from "./index";
import { sql } from "drizzle-orm";

export async function ensureDatabaseTablesExist() {
  try {
    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS "pull_requests" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "repository_id" uuid,
        "repo_full_name" varchar(512) NOT NULL,
        "pr_number" integer NOT NULL,
        "title" text NOT NULL,
        "body" text,
        "state" varchar(64) NOT NULL DEFAULT 'open',
        "status" varchar(64) NOT NULL DEFAULT 'pending',
        "base_branch" varchar(255) NOT NULL DEFAULT 'main',
        "head_branch" varchar(255) NOT NULL,
        "base_sha" varchar(128),
        "head_sha" varchar(128),
        "author_login" varchar(255),
        "html_url" text,
        "created_at" timestamp with time zone NOT NULL DEFAULT now(),
        "updated_at" timestamp with time zone NOT NULL DEFAULT now(),
        CONSTRAINT "pull_requests_repo_pr_unique" UNIQUE ("repo_full_name", "pr_number")
      );
    `);

    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS "pr_reviews" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "pull_request_id" uuid NOT NULL REFERENCES "pull_requests"("id") ON DELETE CASCADE,
        "verdict" varchar(32) NOT NULL,
        "risk_score" real NOT NULL DEFAULT 0.0,
        "summary" text NOT NULL,
        "agent_rationale" text,
        "raw_review_json" jsonb,
        "created_at" timestamp with time zone NOT NULL DEFAULT now()
      );
    `);

    await db.execute(sql`
      CREATE TABLE IF NOT EXISTS "pr_issues" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "review_id" uuid NOT NULL REFERENCES "pr_reviews"("id") ON DELETE CASCADE,
        "title" varchar(512) NOT NULL,
        "description" text NOT NULL,
        "category" varchar(64) NOT NULL,
        "severity" varchar(32) NOT NULL DEFAULT 'warning',
        "file_path" text NOT NULL,
        "line" integer DEFAULT 1,
        "suggested_fix" text,
        "is_fixed" boolean NOT NULL DEFAULT false,
        "fix_pr_url" text,
        "created_at" timestamp with time zone NOT NULL DEFAULT now()
      );
    `);

    console.log("✅ Database tables ensured successfully (pull_requests, pr_reviews, pr_issues).");
  } catch (err) {
    console.error("⚠️ Ensure tables status:", err);
  }
}
