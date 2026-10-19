import { eq, and, desc, inArray } from "drizzle-orm";
import { db } from "../../db";
import {
  pullRequests,
  prReviews,
  prIssues,
  connectedRepositories,
  type PullRequest,
  type PRReview,
  type PRIssue,
} from "../../db/schema";
import { env } from "../../configs/env";
import {
  getInstallationTokenForRepo,
  syncPullRequestsForRepo,
  syncAllConnectedPullRequests,
  getIngestedRepoNames,
  isRepoIngested,
} from "../github/github-app.service";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";

export async function listPullRequests(repoFullName?: string, userId?: string) {
  // Only ever list PRs for repositories the requesting user actually owns —
  // an unauthenticated caller, or a repoFullName they don't own, gets nothing
  // rather than a global dump of every user's pull requests.
  if (!userId) return [];

  const ownedRepos = await db
    .select()
    .from(connectedRepositories)
    .where(eq(connectedRepositories.userId, userId));
  const ownedFullNames = new Set(ownedRepos.map((r) => r.fullName));
  const ownedShortNames = new Map(ownedRepos.map((r) => [r.name, r.fullName]));

  let targetFullName = repoFullName?.trim();

  if (targetFullName && !ownedFullNames.has(targetFullName)) {
    // Allow callers to pass a bare repo name instead of "owner/repo".
    const resolved = ownedShortNames.get(targetFullName);
    targetFullName = resolved;
  }

  if (repoFullName && !targetFullName) {
    // Caller asked for a specific repo they don't own — deny, don't leak.
    return [];
  }

  // Fetch only ingested repository names from Knowledge Base
  const ingestedNames = await getIngestedRepoNames();

  // If a specific repository was requested:
  if (targetFullName) {
    // Only sync and return PRs if this repository is ingested
    if (!isRepoIngested(targetFullName, ingestedNames)) {
      return [];
    }

    try {
      await syncPullRequestsForRepo(targetFullName);
    } catch (err) {
      console.warn("Notice: background PR sync from GitHub encountered an issue:", err);
    }

    const prs = await db
      .select()
      .from(pullRequests)
      .where(eq(pullRequests.repoFullName, targetFullName))
      .orderBy(desc(pullRequests.createdAt));
    return enrichPRsWithReviewData(prs);
  }

  // Listing all PRs for the user: filter owned repositories strictly to ingested ones
  const ingestedOwnedRepos = ownedRepos.filter(
    (r) => isRepoIngested(r.fullName, ingestedNames) || isRepoIngested(r.name, ingestedNames),
  );

  if (ingestedOwnedRepos.length === 0) return [];

  // Sync latest PRs from GitHub in real-time for only ingested repos
  try {
    await syncAllConnectedPullRequests(userId);
  } catch (err) {
    console.warn("Notice: background PR sync from GitHub encountered an issue:", err);
  }

  const ingestedFullNames = Array.from(new Set(ingestedOwnedRepos.map((r) => r.fullName)));

  const prs = await db
    .select()
    .from(pullRequests)
    .where(inArray(pullRequests.repoFullName, ingestedFullNames))
    .orderBy(desc(pullRequests.createdAt));
  return enrichPRsWithReviewData(prs);
}

export async function syncPullRequests(repoFullName?: string, userId?: string) {
  const ingestedNames = await getIngestedRepoNames();

  if (repoFullName) {
    if (isRepoIngested(repoFullName, ingestedNames)) {
      await syncPullRequestsForRepo(repoFullName);
    }
  } else {
    await syncAllConnectedPullRequests(userId);
  }
  return listPullRequests(repoFullName, userId);
}

async function enrichPRsWithReviewData(prs: PullRequest[]) {
  const result = [];
  for (const pr of prs) {
    const [review] = await db
      .select()
      .from(prReviews)
      .where(eq(prReviews.pullRequestId, pr.id))
      .limit(1);

    let issues: PRIssue[] = [];
    if (review) {
      issues = await db
        .select()
        .from(prIssues)
        .where(eq(prIssues.reviewId, review.id));
    }

    result.push({
      ...pr,
      review: review || null,
      issues,
    });
  }
  return result;
}

