import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import { env } from "../configs/env";

async function main() {
  console.log("⏳ Running migrations on database...");
  const isSsl = env.DB_URL.includes("sslmode=require") || env.DB_URL.includes("neon.tech");
  const client = postgres(env.DB_URL, { max: 1, ...(isSsl ? { ssl: "require" } : {}) });
  const db = drizzle(client);
  await migrate(db, { migrationsFolder: "./drizzle" });
  await client.end();
  console.log("✅ Migrations completed successfully!");
}

main().catch((err) => {
  console.error("❌ Migration failed:", err);
  process.exit(1);
});

