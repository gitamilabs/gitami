import { eq, and } from "drizzle-orm";
import { env } from "../../configs/env";
import { db } from "../../db";
import {
  githubInstallations,
  connectedRepositories,
  pullRequests,
} from "../../db/schema";
import { getUserByGithubId } from "../auth/auth.service";
import { evaluatePRWithAIService } from "../pr/pr.service";


export async function verifySignature(
  rawBody: string,
  signature: string,
): Promise<boolean> {
  if (!signature || !signature.startsWith("sha256=")) return false;
  try {
    const expectedSig = signature.substring(7);
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(env.GITHUB_WEBHOOK_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const signatureBuffer = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(rawBody)
    );
    const hashArray = Array.from(new Uint8Array(signatureBuffer));
    const calculatedSig = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
    
    return calculatedSig === expectedSig;
  } catch {
    return false;
  }
}

/**
 * Dispatches a webhook event to the appropriate handler.
 */
export async function handleEvent(
  eventName: string,
  payload: Record<string, unknown>,
): Promise<{ handled: boolean; action?: string }> {
  console.log(
    `📡 Webhook event: ${eventName} (action: ${(payload as { action?: string }).action})`,
  );

  switch (eventName) {
    case "installation":
      return handleInstallationEvent(payload);
    case "installation_repositories":
      return handleInstallationRepositoriesEvent(payload);
    case "issues":
      return handleIssuesEvent(payload);
    case "pull_request":
      return handlePullRequestEvent(payload);
    default:
      return { handled: true, action: "ignored_event_type" };
  }
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

async function handleInstallationEvent(
  payload: Record<string, unknown>,
): Promise<{ handled: boolean; action: string }> {
  const action = payload.action as string;
  const installation = payload.installation as {
    id: number;
    account?: { login: string; id: number };
    target_type?: string;
  };
  const installationId = String(installation.id);

  if (action === "deleted") {
    await db
      .delete(githubInstallations)
      .where(eq(githubInstallations.installationId, installationId));

    console.log(`🗑️ Deleted GitHub Installation: ${installationId}`);
    return { handled: true, action: "installation_deleted" };
  }

  if (action === "created") {
    const sender = payload.sender as { id: number } | undefined;
    const senderGithubId = sender ? String(sender.id) : undefined;
    const user = senderGithubId
      ? await getUserByGithubId(senderGithubId)
      : undefined;

    const [savedInst] = await db
      .insert(githubInstallations)
      .values({
        userId: user?.id ?? "00000000-0000-0000-0000-000000000000",
        installationId,
        accountLogin: installation.account?.login ?? "unknown",
        accountId: installation.account
          ? String(installation.account.id)
          : "0",
        targetType: installation.target_type ?? "User",
      })
      .onConflictDoUpdate({
        target: githubInstallations.installationId,
        set: {
          accountLogin: installation.account?.login ?? "unknown",
          accountId: installation.account
            ? String(installation.account.id)
            : "0",
          targetType: installation.target_type ?? "User",
        },
      })
      .returning();

    // Save initial repositories if provided
    const repositories = payload.repositories as
      | Array<{ id: number; name: string; full_name: string; private: boolean }>
      | undefined;

    if (repositories) {
      for (const repo of repositories) {
        await db
          .insert(connectedRepositories)
          .values({
            installationId: savedInst!.id,
            userId: user?.id ?? "00000000-0000-0000-0000-000000000000",
            githubRepoId: String(repo.id),
            name: repo.name,
            fullName: repo.full_name,
            isPrivate: repo.private,
            htmlUrl: `https://github.com/${repo.full_name}`,
            defaultBranch: "main",
            isActive: true,
          })
          .onConflictDoUpdate({
            target: connectedRepositories.githubRepoId,
            set: {
              name: repo.name,
              fullName: repo.full_name,
              isPrivate: repo.private,
              isActive: true,
            },
          });
      }
    }

    console.log(`✨ Created GitHub Installation: ${installationId}`);
    return { handled: true, action: "installation_created" };
  }

  return { handled: true, action: `installation_${action}` };
}

async function handleInstallationRepositoriesEvent(
  payload: Record<string, unknown>,
): Promise<{ handled: boolean; action: string }> {
  const action = payload.action as string;
  const installation = payload.installation as { id: number };
  const installationId = String(installation.id);

  const [inst] = await db
    .select()
    .from(githubInstallations)
    .where(eq(githubInstallations.installationId, installationId))
    .limit(1);

  if (!inst) {
    return { handled: false, action: "installation_not_found" };
  }

  if (action === "added") {
    const added = payload.repositories_added as
      | Array<{ id: number; name: string; full_name: string; private: boolean }>
      | undefined;

    if (added) {
      for (const repo of added) {
        await db
          .insert(connectedRepositories)
          .values({
            installationId: inst.id,
            userId: inst.userId,
            githubRepoId: String(repo.id),
            name: repo.name,
            fullName: repo.full_name,
            isPrivate: repo.private,
            htmlUrl: `https://github.com/${repo.full_name}`,
            defaultBranch: "main",
            isActive: true,
          })
          .onConflictDoUpdate({
            target: connectedRepositories.githubRepoId,
            set: {
              name: repo.name,
              fullName: repo.full_name,
              isPrivate: repo.private,
              isActive: true,
            },
          });
      }
      console.log(
        `➕ Added ${added.length} repos to installation ${installationId}`,
      );
    }
  }

  if (action === "removed") {
    const removed = payload.repositories_removed as
      | Array<{ id: number }>
      | undefined;

    if (removed) {
      for (const repo of removed) {
        await db
          .update(connectedRepositories)
          .set({ isActive: false })
          .where(
            and(
              eq(connectedRepositories.githubRepoId, String(repo.id)),
              eq(connectedRepositories.userId, inst.userId),
            ),
          );
      }
      console.log(
        `➖ Removed ${removed.length} repos from installation ${installationId}`,
      );
    }
  }

  return { handled: true, action: `repositories_${action}` };
}

function handleIssuesEvent(
  payload: Record<string, unknown>,
): { handled: boolean; action: string } {
  const action = payload.action as string;
  const issue = payload.issue as { number?: number; title?: string };
  const repo = payload.repository as { full_name?: string };

  console.log(
    `📌 Issue ${action} in ${repo?.full_name}: #${issue?.number} — "${issue?.title}"`,
  );

  return { handled: true, action: `issue_${action}` };
}

async function handlePullRequestEvent(
  payload: Record<string, unknown>,
): Promise<{ handled: boolean; action: string }> {
  const action = payload.action as string;
  const pr = payload.pull_request as {
    number?: number;
    title?: string;
    body?: string;
    state?: string;
    html_url?: string;
    base?: { ref?: string; sha?: string };
    head?: { ref?: string; sha?: string };
    user?: { login?: string };
  };
  const repo = payload.repository as { id?: number; full_name?: string };

  if (!pr || !pr.number || !repo || !repo.full_name) {
    return { handled: false, action: "pr_missing_data" };
  }

  console.log(
    `🔀 PR ${action} in ${repo.full_name}: #${pr.number} — "${pr.title}"`,
  );

  // We act on opened, synchronize, or reopened PR events
  if (!["opened", "synchronize", "reopened"].includes(action)) {
    return { handled: true, action: `pr_${action}_ignored` };
  }

  const headBranch = pr.head?.ref || "unknown";
  const baseBranch = pr.base?.ref || "main";
  const title = pr.title || `PR #${pr.number}`;

  // AI Fix Loop Protection Guardrail: Skip PRs generated by AI Fix Agent
  const isAiFixBranch = headBranch.startsWith("ai-fix/");
  const isAiFixTitle = title.toLowerCase().startsWith("[ai fix]");

  let prRecord;
  if (isAiFixBranch || isAiFixTitle) {
    console.log(`🛡️ Skipping review for AI Agent Fix PR: #${pr.number} (${headBranch})`);
    [prRecord] = await db
      .insert(pullRequests)
      .values({
        repoFullName: repo.full_name,
        prNumber: pr.number,
        title,
        body: pr.body || "",
        state: pr.state || "open",
        status: "skipped_ai_fix",
        baseBranch,
        headBranch,
        baseSha: pr.base?.sha || "",
        headSha: pr.head?.sha || "",
        authorLogin: pr.user?.login || "bot",
        htmlUrl: pr.html_url || `https://github.com/${repo.full_name}/pull/${pr.number}`,
      })
      .onConflictDoUpdate({
        target: [pullRequests.repoFullName, pullRequests.prNumber],
        set: {
          title,
          body: pr.body || "",
          state: pr.state || "open",
          status: "skipped_ai_fix",
          headBranch,
          headSha: pr.head?.sha || "",
        },
      })
      .returning();

    return { handled: true, action: "pr_skipped_ai_fix" };
  }

  // Save/upsert standard pull request record in DB
  [prRecord] = await db
    .insert(pullRequests)
    .values({
      repoFullName: repo.full_name,
      prNumber: pr.number,
      title,
      body: pr.body || "",
      state: pr.state || "open",
      status: "pending",
      baseBranch,
      headBranch,
      baseSha: pr.base?.sha || "",
      headSha: pr.head?.sha || "",
      authorLogin: pr.user?.login || "user",
      htmlUrl: pr.html_url || `https://github.com/${repo.full_name}/pull/${pr.number}`,
    })
    .onConflictDoUpdate({
      target: [pullRequests.repoFullName, pullRequests.prNumber],
      set: {
        title,
        body: pr.body || "",
        state: pr.state || "open",
        status: "pending",
        headBranch,
        headSha: pr.head?.sha || "",
      },
    })
    .returning();

  // Async dispatch evaluation so webhook responds immediately to GitHub
  if (prRecord) {
    evaluatePRWithAIService(prRecord.id).catch((err) => {
      console.error(`❌ Background PR evaluation error for PR #${pr.number}:`, err);
    });
  }

  return { handled: true, action: `pr_${action}_evaluating` };
}

