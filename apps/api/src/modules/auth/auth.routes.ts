import { Hono } from "hono";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import {
  getOAuthAuthorizeUrl,
  handleCallback,
} from "./auth.service";
import { env } from "../../configs/env";

const authRouter = new Hono<{ Variables: AuthContextVariables }>();

/**
 * GET /github
 * Redirects the user to GitHub OAuth authorization screen.
 */
authRouter.get("/github", (c) => {
  const state = crypto.randomUUID();
  const url = getOAuthAuthorizeUrl(state);
  return c.redirect(url);
});

/**
 * GET /github/callback
 * GitHub OAuth callback - exchanges code for token, upserts user, signs JWT.
 */
authRouter.get("/github/callback", async (c) => {
  const code = c.req.query("code");
  const error = c.req.query("error");
  const errorDescription = c.req.query("error_description");

  if (error) {
    return c.json({ error: errorDescription || error }, 400);
  }

  if (!code) {
    return c.json(
      { error: "Missing authorization code from GitHub" },
      400,
    );
  }

  try {
    const { user, token } = await handleCallback(code);

    // If the client accepts JSON, return it directly
    const acceptHeader = c.req.header("Accept") || "";
    if (acceptHeader.includes("application/json")) {
      return c.json({ user, token });
    }

    // Otherwise redirect to the frontend callback route with the token
    const baseUrl = (env.FRONTEND_URL || "http://localhost:3000").replace(/\/+$/, "");
    const redirectUrl = new URL(`${baseUrl}/auth/callback`);
    redirectUrl.searchParams.set("token", token);
    return c.redirect(redirectUrl.toString());
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Authentication failed";
    console.error("OAuth callback error:", err);
    return c.json({ error: message }, 500);
  }
});

/**
 * GET /me
 * Returns the authenticated user profile with normalized fields.
 */
authRouter.get("/me", authMiddleware, (c) => {
  const user = c.get("user");
  const normalized = {
    ...user,
    avatar_url: user.avatarUrl,
    github_id: user.githubId,
    name: user.username,
    created_at: user.createdAt,
    updated_at: user.updatedAt,
  };
  return c.json({ user: normalized });
});

/**
 * POST /logout
 * Acknowledges logout. Token invalidation is client-side.
 */
authRouter.post("/logout", authMiddleware, (c) => {
  return c.json({ success: true, message: "Logged out successfully" });
});

export default authRouter;
