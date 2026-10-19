import { Hono } from "hono";
import {
  authMiddleware,
  type AuthContextVariables,
} from "../../middlewares/auth.middleware";
import {
  getUserTeams,
  getTeamBySlug,
  createTeam,
  updateTeam,
  deleteTeam,
  getTeamProjectsWithMetadata,
  createTeamProject,
  getTeamMembers,
  addTeamMember,
  updateTeamMemberRole,
  removeTeamMember,
} from "./teams.service";

const teamsRouter = new Hono<{ Variables: AuthContextVariables }>();

teamsRouter.use("*", authMiddleware);

/**
 * GET /
 * Returns all teams accessible to the current user.
 */
teamsRouter.get("/", async (c) => {
  const user = c.get("user");
  const teams = await getUserTeams(user);
  return c.json({ teams });
});

/**
 * POST /
 * Creates a new team with the current user as OWNER.
 */
teamsRouter.post("/", async (c) => {
  const user = c.get("user");
  const body = await c.req.json().catch(() => ({}));
  const name = (body.name || "").trim();

  if (!name) {
    return c.json({ error: "Team name is required" }, 400);
  }

  const team = await createTeam(user, name);
  return c.json({ team }, 201);
});

/**
 * GET /:teamSlug
 * Returns team details for the given slug if the user has access.
 */
teamsRouter.get("/:teamSlug", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");

  const team = await getTeamBySlug(user, teamSlug);
  if (!team) {
    return c.json({ error: "Team not found or access denied" }, 404);
  }

  return c.json({ team });
});

/**
 * PATCH /:teamSlug
 * Updates team name and/or slug.
 */
teamsRouter.patch("/:teamSlug", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");
  const body = await c.req.json().catch(() => ({}));

  try {
    const updated = await updateTeam(user, teamSlug, {
      name: body.name,
      slug: body.slug,
    });
    return c.json({ team: updated });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to update team" }, 400);
  }
});

/**
 * DELETE /:teamSlug
 * Deletes team, projects, and memberships.
 */
teamsRouter.delete("/:teamSlug", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");

  try {
    await deleteTeam(user, teamSlug);
    return c.json({ success: true, message: "Team deleted successfully" });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to delete team" }, 400);
  }
});

/**
 * GET /:teamSlug/members
 * Lists all members of the team.
 */
teamsRouter.get("/:teamSlug/members", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");

  try {
    const members = await getTeamMembers(user, teamSlug);
    return c.json({ members });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to fetch members" }, 400);
  }
});

/**
 * POST /:teamSlug/members
 * Adds a new member to the team by username or email.
 */
teamsRouter.post("/:teamSlug/members", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");
  const body = await c.req.json().catch(() => ({}));
  const usernameOrEmail = (body.usernameOrEmail || body.username || body.email || "").trim();
  const role = (body.role || "MEMBER").trim();

  if (!usernameOrEmail) {
    return c.json({ error: "Username or email is required" }, 400);
  }

  try {
    const member = await addTeamMember(user, teamSlug, usernameOrEmail, role);
    return c.json({ member }, 201);
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to add team member" }, 400);
  }
});

/**
 * PATCH /:teamSlug/members/:memberId
 * Updates member role (OWNER, MEMBER, VIEWER).
 */
teamsRouter.patch("/:teamSlug/members/:memberId", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");
  const memberId = c.req.param("memberId");
  const body = await c.req.json().catch(() => ({}));
  const role = (body.role || "").trim();

  if (!role) {
    return c.json({ error: "Role is required" }, 400);
  }

  try {
    const member = await updateTeamMemberRole(user, teamSlug, memberId, role);
    return c.json({ member });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to update member role" }, 400);
  }
});

/**
 * DELETE /:teamSlug/members/:memberId
 * Removes a member from the team.
 */
teamsRouter.delete("/:teamSlug/members/:memberId", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");
  const memberId = c.req.param("memberId");

  try {
    await removeTeamMember(user, teamSlug, memberId);
    return c.json({ success: true, message: "Member removed from team" });
  } catch (err: any) {
    return c.json({ error: err.message || "Failed to remove member" }, 400);
  }
});

/**
 * GET /:teamSlug/projects
 * Returns all projects belonging to the team.
 */
teamsRouter.get("/:teamSlug/projects", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");

  const team = await getTeamBySlug(user, teamSlug);
  if (!team) {
    return c.json({ error: "Team not found or access denied" }, 404);
  }

  const projects = await getTeamProjectsWithMetadata(team.id);
  return c.json({ projects, team });
});

/**
 * POST /:teamSlug/projects
 * Creates a project in the team.
 */
teamsRouter.post("/:teamSlug/projects", async (c) => {
  const user = c.get("user");
  const teamSlug = c.req.param("teamSlug");
  const body = await c.req.json().catch(() => ({}));
  const name = (body.name || "").trim();
  const description = (body.description || "").trim();

  if (!name) {
    return c.json({ error: "Project name is required" }, 400);
  }

  const team = await getTeamBySlug(user, teamSlug);
  if (!team) {
    return c.json({ error: "Team not found or access denied" }, 404);
  }

  const project = await createTeamProject(team.id, name, description);
  return c.json({ project }, 201);
});

export default teamsRouter;

