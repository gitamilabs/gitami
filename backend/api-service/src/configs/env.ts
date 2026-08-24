import { z } from "zod";

const envSchema = z.object({
  PORT: z.string().default("5000"),
  NODE_ENV: z
    .enum(["development", "production", "test"])
    .default("development"),

  // Database
  DB_URL: z.string().min(1, "DB_URL is required"),

  // GitHub OAuth App (User Auth)
  GITHUB_CLIENT_ID: z.string().default("mock_client_id"),
  GITHUB_CLIENT_SECRET: z.string().default("mock_client_secret"),
  GITHUB_OAUTH_REDIRECT_URI: z
    .string()
    .default("http://localhost:5000/api/v1/auth/github/callback"),

  // Platform GitHub App (Repo Access & Webhooks)
  GITHUB_APP_ID: z.string().default("123456"),
  GITHUB_APP_SLUG: z.string().default("my-repo-manager-app"),
  GITHUB_APP_PRIVATE_KEY: z
    .string()
    .default(
      "-----BEGIN RSA PRIVATE KEY-----\nMOCK_KEY\n-----END RSA PRIVATE KEY-----",
    ),
  GITHUB_WEBHOOK_SECRET: z.string().default("mock_webhook_secret"),

  // JWT & Session Security
  JWT_SECRET: z
    .string()
    .default("super_secret_jwt_key_change_in_production_32bytes"),
  FRONTEND_URL: z.string().default("http://localhost:3000"),
  AI_SERVICE_URL: z.string().default("http://localhost:8000"),
});


export type Env = z.infer<typeof envSchema>;

function loadEnv(): Env {
  const result = envSchema.safeParse(process.env);

  if (!result.success) {
    const formatted = result.error.flatten().fieldErrors;
    console.warn("⚠️ Environment variables fallback to defaults:", formatted);
    return envSchema.parse({});
  }

  return result.data;
}

export const env = loadEnv();