/**
 * Verifies the given user actually owns (has connected) the repository a
 * PR belongs to — used to gate read/review/fix access to a specific PR so
 * a guessed or leaked PR id can't be used to read or act on someone else's
 * pull request.
 */
export async function userOwnsRepo(userId: string, repoFullName: string): Promise<boolean> {
  const rows = await db
    .select()
    .from(connectedRepositories)
    .where(eq(connectedRepositories.userId, userId));
  return rows.some((r) => r.fullName.toLowerCase() === repoFullName.toLowerCase());
}

export async function getPullRequestDetails(prId: string) {
  const [pr] = await db
    .select()
    .from(pullRequests)
    .where(eq(pullRequests.id, prId))
    .limit(1);

  if (!pr) return null;

  const [review] = await db
    .select()
    .from(prReviews)
    .where(eq(prReviews.pullRequestId, pr.id))
    .limit(1);

  let issues: PRIssue[] = [];
  if (review) {
    issues = await db
      .select()
      .from(prIssues)
      .where(eq(prIssues.reviewId, review.id));
  }

  return {
    ...pr,
    review: review || null,
    issues,
  };
}

/**
 * Fetches PR diff text using authenticated GitHub App installation access.
 * Handles private repositories seamlessly and falls back to public diff URL if necessary.
 */
