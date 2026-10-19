import { eq, and, desc, or, ne, sql } from "drizzle-orm";
import { db } from "../../db";
import {
  organizations,
  organizationMembers,
  projects,
  connectedRepositories,
  indexJobs,
  users,
  type Organization,
  type OrganizationMember,
  type Project,
  type User,
} from "../../db/schema";

/**
 * Generates a clean URL slug from a name.
 */
export function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "team";
}

/**
 * Ensures the user has at least one personal team.
 * If none exists, creates one and associates any existing legacy projects.
 */
export async function getUserTeams(user: User): Promise<Organization[]> {
  const members = await db
    .select({
      org: organizations,
    })
    .from(organizationMembers)
    .innerJoin(organizations, eq(organizationMembers.organizationId, organizations.id))
    .where(eq(organizationMembers.userId, user.id));

  if (members.length > 0) {
    return members.map((m) => m.org);
  }

  // Create personal team for user
  const baseSlug = generateSlug(user.username);
  let slug = baseSlug;

  const [existingOrg] = await db
    .select()
    .from(organizations)
    .where(eq(organizations.slug, slug))
    .limit(1);

  if (existingOrg) {
    slug = `${baseSlug}-${Math.random().toString(36).substring(2, 6)}`;
  }

  const [newOrg] = await db
    .insert(organizations)
    .values({
      name: `${user.username}`,
      slug,
    })
    .returning();

  if (!newOrg) {
    throw new Error("Failed to create personal organization");
  }

  await db.insert(organizationMembers).values({
    organizationId: newOrg.id,
    userId: user.id,
    role: "OWNER",
  });

  // Migrate any legacy "default_org" projects to this user's initial team
  await db
    .update(projects)
    .set({ organizationId: newOrg.id })
    .where(eq(projects.organizationId, "default_org"));

  return [newOrg];
}

/**
 * Fetches an organization by slug, verifying user membership.
 */
export async function getTeamBySlug(user: User, teamSlug: string): Promise<Organization | null> {
  const [org] = await db
    .select({
      org: organizations,
    })
    .from(organizations)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(eq(organizations.slug, teamSlug))
    .limit(1);

  return org?.org || null;
}

/**
 * Creates a new team and assigns caller as OWNER.
 */
export async function createTeam(user: User, name: string): Promise<Organization> {
  const baseSlug = generateSlug(name);
  let slug = baseSlug;

  const [existing] = await db
    .select()
    .from(organizations)
    .where(eq(organizations.slug, slug))
    .limit(1);

  if (existing) {
    slug = `${baseSlug}-${Math.random().toString(36).substring(2, 6)}`;
  }

  const [newOrg] = await db
    .insert(organizations)
    .values({
      name: name.trim(),
      slug,
    })
    .returning();

  if (!newOrg) {
    throw new Error("Failed to create organization");
  }

  await db.insert(organizationMembers).values({
    organizationId: newOrg.id,
    userId: user.id,
    role: "OWNER",
  });

  return newOrg;
}

/**
 * Fetches all projects for a team with repository count and latest build status.
 */
export async function getTeamProjectsWithMetadata(organizationId: string) {
  const teamProjects = await db
    .select()
    .from(projects)
    .where(eq(projects.organizationId, organizationId))
    .orderBy(desc(projects.updatedAt));

  const results = [];
  for (const proj of teamProjects) {
    // Count active connected repositories
    const repos = await db
      .select()
      .from(connectedRepositories)
      .where(
        and(
          eq(connectedRepositories.projectId, proj.id),
          eq(connectedRepositories.isActive, true)
        )
      );

    // Get latest build/index job
    const [latestBuild] = await db
      .select()
      .from(indexJobs)
      .where(eq(indexJobs.projectId, proj.id))
      .orderBy(desc(indexJobs.createdAt))
      .limit(1);

    results.push({
      ...proj,
      repositoryCount: repos.length,
      repositories: repos,
      latestBuild: latestBuild || null,
      status: latestBuild?.status === "RUNNING" ? "BUILDING" : latestBuild?.status === "COMPLETED" ? "READY" : "IDLE",
    });
  }

  return results;
}

/**
 * Creates a new project in a team.
 */
