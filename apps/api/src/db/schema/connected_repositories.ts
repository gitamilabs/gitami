import {
  pgTable,
  uuid,
  varchar,
  text,
  boolean,
  timestamp,
} from "drizzle-orm/pg-core";
import { users } from "./users";
import { githubInstallations } from "./github_installations";
import { projects } from "./projects";

export const connectedRepositories = pgTable("connected_repositories", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: uuid("project_id").references(() => projects.id, { onDelete: "set null" }),
  installationId: uuid("installation_id")
    .notNull()
    .references(() => githubInstallations.id, { onDelete: "cascade" }),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  githubRepoId: varchar("github_repo_id", { length: 64 }).notNull().unique(),
  name: varchar("name", { length: 255 }).notNull(),
  fullName: varchar("full_name", { length: 512 }).notNull(),
  isPrivate: boolean("is_private").notNull().default(false),
  htmlUrl: text("html_url").notNull(),
  defaultBranch: varchar("default_branch", { length: 255 })
    .notNull()
    .default("main"),
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type ConnectedRepository = typeof connectedRepositories.$inferSelect;
export type NewConnectedRepository = typeof connectedRepositories.$inferInsert;
