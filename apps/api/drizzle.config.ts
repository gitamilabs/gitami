import { defineConfig } from "drizzle-kit";
import { neonConfig } from "@neondatabase/serverless";
import ws from "ws";

// Required for drizzle-kit to communicate with Neon over WebSocket
neonConfig.webSocketConstructor = ws;

export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema/index.ts",
  out: "./drizzle",
  dbCredentials: {
    url: process.env.DB_URL!,
  },
  verbose: true,
  strict: true,
});