export async function createTeamProject(
  organizationId: string,
  name: string,
  description?: string
): Promise<Project> {
  const baseSlug = generateSlug(name);
  let slug = baseSlug;

  const [existing] = await db
    .select()
    .from(projects)
    .where(eq(projects.slug, slug))
    .limit(1);

  if (existing) {
    slug = `${baseSlug}-${Math.random().toString(36).substring(2, 6)}`;
  }

  const [newProject] = await db
    .insert(projects)
    .values({
      organizationId,
      name: name.trim(),
      slug,
      description: description?.trim() || "",
    })
    .returning();

  if (!newProject) {
    throw new Error("Failed to create project");
  }

  return newProject;
}

/**
 * Updates a team's name and/or slug. Only allowed for OWNER.
 */
export async function updateTeam(
  user: User,
  teamSlug: string,
  updates: { name?: string; slug?: string }
): Promise<Organization> {
  const [membership] = await db
    .select({
      org: organizations,
      role: organizationMembers.role,
    })
    .from(organizations)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(eq(organizations.slug, teamSlug))
    .limit(1);

  if (!membership) {
    throw new Error("Team not found or access denied");
  }

  if (membership.role !== "OWNER") {
    throw new Error("Only team owners can update team settings");
  }

  const setValues: Partial<typeof organizations.$inferInsert> = {};

  if (updates.name && updates.name.trim()) {
    setValues.name = updates.name.trim();
  }

  if (updates.slug && updates.slug.trim()) {
    const nextSlug = generateSlug(updates.slug);
    if (nextSlug !== membership.org.slug) {
      const [existing] = await db
        .select()
        .from(organizations)
        .where(eq(organizations.slug, nextSlug))
        .limit(1);

      if (existing) {
        throw new Error(`Team slug "${nextSlug}" is already taken`);
      }
      setValues.slug = nextSlug;
    }
  }

  if (Object.keys(setValues).length === 0) {
    return membership.org;
  }

  const [updated] = await db
    .update(organizations)
    .set(setValues)
    .where(eq(organizations.id, membership.org.id))
    .returning();

  if (!updated) {
    throw new Error("Failed to update organization");
  }

  return updated;
}

/**
 * Deletes a team, its projects, and memberships.
 */
export async function deleteTeam(user: User, teamSlug: string): Promise<boolean> {
  const [membership] = await db
    .select({
      org: organizations,
      role: organizationMembers.role,
    })
    .from(organizations)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(eq(organizations.slug, teamSlug))
    .limit(1);

  if (!membership) {
    throw new Error("Team not found or access denied");
  }

  if (membership.role !== "OWNER") {
    throw new Error("Only team owners can delete a team");
  }

  const orgId = membership.org.id;

  // Find all projects in this organization
  const orgProjects = await db
    .select()
    .from(projects)
    .where(eq(projects.organizationId, orgId));

  for (const p of orgProjects) {
    // Disassociate connected repositories
    await db
      .update(connectedRepositories)
      .set({ projectId: null })
      .where(eq(connectedRepositories.projectId, p.id));

    // Delete index jobs for project
    await db.delete(indexJobs).where(eq(indexJobs.projectId, p.id));
  }

  // Delete all projects under organization
  await db.delete(projects).where(eq(projects.organizationId, orgId));

  // Delete organization members
  await db.delete(organizationMembers).where(eq(organizationMembers.organizationId, orgId));

  // Delete organization
  await db.delete(organizations).where(eq(organizations.id, orgId));

  // If this was the user's only team, ensure personal team exists
  await getUserTeams(user);

  return true;
}

/**
 * Returns all members of a team.
 */
export async function getTeamMembers(user: User, teamSlug: string) {
  const team = await getTeamBySlug(user, teamSlug);
  if (!team) {
    throw new Error("Team not found or access denied");
  }

  const members = await db
    .select({
      id: organizationMembers.id,
      organizationId: organizationMembers.organizationId,
      userId: organizationMembers.userId,
      role: organizationMembers.role,
      createdAt: organizationMembers.createdAt,
      user: {
        id: users.id,
        username: users.username,
        email: users.email,
        avatarUrl: users.avatarUrl,
      },
    })
    .from(organizationMembers)
    .innerJoin(users, eq(organizationMembers.userId, users.id))
    .where(eq(organizationMembers.organizationId, team.id));

  return members;
}

/**
 * Adds a new member to a team by username or email.
 */