export async function fetchAuthenticatedPRDiff(
  repoFullName: string,
  prNumber: number
): Promise<string> {
  const [owner, repo] = repoFullName.split("/");
  if (owner && repo) {
    try {
      const token = await getInstallationTokenForRepo(owner, repo);
      const headers: Record<string, string> = {
        "User-Agent": "Gitami-API",
        Accept: "application/vnd.github.v3.diff",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const diffRes = await fetch(
        `https://api.github.com/repos/${repoFullName}/pulls/${prNumber}`,
        { headers }
      );
      if (diffRes.ok) {
        return await diffRes.text();
      }
    } catch (err) {
      console.warn(`Authenticated diff fetch failed for ${repoFullName}#${prNumber}:`, err);
    }
  }

  // Fallback to public diff if token not available or public repo
  try {
    const diffRes = await fetch(`https://github.com/${repoFullName}/pull/${prNumber}.diff`, {
      headers: { "User-Agent": "Gitami-API" },
    });
    if (diffRes.ok) {
      return await diffRes.text();
    }
  } catch (e) {
    console.warn(`Public fallback diff fetch failed for ${repoFullName}#${prNumber}:`, e);
  }

  return "";
}

export async function evaluatePRWithAIService(prId: string) {
  const pr = await getPullRequestDetails(prId);
  if (!pr) throw new Error("PR not found");

  // Ingestion Check: Verify that the repository is indexed in Knowledge Base before running review
  const ingestedNames = await getIngestedRepoNames();
  if (!isRepoIngested(pr.repoFullName, ingestedNames)) {
    throw new Error(
      `Repository "${pr.repoFullName}" has not been ingested into the Knowledge Base yet. Please ingest the repository from the Dashboard first.`,
    );
  }

  // AI Fix PR Guardrail: Check if PR is generated by AI agent
  if (pr.headBranch.startsWith("ai-fix/") || pr.title.toLowerCase().startsWith("[ai fix]")) {
    await db
      .update(pullRequests)
      .set({ status: "skipped_ai_fix" })
      .where(eq(pullRequests.id, prId));

    return {
      status: "skipped_ai_fix",
      reason: "PR was generated by AI Agent fix workflow (ai-fix/* branch). Review skipped to prevent feedback loops.",
    };
  }

  // Fetch GitHub patch diff via authenticated Octokit/REST API
  const diffText = await fetchAuthenticatedPRDiff(pr.repoFullName, pr.prNumber);

  // Call AI Service PR review endpoint
  const response = await fetch(`${AI_SERVICE_URL}/api/pr/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_id: pr.repoFullName,
      pr_number: pr.prNumber,
      base_branch: pr.baseBranch,
      head_branch: pr.headBranch,
      title: pr.title,
      body: pr.body || "",
      diff_text: diffText,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`AI Service review failed: ${errText}`);
  }

  const data = (await response.json()) as any;

  // Save/update review
  const existingReview = pr.review;
  let reviewId: string;

  if (existingReview) {
    reviewId = existingReview.id;
    await db
      .update(prReviews)
      .set({
        verdict: data.verdict || "SUGGEST",
        riskScore: data.risk_score || 0.0,
        summary: data.summary || "Agentic PR review completed.",
        agentRationale: data.agent_rationale || "",
        rawReviewJson: data,
      })
      .where(eq(prReviews.id, reviewId));

    // Delete previous issues for this review before inserting fresh ones
    await db.delete(prIssues).where(eq(prIssues.reviewId, reviewId));
  } else {
    const [newReview] = await db
      .insert(prReviews)
      .values({
        pullRequestId: pr.id,
        verdict: data.verdict || "SUGGEST",
        riskScore: data.risk_score || 0.0,
        summary: data.summary || "Agentic PR review completed.",
        agentRationale: data.agent_rationale || "",
        rawReviewJson: data,
      })
      .returning();
    reviewId = newReview!.id;
  }

  // Insert structured checklist issues
  const issuesList = data.issues || [];
  for (const item of issuesList) {
    await db.insert(prIssues).values({
      reviewId,
      title: item.title || item.description || "PR Code Improvement",
      description: item.description || item.title || "",
      category: item.category || "bug",
      severity: item.severity || "warning",
      filePath: item.file_path || "codebase",
      line: item.line || 1,
      suggestedFix: item.suggested_fix || item.fix_patch || "",
      isFixed: false,
    });
  }

  // Update PR status
  await db
    .update(pullRequests)
    .set({ status: "reviewed" })
    .where(eq(pullRequests.id, pr.id));

  return getPullRequestDetails(pr.id);
}

export async function fixSelectedPRIssues(prId: string, issueIds: string[]) {
  const pr = await getPullRequestDetails(prId);
  if (!pr) throw new Error("PR not found");

  if (!issueIds || issueIds.length === 0) {
    throw new Error("No issues selected for AI fixing");
  }

  // Fetch selected issues
  const selectedIssues = await db
    .select()
    .from(prIssues)
    .where(inArray(prIssues.id, issueIds));

  if (selectedIssues.length === 0) {
    throw new Error("Selected issues not found");
  }

  // Fetch GitHub file contents for each affected file so the AI fixer has the real source
  const githubToken = (process.env.GITHUB_TOKEN || process.env.GITHUB_PAT || env.GITHUB_TOKEN || "").trim();
  const uniqueFilePaths = [...new Set(selectedIssues.map((i) => i.filePath))];
  const existingFileContents: Record<string, string> = {};

  for (const filePath of uniqueFilePaths) {
    try {
      const headers: Record<string, string> = {
        Accept: "application/vnd.github.v3.raw",
        "User-Agent": "Sentinel-AI-Agent",
      };
      if (githubToken) {
        headers.Authorization = `Bearer ${githubToken}`;
      }
      const fileUrl = `https://api.github.com/repos/${pr.repoFullName}/contents/${filePath}?ref=${pr.headBranch}`;
      const fileResp = await fetch(fileUrl, { headers });
      if (fileResp.ok) {
        existingFileContents[filePath] = await fileResp.text();
      }
    } catch (e) {
      console.warn(`⚠️ Could not fetch ${filePath} from GitHub:`, e);
    }
  }

  // Fetch PR diff for context using authenticated GitHub API
  const diffText = await fetchAuthenticatedPRDiff(pr.repoFullName, pr.prNumber);

  // Request AI Service to generate SURGICAL patch fixes for selected issues
  const aiResponse = await fetch(`${AI_SERVICE_URL}/api/pr/fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_id: pr.repoFullName,
      pr_number: pr.prNumber,
      base_branch: pr.headBranch,
      diff_text: diffText.slice(0, 5000),
      existing_file_contents: existingFileContents,
      issues: selectedIssues.map((i) => ({
        id: i.id,
        title: i.title,
        description: i.description,
        file_path: i.filePath,
        line: i.line,
        category: i.category,
        suggested_fix: i.suggestedFix,
      })),
    }),
  });

  if (!aiResponse.ok) {
    const errText = await aiResponse.text();
    throw new Error(`AI Service fix patch generation failed: ${errText}`);
  }

  const fixResult = (await aiResponse.json()) as any;
  const fileFixes: Array<{ file_path: string; content: string }> = fixResult.file_fixes || [];

  if (fileFixes.length === 0) {
    throw new Error("AI Agent did not return any modified file contents");
  }

  const [owner, repoName] = (pr.repoFullName || "").split("/");
  if (!owner || !repoName) {
    throw new Error(`Invalid repository name: ${pr.repoFullName}`);
  }
  const newBranchName = `ai-fix/pr-${pr.prNumber}-${Date.now()}`;
  let fixPrUrl = "";

  // 1. Resolve token: User PAT / OAuth token -> Fallback: GitHub App Installation Token
  let token = (process.env.GITHUB_TOKEN || process.env.GITHUB_PAT || env.GITHUB_TOKEN || "").trim();

  if (!token) {
    const appToken = await getInstallationTokenForRepo(owner, repoName);
    if (appToken) {
      token = appToken;
    }
  }

  if (!token) {
    throw new Error(
      `GitHub Authentication Error: No GITHUB_TOKEN or GitHub App installation found for '${pr.repoFullName}'. Please configure your GitHub OAuth token or install the GitHub App.`,
    );
  }

  // 2. Standard GitHub REST API execution via fetch
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "Sentinel-AI-Fix-Agent",
    "Content-Type": "application/json",
  };

  try {
    // 1. Get base branch SHA
    const refRes = await fetch(
      `https://api.github.com/repos/${pr.repoFullName}/git/ref/heads/${pr.headBranch}`,
      { headers },
    );
    if (!refRes.ok) {
      const refErr = await refRes.text();
      if (refRes.status === 403 || refRes.status === 404) {
        throw new Error(
          `GitHub Permission Denied: Token lacks read/write permissions for '${pr.repoFullName}'.`,
        );
      }
      throw new Error(`Failed to fetch ref for branch '${pr.headBranch}': ${refErr}`);
    }
    const refData = (await refRes.json()) as any;
    const baseSha = refData.object.sha;

    // 2. Create new branch
    const createBranchRes = await fetch(
      `https://api.github.com/repos/${pr.repoFullName}/git/refs`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          ref: `refs/heads/${newBranchName}`,
          sha: baseSha,
        }),
      },
    );
    if (!createBranchRes.ok) {
      const branchErr = await createBranchRes.text();
      if (createBranchRes.status === 403 || createBranchRes.status === 404) {
        throw new Error(
          `GitHub Write Permission Denied: Token does not have permission to push branches to '${pr.repoFullName}'.`,
        );
      }
      throw new Error(`Failed to create branch '${newBranchName}': ${branchErr}`);
    }

    // 3. Commit modified files to new branch
    for (const fileFix of fileFixes) {
      let currentSha: string | undefined = undefined;
      try {
        const fileRes = await fetch(
          `https://api.github.com/repos/${pr.repoFullName}/contents/${fileFix.file_path}?ref=${newBranchName}`,
          { headers },
        );
        if (fileRes.ok) {
          const fileData = (await fileRes.json()) as any;
          currentSha = fileData.sha;
        }
      } catch {
        // File might be new
      }

      const putRes = await fetch(
        `https://api.github.com/repos/${pr.repoFullName}/contents/${fileFix.file_path}`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            message: `fix(ai): resolve automated PR issue in ${fileFix.file_path}`,
            content: Buffer.from(fileFix.content).toString("base64"),
            branch: newBranchName,
            sha: currentSha,
          }),
        },
      );

      if (!putRes.ok) {
        throw new Error(
          `Failed to commit file '${fileFix.file_path}': ${await putRes.text()}`,
        );
      }
    }

    // 4. Create Pull Request
    const prRes = await fetch(
      `https://api.github.com/repos/${pr.repoFullName}/pulls`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          title: `[AI Fix] Resolve ${selectedIssues.length} issue(s) for PR #${pr.prNumber}`,
          head: newBranchName,
          base: pr.headBranch,
          body:
            `🤖 **AI Automated PR Fix**\n\nThis PR was automatically raised by the Sentinel AI Agent to resolve the following selected issues from PR #${pr.prNumber}:\n\n` +
            selectedIssues
              .map((i) => `- **${i.title}** (\`${i.filePath}:${i.line}\`)`)
              .join("\n"),
        }),
      },
    );

    if (!prRes.ok) {
      throw new Error(`Failed to create GitHub Pull Request: ${await prRes.text()}`);
    }

    const prData = (await prRes.json()) as any;
    fixPrUrl = prData.html_url;
  } catch (err: any) {
    console.error("❌ GitHub Token REST API Error:", err);
    throw new Error(`GitHub PR Creation failed: ${err.message || err}`);
  }

  // Mark selected issues as fixed
  for (const issueId of issueIds) {
    await db
      .update(prIssues)
      .set({
        isFixed: true,
        fixPrUrl,
      })
      .where(eq(prIssues.id, issueId));
  }

  return {
    success: true,
    branch: newBranchName,
    fixPrUrl,
    fixedIssuesCount: selectedIssues.length,
  };
}

