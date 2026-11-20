import { eq, and } from "drizzle-orm";
import { env } from "../../configs/env";
import { db } from "../../db";
import {
  githubInstallations,
  connectedRepositories,
  pullRequests,
  indexJobs,
} from "../../db/schema";
import { getUserByGithubId } from "../auth/auth.service";
import { evaluatePRWithAIService } from "../pr/pr.service";
import {
  getIngestedRepoNames,
  isRepoIngested,
  getInstallationTokenForRepo,
} from "./github-app.service";


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

async function handleIssuesEvent(
  payload: Record<string, unknown>,
): Promise<{ handled: boolean; action: string }> {
  const action = payload.action as string;
  const issue = payload.issue as {
    number?: number;
    title?: string;
    body?: string;
    user?: { login?: string };
    html_url?: string;
    labels?: Array<{ name: string }>;
  };
  const repo = payload.repository as { full_name?: string };

  console.log(
    `📌 Issue ${action} in ${repo?.full_name}: #${issue?.number} — "${issue?.title}"`,
  );

  // Trigger Issue Agent analysis workflow for newly opened or updated issues
  if (["opened", "edited"].includes(action) && repo?.full_name && issue?.number) {
    const aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";
    fetch(`${aiServiceUrl}/api/issue/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: repo.full_name,
        issue_number: issue.number,
        title: issue.title || "",
        body: issue.body || "",
        author: issue.user?.login || "unknown",
        html_url: issue.html_url || "",
        labels: (issue.labels || []).map((l) => l.name),
      }),
    }).catch((err) => {
      console.warn(`Issue analysis trigger notice for #${issue.number}:`, err);
    });
  }

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
    merged?: boolean;
  };
  const repo = payload.repository as { id?: number; full_name?: string };

  if (!pr || !pr.number || !repo || !repo.full_name) {
    return { handled: false, action: "pr_missing_data" };
  }

  console.log(
    `🔀 PR ${action} in ${repo.full_name}: #${pr.number} — "${pr.title}"`,
  );

  const ingestedNames = await getIngestedRepoNames();

  // Handle PR closed event: update DB status and trigger incremental reindex if merged
  if (action === "closed") {
    const isMerged = Boolean(pr.merged);
    const headSha = pr.head?.sha || "";
    const baseSha = pr.base?.sha || "";

    await db
      .update(pullRequests)
      .set({
        state: "closed",
        status: isMerged ? "merged" : "closed",
      })
      .where(
        and(
          eq(pullRequests.repoFullName, repo.full_name),
          eq(pullRequests.prNumber, pr.number)
        )
      );

    if (isMerged && isRepoIngested(repo.full_name, ingestedNames)) {
      console.log(`🔄 PR #${pr.number} merged into ${repo.full_name}. Triggering tracked incremental reindexing...`);
      const parts = repo.full_name.split("/");
      const owner = parts[0] || "";
      const repoName = parts[1] || "";

      // Lookup connected repository for projectId and rootDirectory
      const [connRepo] = await db
        .select()
        .from(connectedRepositories)
        .where(eq(connectedRepositories.fullName, repo.full_name))
        .limit(1);

      const projectId = connRepo?.projectId || "default";
      const rootDirectory = connRepo?.rootDirectory || undefined;
      const accessToken = (owner && repoName ? await getInstallationTokenForRepo(owner, repoName) : undefined) || undefined;

      // Tracked task persistence (type: INCREMENTAL, status: QUEUED)
      const [jobRecord] = await db
        .insert(indexJobs)
        .values({
          projectId,
          repositoryId: repo.full_name,
          type: "INCREMENTAL",
          baseCommitSha: baseSha,
          targetCommitSha: headSha,
          branch: pr.base?.ref || "main",
          status: "QUEUED",
          stage: "PENDING",
        })
        .returning();

      if (jobRecord) {
        triggerTrackedIncrementalReindex({
          jobId: jobRecord.id,
          repoId: repo.full_name,
          baseSha,
          headSha,
          branch: pr.base?.ref || "main",
          projectId,
          accessToken,
          rootDirectory,
        }).catch((err) => {
          console.error(`Error in tracked incremental reindex for ${repo.full_name}:`, err);
        });
      }
    }

    return { handled: true, action: isMerged ? "pr_closed_merged" : "pr_closed" };
  }

  // We act on opened, synchronize, or reopened PR events
  if (!["opened", "synchronize", "reopened"].includes(action)) {
    return { handled: true, action: `pr_${action}_ignored` };
  }

  // Only process PR events for ingested repositories
  if (!isRepoIngested(repo.full_name, ingestedNames)) {
    console.log(`ℹ️ Skipping PR webhook review for non-ingested repo: ${repo.full_name}`);
    return { handled: true, action: "pr_repo_not_ingested" };
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

export async function triggerTrackedIncrementalReindex(params: {
  jobId: string;
  repoId: string;
  baseSha: string;
  headSha: string;
  branch: string;
  projectId: string;
  accessToken?: string;
  rootDirectory?: string;
}): Promise<void> {
  const { jobId, repoId, baseSha, headSha, branch, projectId, accessToken, rootDirectory } = params;
  const aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";

  await db
    .update(indexJobs)
    .set({
      status: "RUNNING",
      startedAt: new Date(),
      stage: "DIFF",
    })
    .where(eq(indexJobs.id, jobId));

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000); // 10m timeout

  try {
    const res = await fetch(`${aiServiceUrl}/api/reindex`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: repoId,
        full_name: repoId,
        base_commit_sha: baseSha,
        target_commit_sha: headSha,
        branch,
        project_id: projectId,
        access_token: accessToken,
        root_directory: rootDirectory,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const errData = (await res.json().catch(() => ({}))) as any;
      const errorMsg = errData.detail || errData.error || `AI service returned status ${res.status}`;
      await db
        .update(indexJobs)
        .set({
          status: "FAILED",
          error: errorMsg,
          completedAt: new Date(),
        })
        .where(eq(indexJobs.id, jobId));
      return;
    }

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("ndjson") && res.body) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let lastStatus = "RUNNING";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.status) {
              lastStatus = event.status;
            }
            if (event.stage) {
              const isTerminal = event.status === "COMPLETED" || event.status === "FAILED";
              await db
                .update(indexJobs)
                .set({
                  stage: event.stage,
                  stats: event.stats || {},
                  error: event.error || null,
                  status: event.status || "RUNNING",
                  completedAt: isTerminal ? new Date() : undefined,
                })
                .where(eq(indexJobs.id, jobId));
            }
          } catch {
            // ignore malformed line
          }
        }
      }

      if (lastStatus !== "COMPLETED" && lastStatus !== "FAILED") {
        console.warn(`Incremental reindex stream ended unexpectedly for job ${jobId}`);
        await db
          .update(indexJobs)
          .set({
            status: "FAILED",
            error: "Reindex stream disconnected unexpectedly before completion",
            completedAt: new Date(),
          })
          .where(eq(indexJobs.id, jobId));
      }
    } else {
      await db
        .update(indexJobs)
        .set({
          status: "COMPLETED",
          stage: "COMPLETED",
          completedAt: new Date(),
        })
        .where(eq(indexJobs.id, jobId));
    }
  } catch (err: any) {
    clearTimeout(timeoutId);
    console.error(`Incremental reindex execution error for job ${jobId}:`, err);
    const errorMsg =
      err.name === "AbortError"
        ? "Incremental reindexing timed out after 10 minutes"
        : err.message || "Failed to complete incremental reindexing";
    await db
      .update(indexJobs)
      .set({
        status: "FAILED",
        error: errorMsg,
        completedAt: new Date(),
      })
      .where(eq(indexJobs.id, jobId));
  }
}

