# GitAmi — Comprehensive System Audit & Current Implementation Details

> **Date:** October 2026  
> **Status:** Architecture & Implementation Audit  
> **Target Services:** `apps/web` (Next.js 16), `apps/api` (Bun / Hono), `apps/ai` (Python FastAPI / Neo4j / ChromaDB)  
> **Primary Goal:** Evolve GitAmi into a robust codebase management and auditing platform powered by a dual-engine knowledge base (Graph + Vector) and optimized re-indexing.

---

## 1. Executive Summary & Core Mission Alignment

### 1.1 The Core Mission
GitAmi is **not** a generic code generation or autocompletion assistant. It is a **codebase management, auditing, and intelligence platform**. Its primary objective is to empower software maintainers, engineering leads, and developers to:
1. **Audit & Maintain Health:** Continuously track code structural integrity, detect dead code, measure blast radius, and enforce architectural conventions.
2. **Triage & Investigate:** Automatically triage GitHub issues (duplicate detection, criticality scoring, spam filtering) and conduct multi-step root-cause investigations.
3. **Review with Context:** Evaluate pull requests against structural AST call graphs, semantic documentation, and cross-repository contracts with rigorous risk scoring.
4. **Document Intelligently:** Generate domain onboarding guides, architecture logs, and changelogs, keeping them continuously up to date and flagging stale documentation when code changes.
5. **Safely Remediate:** Allow maintainer-approved, test-first remediation inside isolated sandboxes.

### 1.2 The Current Reality
While foundational building blocks (Tree-sitter multi-language AST extraction, Neo4j graph schemas, and ChromaDB vector integrations) are present and unit-tested in isolation, the integrated system is fragmented, inconsistent, and experiences critical failures in production flows:
* **The Frontend (`apps/web`):** Suffers from split routing hierarchies, state management cross-contamination, confusing UX terminology, hidden or incomplete CRUD controls, and direct client-to-AI-service calls that bypass the control plane.
* **The API Service (`apps/api`):** Written as dense, non-modular controller files; performs unauthenticated public diff scraping; lacks durable queue workers; and relies on no-op stubs for crucial features like the Issue Agent.
* **The AI Service (`apps/ai`):** The canonical incremental indexer is completely disconnected from production triggers; initial GitHub indexing accidentally indexes the AI service's own server directory; vector ingestion floods the vector store with unfiltered AST symbols causing document limits to be reached; and the Context Engine is disconnected from chat and agents.

---

## 2. Frontend Deep Analysis (`apps/web`)

### 2.1 Routing Architecture & Layout Inconsistencies

#### Problem 1: Fractured Route Hierarchies
The Next.js App Router contains three conflicting routing paradigms:
1. **The Legacy Single-Repo Routes (`app/(app)/*`):**  
   * Located at `(app)/overview`, `(app)/dashboard`, `(app)/chat`, `(app)/prs`, `(app)/graph`, `(app)/repositories`, `(app)/settings`, `(app)/builds`.  
   * Every single one of these routes renders a client-side `<LegacyRedirect target="..." />` component. When a user lands on or refreshes these pages, the UI renders a spinning loader, fetches teams and projects asynchronously in `useEffect`, and calls `router.replace(...)`.
2. **Duplicate Legacy Project Routes (`app/[teamSlug]/projects/[projectSlug]/*`):**  
   * Complete duplicate directories exist under `[teamSlug]/projects/[projectSlug]/builds`, `chat`, `graph`, `prs`, `repositories`, which simply render server-side `redirect("/${teamSlug}/${projectSlug}/...")`.
3. **The Target Multi-Tenant Routes (`app/[teamSlug]/[projectSlug]/*`):**  
   * The actual active application views live under `[teamSlug]/[projectSlug]/*`.

#### Problem 2: Conflicting Navigation Layouts & Broken Sidebar Links
* **Team Page vs. Project Page:**  
  * `app/[teamSlug]/page.tsx` (the Team Projects overview) renders its own custom inline header without a sidebar.  
  * `app/[teamSlug]/[projectSlug]/layout.tsx` renders `<Sidebar />` and `<TopBar />`.
