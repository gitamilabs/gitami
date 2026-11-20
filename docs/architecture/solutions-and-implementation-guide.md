# Gitami Solutions and Architectural Implementation Guide

> **Document Version:** 1.0.0  
> **Status:** Architecture Reference & Implementation Specification  
> **Target Systems:** `apps/ai` (Python Intelligence Worker), `apps/api` (Bun Control Plane), Neo4j Graph DB, ChromaDB Vector DB, PostgreSQL  
> **Audience:** Core System Architects, Staff Engineers, Infrastructure Engineers  

---

## Executive Summary & System Overview

Gitami combines a Bun/Hono control plane (`apps/api`) with a FastAPI Python intelligence worker (`apps/ai`), backed by a Neo4j knowledge graph, a ChromaDB vector store, and a PostgreSQL database. 

A thorough architectural audit of the codebase revealed 6 critical engineering bottlenecks, race conditions, and security gaps across the boundary between the control plane and intelligence engine:

1. **Remote Incremental Indexing Engine:** Incremental indexing (`run_incremental` in `apps/ai/src/indexer/pipeline.py`) strictly assumes an on-disk Git clone (`git.Repo`), while remote GitHub repos are streamed into memory as full tarballs (`stream_and_parse_github_repo` in `apps/ai/src/repo/streamer.py`). PR webhook merge events either fall back to expensive full re-indexes or fail due to unauthenticated requests.
2. **Durable Task Dispatcher & Heartbeat Worker:** Background operations (indexing builds, PR reviews) execute as unmanaged in-memory promises (`executeBackgroundBuild(...).catch(...)` in `apps/api/src/modules/projects/projects.service.ts` and `evaluatePRWithAIService(...).catch(...)` in `apps/api/src/modules/github/webhook.service.ts`). Process restarts or scale-downs permanently orphan jobs in `RUNNING` status without heartbeats or retry leases.
3. **Consolidation of PR Review & Remediation:** The public PR endpoints in `apps/ai/src/web/routes/pr.py` call legacy prototype scripts (`src/agents/reviewer.py` and `src/agents/fixer.py`), leaving the curated `ReviewAgent` (with security linting, blast radius analysis, test gap detection, and Claude Code export) and `CodeAgent` (with two-stage approval and test synthesis) completely orphaned.
4. **Governed Context Retrieval via `ContextEngine`:** The ReAct chat agent loop (`apps/ai/src/agents/agent_loop.py`) and chat SSE route (`apps/ai/src/web/routes/chat.py`) bypass `ContextEngine` (`apps/ai/src/context/engine.py`), instead duplicating a 170-line dispatch ladder that invokes raw MCP tools without deduplication, ranking, token budgeting, or provenance validation.
5. **Call-Graph Precision & Database Connection Pooling:** Neo4j `upsert_call_edges` in `apps/ai/src/graph/writer.py` matches callers to every symbol sharing `callee.name` repository-wide, creating false call-graph edges that corrupt blast radius computations. MCP tools churn new `Neo4jClient` connections per function call, and unit tests hang when Neo4j is offline.
6. **API Gateway & Multi-Tenant Intelligence Seam:** The intelligence router (`apps/api/src/modules/intelligence/intelligence.routes.ts`) imports `authMiddleware` but never mounts it, exposing AI and prompt-editing endpoints unauthenticated, defaulting missing tenant scopes to `"default"`, and lacking signed internal service-to-service communication.

