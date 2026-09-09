import {
  pgTable,
  uuid,
  varchar,
  timestamp,
} from "drizzle-orm/pg-core";
import { users } from "./users";

export const githubInstallations = pgTable("github_installations", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  installationId: varchar("installation_id", { length: 64 }).notNull().unique(),
  accountLogin: varchar("account_login", { length: 255 }).notNull(),
  accountId: varchar("account_id", { length: 64 }).notNull(),
  targetType: varchar("target_type", { length: 32 }).notNull().default("User"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type GitHubInstallation = typeof githubInstallations.$inferSelect;
export type NewGitHubInstallation = typeof githubInstallations.$inferInsert;
