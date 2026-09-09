import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import { env } from "../configs/env";
import * as schema from "./schema";

const isSsl = env.DB_URL.includes("sslmode=require") || env.DB_URL.includes("neon.tech");
const client = postgres(env.DB_URL, isSsl ? { ssl: "require" } : {});

export const db = drizzle(client, { schema });