* **Sidebar Double Slash & Scope Confusion:**  
  * In `Sidebar.tsx`, the project navigation links are computed as:  
    `const effectiveProjectSlug = projectSlug || activeProject?.slug || (projects[0]?.slug ?? "");`  
    `const projectBase = '/${teamSlug}/${effectiveProjectSlug}';`  
  * If a user is on the team level or a team has no projects, `effectiveProjectSlug` is empty, causing links like `/${teamSlug}//repositories` and `/${teamSlug}//graph`. Clicking them leads to 404s or broken state.

---

### 2.2 API Integration & Boundary Violations

#### Problem 1: Dual Base URLs & Missing Control Plane Gateway
In `apps/web/src/lib/api.ts`, two separate base URLs are configured:
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api/v1";
const AI_SERVICE_BASE_URL = process.env.NEXT_PUBLIC_AI_SERVICE_URL || "http://localhost:8000";
```
The browser directly calls `AI_SERVICE_BASE_URL` (port 8000) for:
* `aiApi.getHealth` (`/api/health`)
* `aiApi.getConfig` (`/api/config`)
* `aiApi.getPrompts` & update prompts (`/api/prompts/*`)
* `aiApi.listRepos` (`/api/repos`)
* `aiApi.ingest` (`/api/ingest`)
* `aiApi.chat` & `aiApi.chatStream` (`/api/chat`, `/api/chat/stream`)
* `aiApi.getGraphReport` (`/api/graph-report/*`)

**Consequences:**
1. **Security & Auth Bypass:** Calls to port 8000 carry no user session JWT or tenant authorization headers. Any user can trigger ingestion or query repository graphs.
2. **CORS & Infrastructure Fragility:** In staging or production, port 8000 cannot and should not be exposed to the public internet. All traffic must flow through Bun (`API_BASE_URL`).

---

### 2.3 State Management Spaghetti (Zustand Stores)

`apps/web` contains six separate Zustand stores with overlapping, contradictory responsibilities:

| Store | Files | Major Flaws & Inconsistencies |
| :--- | :--- | :--- |
| **`authStore.ts`** | User session & JWT | Stores token in `localStorage` and cookies. Lacks refresh-token lifecycle. |
| **`teamStore.ts`** | Team list & active team | In-flight request deduplication uses a global module variable `fetchTeamsPromise` outside the store. **Has zero state or methods for Team Members.** |
| **`projectStore.ts`**| Projects & repositories | Manages project CRUD and attached repos. Often gets out of sync with `teamStore` when switching teams. |
| **`repoStore.ts`** | Connected & indexed repos | Uses global module variables `connectedReposInFlight` and `indexedReposInFlight`. Queries global indexed repos instead of project-scoped repos. |
| **`buildStore.ts`** | Indexing jobs ("builds") | Polls and tracks jobs. Uses ambiguous term "Build" instead of "Index Job" or "Knowledge Base Indexing". |
| **`chatStore.ts`** | Chat messages & SSE | Defaults `selectedRepo: ""` without scoping to the current project's repositories. |

#### Specific Bug: PR Reviews Infinite Re-Render Loop
In `apps/web/src/app/[teamSlug]/[projectSlug]/prs/page.tsx`:
```typescript
const loadPRs = useCallback(async () => {
  ...
  if (allFetched.length > 0 && !selectedPR) {
    setSelectedPR(allFetched[0]);
  }
}, [selectedRepoFilter, token, selectedPR]); // <-- selectedPR causes recreation of loadPRs!

useEffect(() => {
  loadPRs();
}, [selectedRepoFilter, loadPRs]); // <-- Triggers infinite re-render loop
```

---

### 2.4 CRUD Operations & UX Gaps

1. **Teams & Organizations:**
   * Creation exists via `CreateTeamModal.tsx`.
   * Editing name/slug and deletion exist in `TeamSettings.tsx`, but are buried in `/[teamSlug]/settings?tab=team`.
   * There is no direct access to team switching or team settings from the main project sidebar without navigating away.
2. **Team Members:**
   * The API functions `getTeamMembers`, `addTeamMember`, `updateTeamMemberRole`, and `deleteTeamMember` are implemented in `lib/api.ts` and `teams.routes.ts`.
   * However, member management is tucked away in the settings tab with zero presence in the main workspace navigation. There is no invitation link generation, user search autocomplete, or avatar error handling.
3. **Projects:**
   * Create/Edit/Delete modals exist (`CreateProjectModal`, `EditProjectModal`, `DeleteProjectModal`).
   * The project overview page does not allow multi-repo aggregation. If a project has 3 repositories, the dashboard only shows a single list without cross-repo dependency insights.
4. **Repositories:**
   * Disconnected modals: `ConnectRepositoryModal`, `AddProjectModal`, `EditRepositoryModal`, and `IngestModal`.
   * Unclear status: Users cannot see which commit SHA is indexed, whether an index is stale, or what caused an indexing error without digging into builds.
   * Confusing terminology: Indexing a codebase is called "Running a Build" in the UI, confusing users into thinking GitAmi is a CI/CD platform like Jenkins or GitHub Actions.

---

## 3. API Service Analysis (`apps/api`)

### 3.1 Non-Modular Monoliths & Technical Debt

The Bun control plane (`apps/api/src/modules/`) is characterized by oversized, non-modular service files:

| File | Lines | Problematic Content |
| :--- | :--- | :--- |
| **`github.routes.ts`** | 592 lines | Mixes GitHub OAuth installation, state token JWT signing, repo listing, repo ingestion, local directory ingestion, and webhook intake in a single file. |
| **`pr.service.ts`** | 662 lines | Mixes raw Drizzle queries, Octokit GitHub API calls, unauthenticated public diff URL scraping, calling AI service, and updating issue checklist rows. |
| **`projects.service.ts`** | 498 lines | Mixes project CRUD with an in-memory background worker `executeBackgroundBuild` that streams NDJSON and updates database rows in a loop. |
| **`webhook.service.ts`** | 373 lines | Contains `handleIssuesEvent` which does nothing except `console.log`. |

### 3.2 Security & Architectural Flaws

#### Flaw 1: Public Diff Scraping Breaks Private Repositories
In `apps/api/src/modules/pr/pr.service.ts` (lines 206–216):
```typescript
const diffRes = await fetch(`https://github.com/${pr.repoFullName}/pull/${pr.prNumber}.diff`, {
  headers: { "User-Agent": "Sentinel-AI-PR-Reviewer" },
});
if (diffRes.ok) {
  diffText = await diffRes.text();
}
```
**Fatal Issue:** This fetches diffs anonymously from public GitHub URLs. For any private repository connected via the GitHub App, this request returns a 404 or redirect to login. PR reviews for private repositories fail or receive empty diffs.

#### Flaw 2: Untracked In-Memory Background Jobs
In `projects.service.ts`:
```typescript
executeBackgroundBuild(job.id, repo, targetBranch).catch((err) => {
  console.error(`Background build execution error for job ${job.id}:`, err);
});
```
When a user triggers an indexing job, Bun kicks off an untracked async promise. If Bun is restarted, crashes, or runs in a serverless/containerized environment, the running job is orphaned. The database record remains in `RUNNING` status indefinitely with no timeout, dead-letter queue, or recovery mechanism.

#### Flaw 3: Leaked AI Service Fallback Webhooks
`apps/ai/src/web/app.py` exposes `@app.post("/webhooks")`, `@app.post("/api/webhooks")`, and `@app.post("/api/github/webhooks")`. According to the architecture specification, Python must **never** receive direct GitHub webhooks and holds no GitHub credentials.

---

## 4. AI Service Deep Analysis (`apps/ai`)

### 4.1 Indexing & Re-Indexing Breakdowns

#### Catastrophic Bug 1: GitHub Tarball Stream Result is Discarded
In `apps/ai/src/web/app.py` (lines 327–341):
```python
if req.full_name:
    parse_results = stream_and_parse_github_repo(
        full_name=req.full_name,
        token=req.access_token,
        branch=req.branch or "main",
    )
    result = await run_init_job(
        repo_id=req.repo_id,
        branch=req.branch or "main",
        parse_results=parse_results,
        client=graph_client,
        vector_client=vector_client,
        ...
    )
```
And in `apps/ai/src/jobs/init_job.py`:
```python
async def run_init_job(
    repo_id: str,
    branch: str,
    repo_dir: Optional[str | Path] = None,
    parse_results: Optional[List[ParseResult]] = None,
    ...
):
    indexer = RepositoryIndexer(...)
    target_dir = Path(repo_dir) if repo_dir else Path(".")
    job, state, report = await indexer.run(
        repo_dir=target_dir,  # <-- Path(".") is the local AI service directory!
        ...
    )
```
**The Bug:** `run_init_job` completely ignores the `parse_results` passed from GitHub! Because `repo_dir` is `None` for remote repositories, it defaults to `Path(".")`. It then walks and indexes `apps/ai` on the host machine instead of the user's repository!

#### Catastrophic Bug 2: Incremental Indexing is Dead Code
* `RepositoryIndexer.run_incremental(...)` was implemented in `apps/ai/src/indexer/pipeline.py` (line 328).
* However, grep searches reveal it is **only called in unit/integration test files**.
* Neither `app.py`, `init_job.py`, `pr_eval_job.py`, nor Bun webhooks ever invoke `run_incremental`.
* Webhook push events either re-run a full wiping initialization or run `pr_eval_job.py`.

#### Catastrophic Bug 3: Incremental Indexing Has Zero Vector Sync
In `pipeline.py` (lines 600–770), `run_incremental` updates Neo4j (deleting removed symbols, inserting modified symbols, rewiring caller edges), but **contains zero lines of code interacting with `self.vector_client`**.
* Deleted functions remain in ChromaDB forever.
* Modified functions create duplicate or stale embeddings.
* New functions are never embedded.

---

### 4.2 VectorDB Issues & "Document Limit Reached"

#### Why Document Limits Are Reached:
1. **Unfiltered Symbol Ingestion:**
   In `pipeline.py` (lines 250–266), the indexer iterates over every single symbol extracted from Tree-sitter:
   ```python
   for pr in parse_results:
       for sym in pr.symbols:
           vector_entries.append({...})
   ```
   In any moderate TypeScript/Python repository, this extracts 5,000–25,000 symbols (including every arrow function, callback, helper, test case, type alias, getter, and setter).
2. **Smart Cleaner is Bypassed:**
   A filtering module exists in `apps/ai/src/vector/cleaner.py` (`clean_code_symbol`), which detects script length, drops empty docstrings, and ignores trivial one-liner stubs (`pass`, `return`, `return None`, `{}`, `;`). **This cleaner is never invoked during semantic indexing in `pipeline.py`!**
3. **Unbounded ChromaDB Collection Queries:**
   In `apps/ai/src/vector/stores/chroma_store.py`:
   ```python
   def get_distinct_repos(self) -> List[str]:
       data = self._collection.get(include=["metadatas"]) # <-- Fetches entire DB into memory!
   ```
   Calling `.get()` without a limit parameter causes ChromaDB to attempt loading all embeddings and metadata into memory at once, crashing the process or hitting Chroma/Chroma Cloud document payload limits.
4. **Gemini Embedding Quota & Batching:**
   In `gemini_embedder.py`, sending large uncurated symbol batches exhausts Google GenAI API rate limits (1,500 requests/min or 1M tokens/min on free/pay-as-you-go tiers), producing `RESOURCE_EXHAUSTED` / `429` errors.

---

### 4.3 Missing Agents from [FEATURES.md](file:///home/aryanracha/Coding/projects/gitami/docs/FEATURES.md)

| Feature / Agent | Specification Requirement | Current Codebase Status |
| :--- | :--- | :--- |
| **Investigation Agent** | Single-shot answers for simple questions; up to 8-step iterative hypothesis-refinement loops with reasoning traces and confidence scores for root-cause analysis; structured JSON for agents, plain text for chat; production alert intake. | **Missing.** Only a generic 5-step ReAct loop exists in `agent_loop.py` without hypothesis loops, confidence scores, or structured agent outputs. |
| **Doc Agent** | Generates workflow guides, domain onboarding docs, weekly changelogs from merged PRs, and architectural decision logs; feeds docs back into the knowledge base; marks docs stale on code change. | **Missing completely.** Zero documentation generation logic exists. |
| **Issue Agent** | Triggered on GitHub Issue creation; duplicate detection across open/closed issues; criticality scoring; domain tagging; `ai-code-suspected` flag; triggers Investigation Agent. | **Missing completely.** `handleIssuesEvent` in `webhook.service.ts` is a stub `console.log`. |
| **Review Agent** | Risk score, blast radius, convention violations, test coverage gaps, AI code detection, security anti-patterns, cross-repo contract breaks; checklist with `blocking`, `warning`, `suggestion`; export to Claude Code/Codex. | **Incomplete prototype.** Exists in `reviewer.py`, but misses test coverage checks, AI code detection, cross-repo contracts, and checklist export. |
| **Code Agent** | Guardrailed sandbox remediation. Fix plan first (files and order) $\to$ wait for approval $\to$ writes tests first $\to$ executes in sandbox $\to$ opens PR only if tests pass. | **Missing.** Only a rudimentary LLM string-diff generator exists (`fixer.py`). No sandbox, no test runner, no plan approval gate. |
| **Chat Interface** | Transparent routing (direct LLM vs. Investigation Agent); shows path taken and why; supports natural language agent commands ("review PR #42"). | **Incomplete prototype.** Chat connects to basic ReAct loop; lacks complexity-based routing or agent invocation commands. |

---

## 5. Architectural Alignment Matrix (Current vs. Target)

```
CURRENT FRACTURED STATE:
┌──────────────┐         (calls port 5000)        ┌────────────────────────┐
│  Next.js 16  │ ───────────────────────────────► │ Bun Control Plane API  │
│  (apps/web)  │ ──┐                              │ - Unauth diff scraping │
└──────────────┘   │ (calls port 8000 directly)   │ - In-memory bg jobs    │
                   │                              │ - No-op issue webhook  │
                   ▼                              └────────────────────────┘
┌─────────────────────────────────┐
│     Python AI Service           │
│ - Fallback GitHub webhooks      │
│ - Indexes apps/ai directory     │
│ - run_incremental is dead code  │
│ - VectorDB symbol flood         │
└─────────────────────────────────┘

TARGET STREAMLINED ARCHITECTURE:
┌────────────────────────────────────────────────────────┐
│             Next.js 16 Web Dashboard                  │
│  - Clean multi-tenant routing: /[teamSlug]/[project]   │
│  - Unified Team, Project, Member, Repo CRUD UX         │
│  - Full transparency: routing paths, confidence scores │
└───────────────────────────┬────────────────────────────┘
                            │ Single authenticated API client
                            ▼
┌────────────────────────────────────────────────────────┐
│              Bun API Control Plane                     │
│  - Sole GitHub App owner & webhook receiver            │
│  - Authenticated Octokit diff & PR management          │
│  - Durable PostgreSQL Index Job state machine          │
│  - Dispatches tasks to AI Service                      │
└───────────────────────────┬────────────────────────────┘
                            │ Governed RPC / Job Dispatch
                            ▼
┌────────────────────────────────────────────────────────┐
│              Python AI Service                         │
│  - Canonical Indexer (Snapshot -> Tree-sitter -> Neo4j)│
│  - Working Incremental Indexer (Diff -> Graph + Vector)│
│  - Cleaned & Curated Vector Store (Chroma / Pgvector)  │
│  - Governed Context Engine (Graph + Semantic + Source) │
│  - Curated Agents:                                     │
│    * Investigation Agent (Single-shot + 8-step loop)   │
│    * Doc Agent (Guides, changelogs, stale tracking)    │
│    * Issue Agent (Duplicates, spam, criticality)       │
│    * Review Agent (Blast radius, contracts, checklist) │
│    * Code Agent (Plan approval -> Sandbox tests -> PR) │
└────────────────────────────────────────────────────────┘
```

---

## 6. Step-by-Step Refactoring & Action Plan

### Step 1: Clean Up & Unify the Frontend (`apps/web`)
1. **Purge Route Duplication:**
   * Delete legacy `app/(app)/*` routes and replace with top-level redirects to `/[teamSlug]/[projectSlug]`.
   * Delete `app/[teamSlug]/projects/[projectSlug]/*` redirect files.
2. **Unified Navigation & Layout:**
   * Standardize the layout so both Team Overview and Project Workspace share consistent, robust navigation.
   * Fix `<Sidebar />` so it never generates broken links (`/${teamSlug}//...`) when a project is not yet selected.
3. **Route All API Requests Through Bun Control Plane:**
   * Remove direct `AI_SERVICE_BASE_URL` calls from `lib/api.ts`.
   * Proxy chat, health, prompts, and graph-reports through Bun `/api/v1/*` routes with session validation.
4. **Complete CRUD UX:**
   * **Teams & Members:** Add intuitive team member management with role selection (`OWNER`, `MEMBER`, `VIEWER`), invitations, and removals.
   * **Projects:** Enable smooth project creation, editing, and repository attachment with real-time feedback.
   * **Repositories:** Streamline the connection flow, clearly show indexed commit SHAs and indexing health, and replace confusing "Build" terminology with "Index Knowledge Base".
5. **Fix Store Architecture:**
   * Eliminate global module-level in-flight promise variables.
   * Fix the PR review infinite re-render loop.

### Step 2: Refactor & Modularize the API Service (`apps/api`)
1. **Modularize Route Controllers:**
   * Break `github.routes.ts`, `pr.service.ts`, and `projects.service.ts` into clean, testable sub-modules.
2. **Authenticated GitHub Operations:**
   * Replace public diff scraping with authenticated GitHub App Octokit requests (`octokit.rest.pulls.get({ mediaType: { format: 'diff' } })`).
3. **Implement Durable Job Tracking:**
   * Standardize `indexJobs` state transitions (`QUEUED` $\to$ `RUNNING` $\to$ `COMPLETED` / `FAILED`).
   * Add timeouts and recovery for stuck jobs.
4. **Wire Webhook Handlers to Real Workflows:**
   * Connect `handleIssuesEvent` to the Issue Agent workflow.
   * Dispatch incremental indexing on `push` webhooks.

### Step 3: Repair & Optimize the AI Service (`apps/ai`)
1. **Fix GitHub Remote Ingestion:**
   * Ensure `run_init_job` accepts and indexes the parsed results or checks out the repository snapshot properly, rather than falling back to `Path(".")`.
2. **Activate Incremental Re-Indexing:**
   * Wire `run_incremental` into the push/webhook evaluation pipeline.
   * Add complete Vector DB synchronization to `run_incremental` (delete stale symbol embeddings, update modified symbols, insert added symbols).
3. **Resolve VectorDB Flooding & Document Limits:**
   * Integrate `src/vector/cleaner.py` into `pipeline.py` to filter out boilerplate stubs and trivial code bodies before vector ingestion.
   * Introduce paginated queries in `chroma_store.py` to prevent memory exhaustion and document limit errors.
   * Add metadata batching and rate-limiting resilience for embedding models.
4. **Hook Up the Context Engine:**
   * Connect `apps/ai/src/context/engine.py` as the unified data provider for Chat, Review Agent, and Investigation Agent.

### Step 4: Implement the Missing Curated Agents
1. **Investigation Agent:** Build single-shot vs. 8-step iterative hypothesis loop with confidence scores and structured output.
2. **Doc Agent:** Implement automated architecture docs, onboarding guides, changelogs, and staleness detection.
3. **Issue Agent:** Implement duplicate detection, spam filtering, and criticality scoring on issue webhooks.
4. **Review Agent Upgrades:** Add blast radius checks, test coverage gaps, cross-repo contract validation, and checklist export.
5. **Code Agent:** Create sandbox execution with fix plan approval checkpoints and test-first validation.
