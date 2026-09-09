import type { Context, Next } from "hono";
import { verifySessionToken, getUserById } from "../modules/auth/auth.service";
import type { User } from "../db/schema";

export interface AuthContextVariables {
  user: User;
}

/**
 * JWT authentication middleware.
 * Extracts Bearer token from Authorization header (or `token` query param),
 * verifies it, loads the user from DB, and sets it on the Hono context.
 */
export async function authMiddleware(
  c: Context<{ Variables: AuthContextVariables }>,
  next: Next,
) {
  const authHeader =
    c.req.header("authorization") || c.req.header("Authorization");

  let token: string | null = null;

  if (authHeader?.startsWith("Bearer ")) {
    token = authHeader.substring(7).trim();
  }

  if (!token) {
    token = c.req.query("token") || null;
  }

  if (!token) {
    return c.json(
      { error: "Unauthorized: Missing authentication token" },
      401,
    );
  }

  const userId = await verifySessionToken(token);
  if (!userId) {
    return c.json(
      { error: "Unauthorized: Invalid or expired token" },
      401,
    );
  }

  const user = await getUserById(userId);
  if (!user) {
    return c.json({ error: "Unauthorized: User not found" }, 401);
  }

  c.set("user", user);
  await next();
}
