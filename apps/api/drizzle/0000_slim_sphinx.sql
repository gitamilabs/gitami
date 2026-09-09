CREATE TABLE "connected_repositories" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"installation_id" uuid NOT NULL,
	"user_id" uuid NOT NULL,
	"github_repo_id" varchar(64) NOT NULL,
	"name" varchar(255) NOT NULL,
	"full_name" varchar(512) NOT NULL,
	"is_private" boolean DEFAULT false NOT NULL,
	"html_url" text NOT NULL,
	"default_branch" varchar(255) DEFAULT 'main' NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "connected_repositories_github_repo_id_unique" UNIQUE("github_repo_id")
);
--> statement-breakpoint
CREATE TABLE "github_installations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"installation_id" varchar(64) NOT NULL,
	"account_login" varchar(255) NOT NULL,
	"account_id" varchar(64) NOT NULL,
	"target_type" varchar(32) DEFAULT 'User' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "github_installations_installation_id_unique" UNIQUE("installation_id")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"github_id" varchar(64) NOT NULL,
	"username" varchar(255) NOT NULL,
	"email" varchar(255),
	"avatar_url" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_github_id_unique" UNIQUE("github_id")
);
--> statement-breakpoint
ALTER TABLE "connected_repositories" ADD CONSTRAINT "connected_repositories_installation_id_github_installations_id_fk" FOREIGN KEY ("installation_id") REFERENCES "public"."github_installations"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "connected_repositories" ADD CONSTRAINT "connected_repositories_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "github_installations" ADD CONSTRAINT "github_installations_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;