export async function addTeamMember(
  user: User,
  teamSlug: string,
  usernameOrEmail: string,
  role: string = "MEMBER"
) {
  const team = await getTeamBySlug(user, teamSlug);
  if (!team) {
    throw new Error("Team not found or access denied");
  }

  const normalized = usernameOrEmail.trim().toLowerCase();

  // Find target user
  const [targetUser] = await db
    .select()
    .from(users)
    .where(
      or(
        sql`lower(${users.username}) = ${normalized}`,
        sql`lower(${users.email}) = ${normalized}`
      )
    )
    .limit(1);

  if (!targetUser) {
    throw new Error(`User "${usernameOrEmail}" not found in GitAmi`);
  }

  // Check if already a member
  const [existing] = await db
    .select()
    .from(organizationMembers)
    .where(
      and(
        eq(organizationMembers.organizationId, team.id),
        eq(organizationMembers.userId, targetUser.id)
      )
    )
    .limit(1);

  if (existing) {
    throw new Error(`User "${targetUser.username}" is already a member of this team`);
  }

  const validRole = ["OWNER", "MEMBER", "VIEWER"].includes(role.toUpperCase())
    ? role.toUpperCase()
    : "MEMBER";

  const [newMember] = await db
    .insert(organizationMembers)
    .values({
      organizationId: team.id,
      userId: targetUser.id,
      role: validRole,
    })
    .returning();

  return {
    ...newMember,
    user: {
      id: targetUser.id,
      username: targetUser.username,
      email: targetUser.email,
      avatarUrl: targetUser.avatarUrl,
    },
  };
}

/**
 * Updates a team member's role.
 */
export async function updateTeamMemberRole(
  user: User,
  teamSlug: string,
  memberId: string,
  role: string
) {
  const [callerMembership] = await db
    .select({
      org: organizations,
      role: organizationMembers.role,
    })
    .from(organizations)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(eq(organizations.slug, teamSlug))
    .limit(1);

  if (!callerMembership || callerMembership.role !== "OWNER") {
    throw new Error("Only team owners can update member roles");
  }

  const validRole = ["OWNER", "MEMBER", "VIEWER"].includes(role.toUpperCase())
    ? role.toUpperCase()
    : "MEMBER";

  const [updated] = await db
    .update(organizationMembers)
    .set({ role: validRole })
    .where(
      and(
        eq(organizationMembers.id, memberId),
        eq(organizationMembers.organizationId, callerMembership.org.id)
      )
    )
    .returning();

  if (!updated) {
    throw new Error("Member not found");
  }

  return updated;
}

/**
 * Removes a member from a team.
 */
export async function removeTeamMember(
  user: User,
  teamSlug: string,
  memberId: string
) {
  const [callerMembership] = await db
    .select({
      org: organizations,
      role: organizationMembers.role,
    })
    .from(organizations)
    .innerJoin(
      organizationMembers,
      and(
        eq(organizationMembers.organizationId, organizations.id),
        eq(organizationMembers.userId, user.id)
      )
    )
    .where(eq(organizations.slug, teamSlug))
    .limit(1);

  if (!callerMembership) {
    throw new Error("Team not found or access denied");
  }

  const [targetMember] = await db
    .select()
    .from(organizationMembers)
    .where(
      and(
        eq(organizationMembers.id, memberId),
        eq(organizationMembers.organizationId, callerMembership.org.id)
      )
    )
    .limit(1);

  if (!targetMember) {
    throw new Error("Member not found");
  }

  // Caller must be OWNER, or caller is removing themselves
  const isSelf = targetMember.userId === user.id;
  if (!isSelf && callerMembership.role !== "OWNER") {
    throw new Error("Only team owners can remove members");
  }

  // If target is an OWNER, ensure there is at least one other OWNER remaining
  if (targetMember.role === "OWNER") {
    const owners = await db
      .select()
      .from(organizationMembers)
      .where(
        and(
          eq(organizationMembers.organizationId, callerMembership.org.id),
          eq(organizationMembers.role, "OWNER")
        )
      );

    if (owners.length <= 1) {
      throw new Error("Cannot remove the only team owner");
    }
  }

  await db
    .delete(organizationMembers)
    .where(eq(organizationMembers.id, memberId));

  return true;
}