/**
 * Manually registers a new Pull Request for testing or custom tracking.
 */
export async function createPullRequestManual(
  userId: string,
  data: {
    repoFullName: string;
    prNumber: number;
    title: string;
    body?: string;
    baseBranch?: string;
    headBranch: string;
    htmlUrl?: string;
  }
): Promise<PullRequest> {
  const [repo] = await db
    .select()
    .from(connectedRepositories)
    .where(
      and(
        eq(connectedRepositories.userId, userId),
        eq(connectedRepositories.fullName, data.repoFullName)
      )
    )
    .limit(1);

  const [newPr] = await db
    .insert(pullRequests)
    .values({
      repositoryId: repo?.id || null,
      repoFullName: data.repoFullName,
      prNumber: data.prNumber,
      title: data.title,
      body: data.body || "",
      baseBranch: data.baseBranch || "main",
      headBranch: data.headBranch,
      state: "open",
      status: "pending",
      htmlUrl: data.htmlUrl || `https://github.com/${data.repoFullName}/pull/${data.prNumber}`,
    })
    .returning();

  if (!newPr) {
    throw new Error("Failed to create pull request");
  }

  return newPr;
}

/**
 * Updates a Pull Request's title, body, state (open/closed), or status.
 */
export async function updatePullRequest(
  id: string,
  updates: {
    title?: string;
    body?: string;
    state?: string;
    status?: string;
  }
): Promise<PullRequest | null> {
  const setValues: Partial<typeof pullRequests.$inferInsert> = {};
  if (updates.title) setValues.title = updates.title.trim();
  if (updates.body !== undefined) setValues.body = updates.body;
  if (updates.state) setValues.state = updates.state;
  if (updates.status) setValues.status = updates.status;

  if (Object.keys(setValues).length === 0) {
    const [existing] = await db
      .select()
      .from(pullRequests)
      .where(eq(pullRequests.id, id))
      .limit(1);
    return existing || null;
  }

  const [updated] = await db
    .update(pullRequests)
    .set(setValues)
    .where(eq(pullRequests.id, id))
    .returning();

  return updated || null;
}

/**
 * Deletes a Pull Request record and cascaded reviews/issues.
 */
export async function deletePullRequest(id: string): Promise<boolean> {
  const [deleted] = await db
    .delete(pullRequests)
    .where(eq(pullRequests.id, id))
    .returning();

  return !!deleted;
}

/**
 * Updates an issue in a PR review (e.g. toggle isFixed or update status).
 */
export async function updatePRIssue(
  issueId: string,
  updates: { isFixed?: boolean; title?: string; severity?: string }
): Promise<PRIssue | null> {
  const setValues: Partial<typeof prIssues.$inferInsert> = {};
  if (typeof updates.isFixed === "boolean") setValues.isFixed = updates.isFixed;
  if (updates.title) setValues.title = updates.title.trim();
  if (updates.severity) setValues.severity = updates.severity;

  const [updated] = await db
    .update(prIssues)
    .set(setValues)
    .where(eq(prIssues.id, issueId))
    .returning();

  return updated || null;
}

