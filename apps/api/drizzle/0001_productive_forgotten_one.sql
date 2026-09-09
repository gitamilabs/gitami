CREATE TABLE IF NOT EXISTS "index_jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" varchar(128) DEFAULT 'default' NOT NULL,
	"repository_id" varchar(255) NOT NULL,
	"type" varchar(32) DEFAULT 'INITIAL' NOT NULL,
	"base_commit_sha" varchar(128),
	"target_commit_sha" varchar(128) NOT NULL,
	"branch" varchar(255) DEFAULT 'main' NOT NULL,
	"status" varchar(32) DEFAULT 'QUEUED' NOT NULL,
	"progress" integer DEFAULT 0 NOT NULL,
	"stage" varchar(64) DEFAULT 'PENDING' NOT NULL,
	"stats" jsonb DEFAULT '{}'::jsonb,
	"error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "pr_issues" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"review_id" uuid NOT NULL,
	"title" varchar(512) NOT NULL,
	"description" text NOT NULL,
	"category" varchar(64) NOT NULL,
	"severity" varchar(32) DEFAULT 'warning' NOT NULL,
	"file_path" text NOT NULL,
	"line" integer DEFAULT 1,
	"suggested_fix" text,
	"is_fixed" boolean DEFAULT false NOT NULL,
	"fix_pr_url" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "pr_reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"pull_request_id" uuid NOT NULL,
	"verdict" varchar(32) NOT NULL,
	"risk_score" real DEFAULT 0 NOT NULL,
	"summary" text NOT NULL,
	"agent_rationale" text,
	"raw_review_json" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "projects" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"organization_id" varchar(64) DEFAULT 'default_org' NOT NULL,
	"name" varchar(255) NOT NULL,
	"slug" varchar(255) NOT NULL,
	"description" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "projects_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "pull_requests" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"repository_id" uuid,
	"repo_full_name" varchar(512) NOT NULL,
	"pr_number" integer NOT NULL,
	"title" text NOT NULL,
	"body" text,
	"state" varchar(64) DEFAULT 'open' NOT NULL,
	"status" varchar(64) DEFAULT 'pending' NOT NULL,
	"base_branch" varchar(255) DEFAULT 'main' NOT NULL,
	"head_branch" varchar(255) NOT NULL,
	"base_sha" varchar(128),
	"head_sha" varchar(128),
	"author_login" varchar(255),
	"html_url" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "repository_index_states" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"repository_id" varchar(255) NOT NULL,
	"branch" varchar(255) DEFAULT 'main' NOT NULL,
	"indexed_commit_sha" varchar(128) NOT NULL,
	"index_version" varchar(32) DEFAULT 'v1' NOT NULL,
	"schema_version" varchar(32) DEFAULT 'v1' NOT NULL,
	"parser_version" varchar(32) DEFAULT '1.0.0' NOT NULL,
	"status" varchar(32) DEFAULT 'INITIALIZING' NOT NULL,
	"stats" jsonb DEFAULT '{}'::jsonb,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "connected_repositories" ADD COLUMN IF NOT EXISTS "project_id" uuid;
--> statement-breakpoint
DO $$ BEGIN
  ALTER TABLE "pr_issues" ADD CONSTRAINT "pr_issues_review_id_pr_reviews_id_fk" FOREIGN KEY ("review_id") REFERENCES "public"."pr_reviews"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
  ALTER TABLE "pr_reviews" ADD CONSTRAINT "pr_reviews_pull_request_id_pull_requests_id_fk" FOREIGN KEY ("pull_request_id") REFERENCES "public"."pull_requests"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
  ALTER TABLE "pull_requests" ADD CONSTRAINT "pull_requests_repository_id_connected_repositories_id_fk" FOREIGN KEY ("repository_id") REFERENCES "public"."connected_repositories"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
  ALTER TABLE "connected_repositories" ADD CONSTRAINT "connected_repositories_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE set null ON UPDATE no action;
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;