```
+----------------------------------------------------------------------------------------------------+
|                                    CONTROL PLANE (apps/api - Bun)                                  |
|                                                                                                    |
|  +-------------------------+     +-------------------------------+     +------------------------+  |
|  | GitHub Webhook Service  |     |  Durable Task Worker Loop     |     | Intelligence Gateway   |  |
|  | (HMAC verified,         | --> |  (FOR UPDATE SKIP LOCKED,     | --> | (AuthMiddleware,       |  |
|  |  Idempotency dedupe)    |     |   Heartbeats, Lease Recovery) |     |  Tenant Verification)  |  |
|  +-------------------------+     +-------------------------------+     +------------------------+  |
|               |                                  |                                  |              |
|               v                                  v                                  v              |
|      [PostgreSQL Store]                  [Internal RPC /                    [Signed Internal Auth] |
|   (Tasks, Leases, Projects)                HTTP Stream]                             |              |
+--------------------------------------------------|----------------------------------|--------------+
                                                   |                                  |
                                                   v                                  v
+----------------------------------------------------------------------------------------------------+
|                                INTELLIGENCE ENGINE (apps/ai - FastAPI)                             |
|                                                                                                    |
|  +--------------------------------+  +-------------------------------+  +-----------------------+  |
|  | Remote Incremental Indexer     |  | Curated PR Review & Fix       |  | Governed Retrieval    |  |
|  | (GitHub Compare API Differ,    |  | (ReviewAgent + CodeAgent,     |  | (ContextEngine,       |  |
|  |  Remote Snapshot Provider)     |  |  Two-Stage Approval & Patch)  |  |  Dedup, Rank, Budget) |  |
|  +--------------------------------+  +-------------------------------+  +-----------------------+  |
|               |                                  |                                  |              |
|               +----------------------------------+----------------------------------+              |
|                                                  |                                                 |
|                                                  v                                                 |
|                                  +-------------------------------+                                 |
|                                  | Neo4j Connection Pool         |                                 |
|                                  | (Scoped Imports Call Graph)   |                                 |
|                                  +-------------------------------+                                 |
|                                      |                       |                                     |
|                                      v                       v                                     |
|                                 [Neo4j Graph]        [ChromaDB Vector KB]                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 1. Unified Repository Ingestion & Remote Incremental Indexing Engine

### 1.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/ai/src/indexer/pipeline.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/indexer/pipeline.py#L43-L125) (lines 43–125 `run`, lines 396–690 `run_incremental`)
- [`apps/ai/src/jobs/init_job.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/jobs/init_job.py#L38-L95) (lines 38–95)
- [`apps/ai/src/web/routes/ingest.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/ingest.py#L21-L118) (lines 21–118 `/ingest`, lines 179–278 `/reindex`)
- [`apps/ai/src/repo/streamer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/repo/streamer.py#L50-L129) (lines 50–129)
- [`apps/api/src/modules/github/webhook.service.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/github/webhook.service.ts#L309-L345) (lines 309–345)

#### The Root Cause
1. **Disk Invariant in `run_incremental`:** In [`pipeline.py#L398`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/indexer/pipeline.py#L398), `run_incremental` takes `repo_dir: str | Path`. In line 427 and line 691, it opens `with RepositorySnapshot(repo_dir, ...) as snapshot:`. In line 538, it calls `self.differ.compute_diff(repo_dir, ...)`. In line 544, it instantiates `git.Repo(repo_dir)`. In lines 729 and 810, it reads file bytes from disk: `snapshot.read_bytes(cf.path)`.
2. **Memory Tarball Stream Bypasses Incremental Logic:** In [`routes/ingest.py#L235-L253`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/ingest.py#L235-L253), when `target_full_name` is present without a local `repo_dir` (the standard for GitHub App installations), `/api/reindex` completely ignores `base_commit_sha`. It downloads the entire repository archive into memory via `stream_and_parse_github_repo` and triggers a full `run(...)`, throwing away existing graph relationships.
3. **Control Plane Unauthenticated Trigger:** In [`webhook.service.ts#L327-L342`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/github/webhook.service.ts#L327-L342), when a PR merges, the webhook calls `/api/reindex` with `base_commit_sha` and `target_commit_sha`, but **fails to pass `access_token`**. Consequently, `stream_and_parse_github_repo` runs unauthenticated, triggering GitHub 403 rate limits or 404s for private repositories.

### 1.2 Technical Architecture & Solution

We implement a zero-disk, remote incremental indexing architecture that abstracts snapshotting and diff computation into decoupled providers.

```
       +-------------------------------------------------------------+
       | GitHub Push / PR Merge Webhook (base_sha -> target_sha)     |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       | GitHub Compare API (GET /repos/{repo}/compare/{base}...{head}|
       +-------------------------------------------------------------+
                                      |
                      +---------------+---------------+
                      | Status == 'ahead'             | Status == 'diverged'
                      | Changed files <= threshold    | or files > threshold
                      v                               v
       +------------------------------+  +---------------------------+
       | Remote Incremental Indexing  |  | Fallback to Full Reindex  |
       +------------------------------+  +---------------------------+
         1. Selective File Streaming:
            Fetch only added/modified files (GitHub Contents API raw)
         2. Targeted AST Parse:
            Parse AST only for changed files
         3. Neo4j Graph Mutation:
            - Delete removed/renamed old symbols
            - Reconcile modified symbols
            - Rewire affected callers (find_affected_files)
         4. Vector KB Sync:
            - Purge embeddings for deleted files
            - Upsert embeddings for added/modified files
         5. Atomic Commit Roll-Forward:
            UPDATE Repository SET indexed_commit_sha = target_sha
```

#### A. The Remote Diff Provider Interface
Abstract `GitDiffer` behind an abstract base class `IDiffProvider`:

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from src.indexer.contracts import DiffResult, ChangedFile

class IDiffProvider(ABC):
    @abstractmethod
    async def compute_diff(
        self,
        base_commit_sha: str,
        target_commit_sha: str,
    ) -> DiffResult:
        """Computes categorized changed files between two commits."""
        pass
```

Implement `GitHubApiDiffer`:
```python
import httpx
from src.indexer.contracts import ChangedFile, ChangedFileType, DiffResult

class GitHubApiDiffer(IDiffProvider):
    def __init__(self, full_name: str, token: Optional[str] = None):
        self.full_name = full_name
        self.token = token
        self.base_url = f"https://api.github.com/repos/{full_name}"

    async def compute_diff(self, base_commit_sha: str, target_commit_sha: str) -> DiffResult:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Gitami-Incremental-Indexer",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        url = f"{self.base_url}/compare/{base_commit_sha}...{target_commit_sha}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return DiffResult(
                    base_commit_sha=base_commit_sha,
                    target_commit_sha=target_commit_sha,
                    is_ancestor=False,
                    is_safe_incremental=False,
                    fallback_reason=f"GitHub Compare API error: HTTP {resp.status_code}",
                )
            data = resp.json()

        # Ancestry check: 'ahead' confirms target directly extends base
        status = data.get("status")  # ahead, behind, diverged, identical
        if status not in ("ahead", "identical"):
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=False,
                is_safe_incremental=False,
                fallback_reason=f"Git ancestry invariant violated: commit status is '{status}'",
            )

        changed_files: List[ChangedFile] = []
        for f in data.get("files", []):
            gh_status = f.get("status")
            filename = f.get("filename")
            old_name = f.get("previous_filename")

            if gh_status == "added":
                changed_files.append(ChangedFile(path=filename, change_type=ChangedFileType.ADDED))
            elif gh_status == "modified":
                changed_files.append(ChangedFile(path=filename, change_type=ChangedFileType.MODIFIED))
            elif gh_status == "removed":
                changed_files.append(ChangedFile(path=filename, change_type=ChangedFileType.DELETED))
            elif gh_status == "renamed":
                changed_files.append(ChangedFile(path=filename, change_type=ChangedFileType.RENAMED, old_path=old_name))

        # Safe threshold check: > 50% change or > 250 files triggers safe full reindex
        total_changed = len(changed_files)
        is_safe = total_changed <= 250

        return DiffResult(
            base_commit_sha=base_commit_sha,
            target_commit_sha=target_commit_sha,
            is_ancestor=True,
            is_safe_incremental=is_safe,
            changed_files=changed_files,
            fallback_reason=None if is_safe else f"Too many files changed ({total_changed} > 250)",
        )
```

#### B. The Zero-Disk Snapshot Provider Interface
Abstract `RepositorySnapshot` into `ISnapshotProvider`:

```python
class ISnapshotProvider(ABC):
    @abstractmethod
    async def read_bytes(self, relative_path: str) -> bytes:
        pass

    @abstractmethod
    async def read_text(self, relative_path: str) -> str:
        pass
```

Implement `RemoteGitHubSnapshot`:
```python
class RemoteGitHubSnapshot(ISnapshotProvider):
    def __init__(self, full_name: str, commit_sha: str, token: Optional[str] = None):
        self.full_name = full_name
        self.commit_sha = commit_sha
        self.token = token
        self._cache: dict[str, bytes] = {}

    async def read_bytes(self, relative_path: str) -> bytes:
        if relative_path in self._cache:
            return self._cache[relative_path]

        url = f"https://api.github.com/repos/{self.full_name}/contents/{relative_path}?ref={self.commit_sha}"
        headers = {
            "Accept": "application/vnd.github.v3.raw",
            "User-Agent": "Gitami-Incremental-Indexer",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise FileNotFoundError(f"Failed to fetch {relative_path} at {self.commit_sha} (HTTP {resp.status_code})")
            content = resp.content
            self._cache[relative_path] = content
            return content

    async def read_text(self, relative_path: str) -> str:
        b = await self.read_bytes(relative_path)
        return b.decode("utf-8", errors="replace")
```

#### C. Affected Caller Rewiring Strategy
When a function signature or export changes in modified files:
1. `affected_files = await graph_indexer.find_affected_files(repo_id, changed_file_paths)`
2. Query Neo4j for inbound `[:CALLS]` and `[:IMPORTS]` edges to identify external files calling modified symbols.
3. For remote repositories, `RemoteGitHubSnapshot` fetches only the content for `affected_files` (typically 3–8 files), parses them into ASTs, and invokes `rewire_affected_relationships` without re-parsing the rest of the repository.

#### D. Control Plane Webhook Service Update
Update [`apps/api/src/modules/github/webhook.service.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/github/webhook.service.ts#L327-L342):
```typescript
if (isMerged && isRepoIngested(repo.full_name, ingestedNames)) {
  console.log(`🔄 PR #${pr.number} merged into ${repo.full_name}. Triggering incremental reindexing...`);
  
  // Resolve GitHub App installation token
  const [owner, name] = repo.full_name.split("/");
  const token = await getInstallationTokenForRepo(owner, name);
  
  const aiServiceUrl = process.env.AI_SERVICE_URL || env.AI_SERVICE_URL || "http://localhost:8000";
  fetch(`${aiServiceUrl}/api/reindex`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_id: repo.full_name,
      full_name: repo.full_name,
      base_commit_sha: baseSha,
      target_commit_sha: headSha,
      branch: pr.base?.ref || "main",
      access_token: token,
      force_full: false,
    }),
  }).catch((err) => {
    console.error(`Failed to trigger incremental reindex for ${repo.full_name}:`, err);
  });
}
```

---

## 2. Durable Task Dispatcher & Heartbeat Worker in Control Plane

### 2.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/api/src/modules/projects/projects.service.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/projects/projects.service.ts#L334-L358) (lines 334–358 `startProjectBuild`, lines 363–549 `executeBackgroundBuild`)
- [`apps/api/src/modules/builds/builds.routes.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/builds/builds.routes.ts#L16-L105) (lines 16–105)
- [`apps/api/src/modules/github/webhook.service.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/github/webhook.service.ts#L431-L436) (lines 431–436)
- [`apps/api/src/db/schema/index_jobs.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/db/schema/index_jobs.ts#L11-L27) (lines 11–27)

#### The Root Cause
1. **Fire-and-Forget In-Memory Promises:**
   - In [`projects.service.ts#L353`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/projects/projects.service.ts#L353):
     `executeBackgroundBuild(job.id, repo, targetBranch).catch(...)`
   - In [`webhook.service.ts#L433`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/github/webhook.service.ts#L433):
     `evaluatePRWithAIService(prRecord.id).catch(...)`
   - These promises run detached in the Node/Bun event loop of the web server process.
2. **Permanent Stuck State on Crashes/Restarts:** When a deployment occurs, a pod crashes, or a container is restarted:
   - All active in-memory promises die immediately.
   - The PostgreSQL row in `index_jobs` remains permanently frozen in `status = 'RUNNING'`, `stage = 'AST_ANALYSIS'`.
   - The frontend UI displays an infinite loading spinner for that build.
3. **Missing Schema Invariants:**
   - [`index_jobs.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/db/schema/index_jobs.ts#L11-L27) lacks lease columns: `locked_by`, `locked_at`, `heartbeat_at`, `lease_expires_at`, `attempts`, `max_attempts`, `idempotency_key`.
   - There is no mechanism to detect when a worker process has died or to reclaim abandoned tasks.

### 2.2 Technical Architecture & Solution

We implement a transactional queue on PostgreSQL using `SELECT ... FOR UPDATE SKIP LOCKED` with cooperative lease heartbeats.

```
       +--------------------------------------------------------------+
       | Webhook / API Request: Insert Task (Idempotency Key Checked) |
       | Status: 'QUEUED', Attempts: 0, MaxAttempts: 3                |
       +--------------------------------------------------------------+
                                      |
                                      v
       +--------------------------------------------------------------+
       | Worker Loop Poll (SELECT ... FOR UPDATE SKIP LOCKED)         |
       | Claims available QUEUED jobs or expired RUNNING leases       |
       +--------------------------------------------------------------+
                                      |
                         +------------+------------+
                         | Lock Acquired           |
                         v                         v
       +---------------------------------+   +-------------------------+
       | Job Execution Worker Thread     |   | Heartbeat Timer (15s)   |
       | (Consumes NDJSON AI Stream)     |   | UPDATE lease_expires_at |
       +---------------------------------+   | = NOW() + 45s           |
                         |                   +-------------------------+
                         |                                 |
                         +---------------------------------+
                                      |
                      +---------------+---------------+
                      | Success                       | Crash / Exception
                      v                               v
       +-----------------------------+  +------------------------------+
       | Status = 'COMPLETED'        |  | If attempts < max_attempts:  |
       | Release lock & lease        |  |   Status = 'QUEUED', backoff |
       +-----------------------------+  | Else:                        |
                                        |   Status = 'FAILED', err log |
                                        +------------------------------+
```

#### A. Database Schema Enhancement
Update [`apps/api/src/db/schema/index_jobs.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/db/schema/index_jobs.ts):

```typescript
import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  timestamp,
  jsonb,
  uniqueIndex,
} from "drizzle-orm/pg-core";

export const indexJobs = pgTable(
  "index_jobs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    projectId: varchar("project_id", { length: 128 }).notNull().default("default"),
    repositoryId: varchar("repository_id", { length: 255 }).notNull(),
    type: varchar("type", { length: 32 }).notNull().default("INITIAL"),
    baseCommitSha: varchar("base_commit_sha", { length: 128 }),
    targetCommitSha: varchar("target_commit_sha", { length: 128 }).notNull(),
    branch: varchar("branch", { length: 255 }).notNull().default("main"),
    status: varchar("status", { length: 32 }).notNull().default("QUEUED"),
    progress: integer("progress").notNull().default(0),
    stage: varchar("stage", { length: 64 }).notNull().default("PENDING"),
    stats: jsonb("stats").$type<Record<string, unknown>>().default({}),
    error: text("error"),
    
    // Durable Worker Lease Columns
    lockedBy: varchar("locked_by", { length: 128 }),
    lockedAt: timestamp("locked_at", { withTimezone: true }),
    heartbeatAt: timestamp("heartbeat_at", { withTimezone: true }),
    leaseExpiresAt: timestamp("lease_expires_at", { withTimezone: true }),
    attempts: integer("attempts").notNull().default(0),
    maxAttempts: integer("max_attempts").notNull().default(3),
    scheduledAt: timestamp("scheduled_at", { withTimezone: true }).defaultNow(),
    idempotencyKey: varchar("idempotency_key", { length: 255 }),

    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
  },
  (table) => ({
    idempotencyIdx: uniqueIndex("idx_index_jobs_idempotency").on(table.idempotencyKey),
  })
);
```

#### B. SQL Claim Query with `FOR UPDATE SKIP LOCKED`
Worker claim query implemented in the control plane:

```sql
UPDATE index_jobs
SET status = 'RUNNING',
    locked_by = :workerId,
    locked_at = NOW(),
    heartbeat_at = NOW(),
    lease_expires_at = NOW() + INTERVAL '45 seconds',
    attempts = attempts + 1,
    started_at = COALESCE(started_at, NOW())
WHERE id = (
  SELECT id FROM index_jobs
  WHERE (status = 'QUEUED' AND (scheduled_at IS NULL OR scheduled_at <= NOW()))
     OR (status = 'RUNNING' AND lease_expires_at < NOW() AND attempts < max_attempts)
  ORDER BY createdAt ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
RETURNING *;
```

#### C. Worker Implementation Specification
Create `apps/api/src/modules/jobs/job-worker.ts`:

```typescript
import { db } from "../../db";
import { indexJobs } from "../../db/schema";
import { eq, sql } from "drizzle-orm";
import os from "os";

export class DurableJobWorker {
  private workerId: string;
  private isRunning: boolean = false;
  private pollIntervalMs: number = 2500;

  constructor() {
    this.workerId = `${os.hostname()}-${process.pid}-${Math.random().toString(36).slice(2, 7)}`;
  }

  public start() {
    this.isRunning = true;
    this.pollLoop().catch((err) => console.error("Worker loop fatal error:", err));
  }

  public stop() {
    this.isRunning = false;
  }

  private async pollLoop() {
    while (this.isRunning) {
      try {
        const claimedJob = await this.claimNextJob();
        if (claimedJob) {
          await this.processJobWithHeartbeat(claimedJob);
        } else {
          await new Promise((r) => setTimeout(r, this.pollIntervalMs));
        }
      } catch (err) {
        console.error("Error in job worker poll iteration:", err);
        await new Promise((r) => setTimeout(r, this.pollIntervalMs));
      }
    }
  }

  private async claimNextJob() {
    const rows = await db.execute(sql`
      UPDATE index_jobs
      SET status = 'RUNNING',
          locked_by = ${this.workerId},
          locked_at = NOW(),
          heartbeat_at = NOW(),
          lease_expires_at = NOW() + INTERVAL '45 seconds',
          attempts = attempts + 1,
          started_at = COALESCE(started_at, NOW())
      WHERE id = (
        SELECT id FROM index_jobs
        WHERE (status = 'QUEUED' AND (scheduled_at IS NULL OR scheduled_at <= NOW()))
           OR (status = 'RUNNING' AND lease_expires_at < NOW() AND attempts < max_attempts)
        ORDER BY created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
      )
      RETURNING *;
    `);
    return rows[0] || null;
  }

  private async processJobWithHeartbeat(job: any) {
    const heartbeatTimer = setInterval(async () => {
      try {
        await db
          .update(indexJobs)
          .set({
            heartbeatAt: new Date(),
            leaseExpiresAt: new Date(Date.now() + 45000),
          })
          .where(eq(indexJobs.id, job.id));
      } catch (err) {
        console.warn(`Heartbeat update failed for job ${job.id}:`, err);
      }
    }, 15000);

    try {
      // Execute the build streaming logic
      await this.runBuildExecution(job);

      clearInterval(heartbeatTimer);
      await db
        .update(indexJobs)
        .set({
          status: "COMPLETED",
          progress: 100,
          completedAt: new Date(),
          lockedBy: null,
        })
        .where(eq(indexJobs.id, job.id));
    } catch (err: any) {
      clearInterval(heartbeatTimer);
      console.error(`Execution failed for job ${job.id}:`, err);

      const nextAttempt = job.attempts;
      if (nextAttempt < job.max_attempts) {
        const backoffSeconds = Math.pow(2, nextAttempt) * 15; // 30s, 60s, 120s
        await db
          .update(indexJobs)
          .set({
            status: "QUEUED",
            scheduledAt: new Date(Date.now() + backoffSeconds * 1000),
            error: `Attempt ${nextAttempt} failed: ${err.message}. Retrying in ${backoffSeconds}s`,
            lockedBy: null,
          })
          .where(eq(indexJobs.id, job.id));
      } else {
        await db
          .update(indexJobs)
          .set({
            status: "FAILED",
            error: `Max retry attempts (${job.max_attempts}) exhausted: ${err.message}`,
            completedAt: new Date(),
            lockedBy: null,
          })
          .where(eq(indexJobs.id, job.id));
      }
    }
  }

  private async runBuildExecution(job: any) {
    // Delegates to AI service streaming NDJSON parser
  }
}
```

---

## 3. Consolidation of PR Review & Remediation (Retiring Prototypes)

### 3.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/ai/src/agents/reviewer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/reviewer.py#L24-L72) (lines 24–72)
- [`apps/ai/src/agents/review_agent.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/review_agent.py#L76-L344) (lines 76–344)
- [`apps/ai/src/agents/fixer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/fixer.py#L28-L100) (lines 28–100)
- [`apps/ai/src/agents/code_agent.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/code_agent.py#L73-L211) (lines 73–211)
- [`apps/ai/src/web/routes/pr.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/pr.py#L1-L91) (lines 1–91)
- [`apps/api/src/modules/pr/pr.service.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/pr/pr.service.ts#L351-L510) (lines 351–510)

#### The Disconnect
1. **Orphaned Curated Agents:**
   - [`routes/pr.py#L3-L5`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/pr.py#L3-L5) imports:
     ```python
     from src.agents.fixer import run_autonomous_pr_fixer
     from src.agents.reviewer import run_agentic_pr_review
     ```
   - These are initial early-stage prototype scripts that lack security heuristics and structured reporting.
   - Meanwhile, `ReviewAgent` ([`review_agent.py#L76`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/review_agent.py#L76)) and `CodeAgent` ([`code_agent.py#L73`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/code_agent.py#L73)) were built with advanced capabilities but are not wired to any HTTP endpoints:
     - `ReviewAgent` features AST blast radius mapping, convention rule enforcement, security anti-pattern scanning (SQLi, eval, hardcoded secrets), test coverage gap detection, AI-code smell detection, and Claude Code export formatting.
     - `CodeAgent` features two-stage surgical planning, test reproduction synthesis, and unified diff generation.
2. **Data Contract Inconsistencies:**
   - `ReviewAgent.run()` returns a `ReviewResult` containing `checklist: List[ChecklistItem]`.
   - `pr.service.ts` expects `data.issues` with fields `{ title, description, category, severity, file_path, line, suggested_fix }`.
   - `reviewer.py` returns `issues: List[Dict]`.
   - In remediation, `pr.service.ts` expects `/api/pr/fix` to return `file_fixes: [{ file_path, content }]`. `fixer.py` satisfies this partially, while `CodeAgent` returns `patch_diff` and `reproduction_test_code`.

### 3.2 Technical Architecture & Solution

We deprecate and sunset the prototypes, routing all traffic through `ReviewAgent` and `CodeAgent` with dual data-contract compatibility.

```
       +-----------------------------------------------------------+
       | POST /api/pr/review                                       |
       +-----------------------------------------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       | ReviewAgent (apps/ai/src/agents/review_agent.py)          |
       |  - parse_git_diff -> DiffHunks                            |
       |  - Neo4j Blast Radius (affected callers)                  |
       |  - Security Rule Engine (Credentials, Eval, SQLi)         |
       |  - Test Gap Detector (logic modified without test changes)|
       |  - AI-Code Smells (TODO stubs, empty swallow catches)     |
       |  - Deterministic Risk Score (0-100)                       |
       |  - Claude Code Markdown Export                            |
       +-----------------------------------------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       | Unified ReviewResponse:                                   |
       |  { verdict, risk_score, summary, issues, checklist,       |
       |    blast_radius, claude_code_export, changed_files }      |
       +-----------------------------------------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       | POST /api/pr/fix                                          |
       +-----------------------------------------------------------+
                                     |
                     +---------------+---------------+
                     | Two-Stage Mode                | Direct Surgical Mode
                     v                               v
       +---------------------------+   +---------------------------+
       | Stage 1: /api/pr/fix/plan |   | CodeAgent Direct Exec     |
       |  - FixPlan JSON           |   |  - Synthesize test code   |
       |  - Maintainer Approval    |   |  - Generate patch diff    |
       | Stage 2: /api/pr/fix/exec |   |  - Return 'file_fixes'    |
       |  - Test + Patch Synthesized|   |    for pr.service.ts      |
       +---------------------------+   +---------------------------+
```

#### A. Harmonized Data Contracts

Update `ReviewResult.to_dict()` in [`apps/ai/src/agents/review_agent.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/review_agent.py#L48-L74) to guarantee dual backward/forward compatibility:

```python
def to_dict(self) -> Dict[str, Any]:
    serialized_items = [
        {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "severity": item.severity,
            "file_path": item.file_path,
            "line": item.line,
            "suggested_fix": item.suggested_fix,
        }
        for item in self.checklist
    ]
    return {
        "repo_id": self.repo_id,
        "pr_number": self.pr_number,
        "risk_score": self.risk_score,
        "verdict": self.verdict,
        "summary": self.summary,
        "agent_rationale": self.summary,
        "checklist": serialized_items,
        # Backward compatibility alias for pr.service.ts
        "issues": serialized_items,
        "blast_radius": self.blast_radius,
        "changed_files": self.changed_files,
        "changed_symbols": self.changed_symbols,
        "claude_code_export": self.claude_code_export,
        "latency_ms": self.latency_ms,
    }
```

#### B. Updated PR Routes Specification
Rewrite [`apps/ai/src/web/routes/pr.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/pr.py):

```python
from fastapi import APIRouter, HTTPException
from src.agents.review_agent import ReviewAgent
from src.agents.code_agent import CodeAgent, FixPlan
from src.agents.llm_client import DualLLMClient
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import PRFixRequest, PRReviewRequest

router = APIRouter(prefix="/api/pr", tags=["PR Intelligence"])

@router.post("/review")
async def review_pull_request(req: PRReviewRequest):
    # Guardrail: Prevent AI Fix recursive feedback loops
    if req.head_branch.startswith("ai-fix/") or req.title.lower().startswith("[ai fix]"):
        return {
            "verdict": "APPROVE",
            "risk_score": 0,
            "summary": "Skipped review for AI Fix Agent PR to prevent recursive feedback loop.",
            "agent_rationale": "Self-review guardrail triggered.",
            "issues": [],
            "checklist": [],
            "status": "skipped_ai_fix",
        }

    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    llm_client = DualLLMClient()

    agent = ReviewAgent(
        graph_client=graph_client,
        vector_client=vector_client,
        llm_client=llm_client,
    )

    result = await agent.run(
        repo_id=req.repo_id,
        pr_number=req.pr_number or 0,
        base_branch=req.base_branch or "main",
        head_branch=req.head_branch,
        title=req.title,
        body=req.body or "",
        diff_text=req.diff_text or "",
    )

    return result.to_dict()

@router.post("/fix")
async def fix_pull_request_issues(req: PRFixRequest):
    """
    Surgical code remediation endpoint backed by CodeAgent.
    Applies minimal changes and returns 'file_fixes' for direct PR creation.
    """
    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    llm_client = DualLLMClient()

    agent = CodeAgent(
        graph_client=graph_client,
        vector_client=vector_client,
        llm_client=llm_client,
    )

    # 1. Synthesize plan
    issue_desc = "\n".join(
        f"- [{i.get('severity')}] {i.get('title')}: {i.get('description')} (File: {i.get('file_path')}:{i.get('line')})"
        for i in req.issues
    )
    plan = await agent.generate_fix_plan(
        repo_id=req.repo_id,
        issue_title=f"Fix {len(req.issues)} review findings for PR #{req.pr_number}",
        issue_description=issue_desc,
        trigger_source="review",
        affected_files=list({i.get("file_path") for i in req.issues if i.get("file_path")}),
        branch=req.base_branch or "main",
    )

    # 2. Execute plan against real file contents
    exec_res = await agent.execute_approved_plan(
        plan=plan,
        existing_file_contents=req.existing_file_contents or {},
    )

    # Transform patch into file_fixes for control plane GitHub committing
    file_fixes = []
    for fp, original_content in (req.existing_file_contents or {}).items():
        if fp in plan.files_to_touch:
            file_fixes.append({
                "file_path": fp,
                "content": exec_res.apply_patch_or_full(fp, original_content),
            })

    return {
        "success": exec_res.status != "failed",
        "plan_rationale": plan.approach,
        "plan": plan.to_dict(),
        "reproduction_test_code": exec_res.reproduction_test_code,
        "patch_diff": exec_res.patch_diff,
        "file_fixes": file_fixes,
        "error": None,
    }
```

#### C. Prototype Sunsetting Checklist
1. Add `@deprecated` warning decorators to `apps/ai/src/agents/reviewer.py` and `apps/ai/src/agents/fixer.py`.
2. Delete unused prompt references in `apps/ai/src/prompts/` tied solely to the older reviewer.
3. Remove test imports pointing to `src.agents.reviewer` and replace them with `src.agents.review_agent`.

---

## 4. Governed Context Retrieval via ContextEngine

### 4.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/ai/src/context/engine.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/context/engine.py#L52-L253) (lines 52–253)
- [`apps/ai/src/web/routes/chat.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/chat.py#L28-L240) (lines 28–240)
- [`apps/ai/src/agents/agent_loop.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/agent_loop.py#L68-L104) (lines 68–104 pre-fetch, lines 201–250 tool dispatch)
- [`apps/ai/src/mcp/tools.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/mcp/tools.py#L380-L452) (lines 380–452)
- [`apps/ai/src/mcp/server.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/mcp/server.py#L33-L103) (lines 33–103)

#### The Architectural Bypass
1. **The 170-Line Ladder in `chat.py`:**
   In [`apps/ai/src/web/routes/chat.py#L69-L240`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/chat.py#L69-L240), `_execute_single_tool` manually parses tool calls and branches across 8 `if/elif` blocks (`vector_search`, `hybrid_search`, `get_blast_radius`, `get_repo_structure`, `get_symbol_details`, `get_file_dependencies`, `search_symbols`).
   It manually extracts arbitrary strings (`text[:300]`) and fabricates raw citation dictionaries without ranking, without token budgeting, and without deduplication.
2. **ContextEngine Neglect in `agent_loop.py`:**
   In [`apps/ai/src/agents/agent_loop.py#L68-L104`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/agent_loop.py#L68-L104), `ContextEngine` is queried once as a cosmetic pre-fetch, and then completely bypassed during the actual ReAct loop in favor of `execute_tool_by_name`.
3. **Loss of Guarantees:**
   Because calls bypass `ContextEngine`:
   - Authorization boundaries ([`ContextAuthorizer`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/context/authorization.py#L74)) are not enforced.
   - Cross-provider duplicates between Neo4j graph nodes and ChromaDB vector chunks are returned twice to the LLM.
   - Context windows blow past token budgets.
   - Provenance metadata (`commit_sha`, exact start/end lines) is dropped.

### 4.2 Technical Architecture & Solution

We unify all chat, agent reasoning, and MCP tool retrieval behind `ContextEngine.retrieve(ContextRequest)`.

```
       +--------------------------------------------------------------+
       | Incoming Query / ReAct Agent Tool Call                       |
       +--------------------------------------------------------------+
                                      |
                                      v
       +--------------------------------------------------------------+
       | ContextEngine.retrieve(ContextRequest)                       |
       +--------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         | Intent Classification                                   |
         | (call_graph, test, dependency, symbol_lookup, semantic) |
         | Authorization Validation (ContextAuthorizer)            |
         +---------------------------------------------------------+
                                      |
                   +------------------+------------------+
                   | Parallel Provider Retrieval         |
                   | (Graph, Semantic, Source, GitHub)   |
                   +-------------------------------------+
                                      |
                                      v
         +---------------------------------------------------------+
         | ProviderAwareDeduplicator                               |
         | Merges graph nodes + vector chunks sharing entity UIDs  |
         +---------------------------------------------------------+
                                      |
                                      v
         +---------------------------------------------------------+
         | DeterministicRanker (TF-IDF + Graph Centrality Scoring) |
         +---------------------------------------------------------+
                                      |
                                      v
         +---------------------------------------------------------+
         | ContextBudgeter (Max Tokens: 4000, Max Items: 10)       |
         +---------------------------------------------------------+
                                      |
                                      v
         +---------------------------------------------------------+
         | Provenance Validation (ContextItem.source)              |
         +---------------------------------------------------------+
                                      |
                                      v
       +--------------------------------------------------------------+
       | Normalized Citations & ToolStep Emitted to SSE Stream        |
       +--------------------------------------------------------------+
```

#### A. Refactoring ReAct Agent Tool Execution
Refactor [`apps/ai/src/agents/agent_loop.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/agents/agent_loop.py#L201-L240):

```python
async def execute_governed_tool(
    engine: ContextEngine,
    tool_name: str,
    tool_args: Dict[str, Any],
    repo_id: str,
    branch: str,
    project_id: str,
) -> tuple[str, List[Dict[str, Any]]]:
    """Executes retrieval governed by ContextEngine with deduplication and token budgeting."""
    query = (
        tool_args.get("query")
        or tool_args.get("query_str")
        or tool_args.get("name")
        or tool_args.get("qualified_name")
        or ""
    )

    req = ContextRequest(
        project_id=project_id,
        query=query,
        repository_ids=[repo_id],
        branch=branch,
        max_items=8,
        max_tokens=2500,
        include_graph=tool_name in ("hybrid_search", "get_symbol_details", "get_repo_structure", "search_symbols", "context_engine"),
        include_semantic=tool_name in ("hybrid_search", "vector_search", "context_engine"),
        include_source=True,
        include_github=False,
    )

    result = await engine.retrieve(req)

    # Format synthesized markdown payload for LLM reasoning observation
    lines = [f"Retrieved {len(result.items)} governed items for '{query}' (intent: {result.retrieval_metadata.query_intent}):"]
    citations = []

    for idx, item in enumerate(result.items, start=1):
        lines.append(f"\n--- Item {idx}: [{item.type.value}] {item.title} ({item.source.file_path or 'codebase'}) ---")
        lines.append(item.content)

        if item.source.file_path:
            citations.append({
                "id": idx,
                "file_path": item.source.file_path,
                "symbol": item.title,
                "lines": f"{item.source.start_line}-{item.source.end_line}" if item.source.start_line else None,
                "snippet": item.content[:300],
                "source_type": item.source.provider,
            })

    output_summary = f"Retrieved {len(result.items)} items across {', '.join(result.retrieval_metadata.candidates_per_provider.keys())}."
    return "\n".join(lines), citations, output_summary
```

#### B. Eliminating Duplicated Dispatch in `routes/chat.py`
In `apps/ai/src/web/routes/chat.py`, delete the 170-line `_execute_single_tool` function and replace it with:

```python
async def _execute_governed_single_tool(
    step_idx: int,
    call: Dict[str, Any],
    req: ChatRequest,
    engine: ContextEngine,
) -> tuple[ToolStep, List[Dict[str, Any]]]:
    t_name = call.get("tool_name", "context_engine")
    t_args = call.get("args", {})
    t_start = time.perf_counter()

    observation, citations, summary = await execute_governed_tool(
        engine=engine,
        tool_name=t_name,
        tool_args=t_args,
        repo_id=req.repo_id,
        branch=req.branch or "main",
        project_id=req.project_id or req.repo_id,
    )

    t_latency = round((time.perf_counter() - t_start) * 1000.0, 2)
    step = ToolStep(
        step_id=f"step_{step_idx}_{t_name}",
        step_index=step_idx,
        tool_name=t_name,
        title=t_name.replace("_", " ").title(),
        status="completed",
        args=t_args,
        summary=summary,
        latency_ms=t_latency,
        raw_output={"content": observation[:2000]},
    )
    return step, citations
```

---

## 5. Knowledge Graph Call-Graph Precision & Database Connection Pooling

### 5.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/ai/src/graph/writer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/graph/writer.py#L71-L98) (lines 71–98 `upsert_call_edges`)
- [`apps/ai/src/graph/client.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/graph/client.py#L10-L89) (lines 10–89 `Neo4jClient`)
- [`apps/ai/src/graph/resolver.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/graph/resolver.py#L76-L142) (lines 76–142 `resolve_repo_imports`)
- [`apps/ai/src/mcp/server.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/mcp/server.py#L33-L103) (lines 33–103)
- [`apps/ai/tests/unit/test_mcp_tools.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/tests/unit/test_mcp_tools.py#L19-L69) (lines 19–69)

#### The False Call Edge Catastrophe
Look at lines 78–85 in [`apps/ai/src/graph/writer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/graph/writer.py#L78-L85):
```cypher
UNWIND $batch AS item
MATCH (caller:Symbol {repo_id: $repo_id, branch: $branch, qualified_name: item.caller_symbol})
MATCH (callee:Symbol {repo_id: $repo_id, branch: $branch})
WHERE callee.name = item.callee_name
MERGE (caller)-[r:CALLS]->(callee)
SET r.file_path = item.file_path, r.line = item.line
```

**Why this breaks:**
- The query matches `callee:Symbol` **purely by bare name** (`callee.name = item.callee_name`) without scoping to the caller's file or imports.
- In any realistic codebase, common symbol names such as `parse`, `validate`, `render`, `init`, `log`, `handle`, and `build` exist in dozens of files.
- If 30 files declare a `validate` function, a call to `validate()` inside `src/auth/login.ts` creates a `[:CALLS]` edge to **all 30 `validate` functions repository-wide**.
- When computing blast radius (`downstream_affected_symbols`), traversing `-[:CALLS*1..3]->` causes false positives that span the entire codebase.

#### Driver Churn in MCP Server & Destructive Ingestion Closes
- In [`apps/ai/src/mcp/server.py#L33-L103`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/mcp/server.py#L33-L103), every tool method (`get_repo_structure`, `get_symbol_details`, `get_blast_radius`, `get_file_dependencies`, `search_symbols`) contains:
  ```python
  client = Neo4jClient()
  await client.connect()
  try: ...
  finally: await client.close()
  ```
  This creates an `AsyncGraphDatabase.driver` on every single request, performing TCP handshakes, TLS negotiation, and cluster routing discovery, introducing 100ms+ overhead and risking socket exhaustion.
- In [`apps/ai/src/web/routes/ingest.py#L106`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/routes/ingest.py#L106), the worker finally block executes `await graph_client.close()`. Because `graph_client` was obtained from `get_shared_graph_client()`, the shared driver is closed after the first ingestion finishes, causing subsequent requests to fail with closed driver exceptions.

#### Test Suite Offline Hangs
In [`apps/ai/tests/unit/test_mcp_tools.py#L19-L69`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/tests/unit/test_mcp_tools.py#L19-L69), tests marked as unit tests instantiate real `Neo4jClient`s and attempt to connect to `bolt://localhost:7687`. When Neo4j is offline, the client retries 3 times with exponential backoff (10s connection timeout per attempt), hanging CI or local test runs for over 60 seconds before failing.

### 5.2 Technical Architecture & Solution

#### A. Scoped Call Graph Resolution
Call resolution must be scoped using a two-tier rule:
1. **Local File Scope:** If `callee_name` is declared in the same file as `caller_symbol`, connect exclusively to that file's symbol.
2. **Import Scope:** If `callee_name` is imported from another file (tracked via `File -[:IMPORTS]-> Symbol`), connect exclusively to the imported symbol.
3. **Unresolved:** If `callee_name` is not in the local file or imports, do not create a speculative `[:CALLS]` edge to random symbols across the repository.

Update `upsert_call_edges` in [`apps/ai/src/graph/writer.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/graph/writer.py#L71-L98):

```cypher
UNWIND $batch AS item
MATCH (caller:Symbol {repo_id: $repo_id, branch: $branch, qualified_name: item.caller_symbol})
MATCH (callerFile:File {repo_id: $repo_id, branch: $branch, file_path: item.file_path})

// Rule 1: Callee in same file
OPTIONAL MATCH (callerFile)-[:DEFINES]->(localCallee:Symbol {repo_id: $repo_id, branch: $branch, name: item.callee_name})

// Rule 2: Callee imported into caller file
OPTIONAL MATCH (callerFile)-[:IMPORTS]->(importedCallee:Symbol {repo_id: $repo_id, branch: $branch, name: item.callee_name})

WITH caller, item, coalesce(localCallee, importedCallee) AS resolvedCallee
WHERE resolvedCallee IS NOT NULL

MERGE (caller)-[r:CALLS]->(resolvedCallee)
SET r.file_path = item.file_path, r.line = item.line
```

#### B. Connection Pooling & FastMCP Lifespan Context
1. In `apps/ai/src/mcp/server.py`, consume the shared client initialized in `app_lifespan`:

```python
@mcp_server.tool()
async def get_symbol_details(repo_id: str, qualified_name: str, branch: str = "main", ctx: Context = None) -> str:
    """Get detailed symbol metadata, docstrings, callers, and callees using the pooled driver."""
    client = ctx.request_context.lifespan_context["client"]
    return await tool_get_symbol_details(client, repo_id=repo_id, qualified_name=qualified_name, branch=branch)
```

2. In `apps/ai/src/web/routes/ingest.py`, remove line 106 (`await graph_client.close()`). The shared client driver lifecycle belongs solely to the application lifespan in [`apps/ai/src/web/app.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/web/app.py#L38-L42).

#### C. In-Memory Graph Adapter for Unit Testing
Implement `InMemoryGraphAdapter` in `apps/ai/src/graph/mock_client.py`:

```python
from typing import Any, Dict, List, Optional

class InMemoryGraphAdapter:
    """Hermetic in-memory graph adapter for deterministic offline unit testing."""
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def verify_connectivity(self) -> bool:
        return True

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        retries: int = 1,
        timeout: float = 5.0,
    ) -> List[Dict[str, Any]]:
        params = parameters or {}
        # Emulate basic Cypher results for fixtures in test_mcp_tools.py
        if "MATCH (f:File" in query and "RETURN file_path" in query:
            return [{"file_path": "UserService.js", "language": "javascript", "symbols": []}]
        if "MATCH (s:Symbol" in query and "query_str" in params:
            return [{"name": "fetchUsers", "kind": "function", "file_path": "api.js", "signature": "fetchUsers()"}]
        if "downstream" in query or "blast" in query.lower():
            return [{"risk_score": 25, "downstream_affected_symbols": ["UserService.js::getUser"]}]
        return []
```

Update `apps/ai/tests/unit/test_mcp_tools.py` to use `InMemoryGraphAdapter` as default, moving real Neo4j tests to `tests/integration/test_neo4j_live.py` marked with `@pytest.mark.integration`.

---

## 6. API Gateway & Multi-Tenant Intelligence Seam

### 6.1 Codebase Audit & Problem Analysis

Primary sources investigated:
- [`apps/api/src/modules/intelligence/intelligence.routes.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/intelligence/intelligence.routes.ts#L8-L48) (lines 8–48)
- [`apps/api/src/middlewares/auth.middleware.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/middlewares/auth.middleware.ts#L14-L53) (lines 14–53)
- [`apps/api/src/index.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/index.ts#L20-L49) (lines 20–49)
- [`apps/ai/src/context/authorization.py`](file:///home/aryanracha/Coding/projects/gitami/apps/ai/src/context/authorization.py#L74-L143) (lines 74–143)

#### The Security & Tenancy Vulnerabilities
1. **Unmounted Authentication Middleware:**
   In [`intelligence.routes.ts#L8-L12`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/intelligence/intelligence.routes.ts#L8-L12):
   ```typescript
   import { authMiddleware, type AuthContextVariables } from "../../middlewares/auth.middleware";
   const intelligenceRouter = new Hono<{ Variables: AuthContextVariables }>();
   ```
   Unlike `builds.routes.ts` (which mounts `buildsRouter.use("*", authMiddleware);`), `intelligence.routes.ts` **never calls `intelligenceRouter.use("*", authMiddleware);`**.
   Every endpoint under `/api/intelligence/*` (`/chat`, `/chat/stream`, `/investigate`, `/issue/analyze`, `/doc/generate`, `/code/plan`, `/code/execute`, `/prompts`, `/prompts/:key`) is exposed completely unauthenticated.
2. **Multi-Tenancy Breakdown via `enrichPayloadWithTenancy`:**
   In [`intelligence.routes.ts#L16-L49`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/intelligence/intelligence.routes.ts#L16-L49):
   - `c.get("user")` evaluates to `undefined` because no auth middleware ran.
   - The query matches any `connectedRepositories.fullName == enriched.repo_id` without verifying that the requesting user belongs to the project or organization owning that repo.
   - If not found, `project_id` defaults to `"default"`.
   - As a result, cross-tenant isolation in Neo4j and Vector KB collapses completely.
3. **No Service-to-Service Trust Boundary:**
   The Python AI service on port 8000 has no authentication middleware. Any container or process on the private network can submit queries or delete indexed codebases without verification.
4. **No Circuit Breaking:**
   When the AI service is saturated or restarting, client requests to `/chat/stream` block until Bun's default socket timeout triggers, degrading the entire web server.

### 6.2 Technical Architecture & Solution

```
    [Client Browser]
           |  (Bearer UserSessionJWT)
           v
+-------------------------------------------------------------------+
| Bun API Gateway (apps/api)                                        |
|                                                                   |
| 1. authMiddleware:                                                |
|    Verify user session JWT -> attach c.set('user', user)          |
| 2. Tenant Verification:                                           |
|    Verify user membership in project.organizationId               |
| 3. Circuit Breaker Guard:                                         |
|    If failureRate > 50% over 10s -> Short-circuit with HTTP 503   |
| 4. Internal Token Signer:                                         |
|    Generate HMAC-SHA256 signature with shared INTERNAL_API_SECRET |
|    Header: X-Gitami-Internal-Auth: Bearer <signature>.<timestamp> |
+-------------------------------------------------------------------+
                                   |
                     (Signed Internal HTTP Request)
                                   v
+-------------------------------------------------------------------+
| FastAPI Intelligence Service (apps/ai)                            |
|                                                                   |
| 1. InternalAuthMiddleware:                                        |
|    Verify HMAC-SHA256 signature against INTERNAL_API_SECRET       |
|    Reject direct unsigned requests (HTTP 401)                     |
| 2. ContextAuthorizer:                                             |
|    Enforce Project -> Repository isolation                        |
+-------------------------------------------------------------------+
```

#### A. Gateway Hardening in `intelligence.routes.ts`
Update [`apps/api/src/modules/intelligence/intelligence.routes.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/intelligence/intelligence.routes.ts):

```typescript
import { Hono } from "hono";
import { authMiddleware, type AuthContextVariables } from "../../middlewares/auth.middleware";
import { getProjectForUser } from "../projects/projects.service";
import { signInternalServiceToken } from "../../utils/internal-auth";
import { aiCircuitBreaker } from "../../utils/circuit-breaker";

const intelligenceRouter = new Hono<{ Variables: AuthContextVariables }>();

// 1. Mount mandatory authentication on all intelligence routes
intelligenceRouter.use("*", authMiddleware);

// 2. Strict tenancy verification
async function verifyAndEnrichTenancy(c: any, body: any): Promise<any> {
  const user = c.get("user");
  const enriched = { ...body };

  const targetRepoId = enriched.repo_id;
  if (!targetRepoId) {
    throw new Error("Missing required field: repo_id");
  }

  // Look up repository and verify access
  const [repo] = await db
    .select({
      projectId: connectedRepositories.projectId,
      userId: connectedRepositories.userId,
      rootDirectory: connectedRepositories.rootDirectory,
    })
    .from(connectedRepositories)
    .where(eq(connectedRepositories.fullName, targetRepoId))
    .limit(1);

  if (!repo || !repo.projectId) {
    throw new Error(`Repository '${targetRepoId}' is not connected to any valid project`);
  }

  // Verify that the authenticated user belongs to the project
  const projectAccess = await getProjectForUser(user, repo.projectId);
  if (!projectAccess) {
    throw new Error(`Forbidden: User does not have access to repository '${targetRepoId}'`);
  }

  enriched.project_id = repo.projectId;
  enriched.team_id = projectAccess.organization.id;
  enriched.user_id = user.id;
  if (repo.rootDirectory) {
    enriched.root_directory = repo.rootDirectory;
  }

  return enriched;
}
```

#### B. Internal Service-to-Service HMAC Signing
Create `apps/api/src/utils/internal-auth.ts`:

```typescript
import { env } from "../configs/env";

export async function signInternalServiceToken(payload: Record<string, unknown>): Promise<string> {
  const secret = env.INTERNAL_API_SECRET || "default-insecure-internal-secret";
  const timestamp = Date.now().toString();
  const rawData = `${timestamp}.${JSON.stringify(payload)}`;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const signatureBuffer = await crypto.subtle.sign("HMAC", key, encoder.encode(rawData));
  const signatureHex = Array.from(new Uint8Array(signatureBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return `${timestamp}.${signatureHex}`;
}
```

#### C. FastAPI Internal Auth Middleware
Implement in `apps/ai/src/web/middleware/internal_auth.py`:

```python
import hmac
import hashlib
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from src.config import settings

class InternalServiceAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow open health checks for container orchestrators
        if request.url.path in ("/api/health", "/health", "/docs", "/openapi.json"):
            return await call_next(request)

        auth_header = request.headers.get("X-Gitami-Internal-Auth")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing internal service authentication token")

        try:
            timestamp_str, signature = auth_header.split(".", 1)
            req_time = int(timestamp_str)
            # Replay protection: max 60s clock drift
            if abs(time.time() * 1000 - req_time) > 60000:
                raise HTTPException(status_code=401, detail="Internal token expired (replay protection)")

            secret = getattr(settings, "internal_api_secret", "default-insecure-internal-secret")
            # Verify HMAC
            expected = hmac.new(
                secret.encode(),
                timestamp_str.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                raise HTTPException(status_code=401, detail="Invalid internal service signature")
        except Exception:
            raise HTTPException(status_code=401, detail="Internal authentication verification failed")

        return await call_next(request)
```

#### D. Circuit Breaker Specification
Create `apps/api/src/utils/circuit-breaker.ts`:

```typescript
export class CircuitBreaker {
  private failureThreshold = 5;
  private recoveryTimeoutMs = 15000;
  private state: "CLOSED" | "OPEN" | "HALF_OPEN" = "CLOSED";
  private failureCount = 0;
  private nextAttempt = 0;

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === "OPEN") {
      if (Date.now() > this.nextAttempt) {
        this.state = "HALF_OPEN";
      } else {
        throw new Error("AI Service Circuit Breaker is OPEN: service temporarily unavailable");
      }
    }

    try {
      const res = await fn();
      if (this.state === "HALF_OPEN") {
        this.state = "CLOSED";
        this.failureCount = 0;
      }
      return res;
    } catch (err) {
      this.failureCount++;
      if (this.failureCount >= this.failureThreshold || this.state === "HALF_OPEN") {
        this.state = "OPEN";
        this.nextAttempt = Date.now() + this.recoveryTimeoutMs;
      }
      throw err;
    }
  }
}

export const aiCircuitBreaker = new CircuitBreaker();
```

---

## 7. Comprehensive Implementation & Migration Plan

### 7.1 Staged Rollout Timeline

```
+-------------------------------------------------------------------------------------------------+
| Stage 1: Security & Stability Foundation (Days 1–3)                                             |
| - Mount authMiddleware in apps/api/src/modules/intelligence/intelligence.routes.ts              |
| - Inject verified tenancy in verifyAndEnrichTenancy                                             |
| - Add InternalServiceAuthMiddleware in FastAPI                                                  |
| - Fix shared Neo4jClient connection close leak in apps/ai/src/web/routes/ingest.py              |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| Stage 2: Database Reliability & Durable Task Worker (Days 4–7)                                   |
| - Apply Drizzle migration for index_jobs lease columns (locked_by, lease_expires_at, attempts)   |
| - Deploy DurableJobWorker loop with SELECT ... FOR UPDATE SKIP LOCKED                           |
| - Replace fire-and-forget executeBackgroundBuild with transactional task enqueue                 |
| - Add idempotency key checks to GitHub webhook events                                           |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| Stage 3: Remote Incremental Indexing Engine (Days 8–11)                                          |
| - Implement GitHubApiDiffer and RemoteGitHubSnapshot in apps/ai/src/indexer/                    |
| - Abstract RepositorySnapshot in pipeline.py to support remote providers                       |
| - Wire GitHub installation access token in webhook.service.ts PR merge event                    |
| - Enable remote incremental path in /api/reindex                                                |
+-------------------------------------------------------------------------------------------------+
                                                |
                                                v
+-------------------------------------------------------------------------------------------------+
| Stage 4: Agent & Retrieval Consolidation (Days 12–15)                                           |
| - Update apps/ai/src/graph/writer.py upsert_call_edges with local file & import scoping         |
| - Replace reviewer.py and fixer.py with ReviewAgent and CodeAgent in routes/pr.py               |
| - Unify routes/chat.py and agent_loop.py onto ContextEngine.retrieve()                          |
| - Add InMemoryGraphAdapter to eliminate unit test offline hangs                                 |
+-------------------------------------------------------------------------------------------------+
```

### 7.2 Verification & Acceptance Matrix

| Issue | Validation Test / Benchmark | Target Metric |
| :--- | :--- | :--- |
| **1. Remote Ingestion** | PR merge webhook simulation on 5,000-file repo | Incremental index completes in < 2.5s with 0 disk writes |
| **2. Durable Tasks** | Kill worker pod during `AST_ANALYSIS` stage | Stale lease reclaimed in < 45s; job retried and completed |
| **3. Agent Consolidation** | Run `/api/pr/review` on synthetic SQLi + test gap diff | Returns `REQUEST_CHANGES`, risk score > 75, Claude Code export generated |
| **4. Governed Retrieval** | Run ReAct chat on multi-symbol ambiguous query | 100% of citations contain start/end lines; 0 duplicate entities |
| **5. Call-Graph Precision** | Index 2 files sharing function name `validate` | Distinct `[:CALLS]` edges scoped to respective files; 0 cross-file false edges |
| **6. Gateway Tenancy** | Send unauthenticated request to `/api/intelligence/chat` | Immediate HTTP 401; authenticated requests across unauthorized project return 403 |

---

## 8. Summary of Files Changed

### `apps/ai` (Python Intelligence Engine)
- `src/indexer/pipeline.py`: Decouple `run_incremental` from local disk paths via `ISnapshotProvider` and `IDiffProvider`.
- `src/indexer/remote_snapshot.py`: New zero-disk `RemoteGitHubSnapshot` using GitHub Contents API.
- `src/indexer/remote_differ.py`: New `GitHubApiDiffer` using GitHub Compare Commits API.
- `src/web/routes/ingest.py`: Remove destructive shared client `close()`; route remote PR reindexes to incremental pipeline.
- `src/web/routes/pr.py`: Replace `reviewer.py` and `fixer.py` with `ReviewAgent` and `CodeAgent`.
- `src/agents/review_agent.py`: Expose dual `issues` and `checklist` keys in `to_dict()`.
- `src/context/engine.py`: Add convenience helper for agent tool retrieval.
- `src/web/routes/chat.py`: Replace 170-line dispatch ladder with `ContextEngine.retrieve()`.
- `src/graph/writer.py`: Update Cypher query in `upsert_call_edges` to scope by local file and imports.
- `src/mcp/server.py`: Use FastMCP lifespan pooled client rather than churning connections.
- `src/graph/mock_client.py`: New `InMemoryGraphAdapter` for offline unit testing.
- `tests/unit/test_mcp_tools.py`: Swap real connection for `InMemoryGraphAdapter`.
- `src/web/middleware/internal_auth.py`: New HMAC service-to-service authentication middleware.

### `apps/api` (Bun Control Plane)
- `src/db/schema/index_jobs.ts`: Add worker lease and retry columns (`locked_by`, `lease_expires_at`, `attempts`, `idempotency_key`).
- `src/modules/jobs/job-worker.ts`: New durable task worker loop implementing `SELECT ... FOR UPDATE SKIP LOCKED`.
- `src/modules/projects/projects.service.ts`: Replace fire-and-forget in-memory promises with transactional job queueing.
- `src/modules/github/webhook.service.ts`: Pass installation tokens in `/api/reindex` and add idempotency deduplication.
- `src/modules/intelligence/intelligence.routes.ts`: Mount `authMiddleware`, verify project access, inject signed internal auth header.
- `src/utils/internal-auth.ts`: New HMAC signer for internal API requests.
- `src/utils/circuit-breaker.ts`: New resilient circuit breaker for AI service calls.
