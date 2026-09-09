import { pgTable, uuid, varchar, text, timestamp } from "drizzle-orm/pg-core";

export const projects = pgTable("projects", {
  id: uuid("id").primaryKey().defaultRandom(),
  organizationId: varchar("organization_id", { length: 64 }).notNull().default("default_org"),
  name: varchar("name", { length: 255 }).notNull(),
  slug: varchar("slug", { length: 255 }).notNull().unique(),
  description: text("description"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export type Project = typeof projects.$inferSelect;
export type NewProject = typeof projects.$inferInsert;
