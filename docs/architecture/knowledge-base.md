# GitAmi — Knowledge Base

> Single source of truth for the current system. Updated: October 2026.

---

## What GitAmi Is

A **codebase management and auditing platform** — not a code generation or CI/CD tool. It gives engineering teams a structured intelligence layer over their GitHub repositories and uses agents to investigate, triage, review, and remediate issues.

---

## System Architecture

Three services. One strict data flow. Never deviate from this boundary.

```
Next.js (apps/web)
    ↓  all traffic — authenticated, session-validated
Bun / Hono (apps/api)          ← sole GitHub App owner
    ↓  governed job dispatch
Python FastAPI (apps/ai)       ← all analysis and agents, no GitHub credentials
```

**Rules that must not be broken:**
- The frontend talks **only** to Bun (`apps/api`). Never directly to Python.
- Bun owns all GitHub App auth, webhooks, and Octokit calls.
- Python never calls GitHub directly and never holds GitHub credentials.
- Python never receives raw GitHub webhooks.

---

## Service Breakdown

### `apps/web` — Next.js 16 Frontend

**Target routing structure** (single canonical path):
```
/[teamSlug]/[projectSlug]/*    ← the only active routes
```

**What exists:** Three conflicting routing hierarchies — legacy `(app)/*`, duplicate redirect files under `[teamSlug]/projects/[projectSlug]/*`, and the actual target routes under `[teamSlug]/[projectSlug]/*`. The first two only exist to redirect to the third.

**State stores (Zustand):** `authStore`, `teamStore`, `projectStore`, `repoStore`, `buildStore`, `chatStore`. They have overlapping responsibilities and go out of sync when switching teams.

**Known bugs:**
- Sidebar generates broken links (`/${teamSlug}//repositories`) when no project is selected — `effectiveProjectSlug` resolves to empty string.
- PR reviews page has an infinite re-render loop: `selectedPR` is a dependency of the `useCallback` that sets `selectedPR`, causing `loadPRs` to recreate itself on every render.
- Frontend directly calls Python on port 8000 for chat, graph reports, ingestion, and health checks — bypassing Bun entirely, carrying no auth headers.

**UX issues:**
- Indexing a codebase is called "Running a Build" — confusing users who expect CI/CD behaviour. Should be "Index Knowledge Base".
- Repository index status (which commit SHA is indexed, whether it's stale) is not visible without navigating into builds.
- Team member management exists in the API but has no meaningful presence in the UI.

---

### `apps/api` — Bun / Hono Control Plane

**What exists:** Working GitHub App OAuth, repo listing, project CRUD, PR review triggering, basic webhook intake, and a Drizzle + PostgreSQL setup.

**Known bugs:**

| Bug | Location | Impact |
|---|---|---|
| Public diff scraping | `pr.service.ts` lines 206–216 | `fetch("https://github.com/{repo}/pull/{n}.diff")` with no auth token. Returns 404 for all private repos. PR reviews receive empty diffs. |
| Untracked background jobs | `projects.service.ts` | `executeBackgroundBuild` is a fire-and-forget async promise. If Bun restarts, the DB row stays `RUNNING` forever with no timeout or recovery. |
| Issue webhook is a stub | `webhook.service.ts` | `handleIssuesEvent` only does `console.log`. No triage, no agent call. |
| Large monolith files | `github.routes.ts` (592 lines), `pr.service.ts` (662 lines), `projects.service.ts` (498 lines) | Untestable, hard to extend. |

---

### `apps/ai` — Python FastAPI + Neo4j + ChromaDB

**What exists:** Tree-sitter multi-language AST parsing, Neo4j graph schema and ingestion, ChromaDB vector store, a context engine, a basic ReAct agent loop, and a PR reviewer prototype.

**Critical bugs:**

| Bug | Location | Impact |
|---|---|---|
| GitHub repo is never indexed | `init_job.py` | `run_init_job` ignores the `parse_results` parameter passed from the tarball stream. Because `repo_dir` is `None` for remote repos, it defaults to `Path(".")` and indexes the `apps/ai` directory on the host machine instead. |
| Incremental indexing is dead code | `pipeline.py` | `run_incremental` is implemented but never called from `app.py`, `init_job.py`, or any webhook handler. Push events either run a full wipe-and-reindex or call `pr_eval_job`. |
| Incremental indexing has zero vector sync | `pipeline.py` lines 600–770 | `run_incremental` updates Neo4j correctly but contains zero calls to `self.vector_client`. Deleted functions remain in ChromaDB forever, modified functions create duplicate embeddings, new functions are never embedded. |
| Vector store flooding | `pipeline.py` lines 250–266 | Every symbol from every file is embedded — 5,000–25,000 per repo including trivial one-liners. The `cleaner.py` module (`clean_code_symbol`) exists and correctly filters these out but is never called. |
| Unbounded ChromaDB query | `chroma_store.py` | `get_distinct_repos()` calls `.get()` with no limit, loading the entire collection into memory. Crashes the process on large repos. |
| Leaked webhook endpoints | `app.py` | Python exposes `/webhooks`, `/api/webhooks`, and `/api/github/webhooks`. Python must never receive GitHub webhooks directly. |
| Context engine disconnected | `context/engine.py` | The context engine exists but is not wired into the chat handler or any agent. |

---

## Intelligence Layer

The indexed knowledge that all agents query. Stored across two databases.

| Store | Contents |
|---|---|
| **Neo4j** | Symbol graph: files, functions, classes, call relationships, import relationships. Blast radius queries run here. |
| **ChromaDB** | Semantic embeddings of code chunks and documentation. Natural language search runs here. |

**Convention fingerprint:** Derived from the codebase at index time — naming patterns, error handling style, async patterns, test framework. Used by the Review Agent to detect deviations.

**Architecture KB:** Domain map, service ownership, ADRs, known anti-patterns. Partially inferred, partially curated by the team. Human-authored entries take precedence over inferred ones.

**Staleness tracking:** Every generated doc stores the commit SHA of the code it describes. When those files change, the doc is marked stale.

---

## Agents — Current Status

| Agent | What it should do | Current status |
|---|---|---|
| **Investigation Agent** | Takes a query + intel layer context. Fast single-shot for simple questions; 8-step iterative loop for root cause. Returns JSON for agents, plain text for chat. | **Missing.** Only a generic 5-step ReAct loop exists with no confidence scores or structured output. |
| **Doc Agent** | Generates workflow guides, onboarding docs, changelogs, and decision logs from the intel layer. Feeds docs back in. Marks docs stale on code change. | **Missing completely.** |
| **Issue Agent** | Triggered on GitHub Issue creation. Spam filter → duplicate detection → criticality scoring → labelling → comment. Passes context to Investigation Agent on request. | **Missing.** Webhook handler is a `console.log` stub. |
| **Review Agent** | Reviews PR diff: blast radius, convention violations, test coverage gaps, AI code detection, security anti-patterns, cross-repo contracts. Produces severity-graded checklist. Exports context to Claude Code. | **Incomplete prototype.** `reviewer.py` exists but misses test coverage, AI detection, cross-repo contracts, and checklist export. |
| **Code Agent** | Sandbox execution. Generates fix plan → maintainer approves → writes tests first → implements → runs tests → opens PR only if green. | **Missing.** Only a rudimentary LLM string-diff generator (`fixer.py`) exists. No sandbox, no approval gate, no test runner. |
| **Chat Interface** | Routes queries to direct LLM (simple) or Investigation Agent (complex). Shows which path was taken. Supports natural language agent commands. | **Incomplete.** Basic chat works but routing is absent and agent commands are not supported. |

---

## Fix Order

Work in this sequence. Each step unblocks the next.

### 1. Fix the foundation (AI Service)
- Fix `init_job.py` to use `parse_results` from the tarball stream, not `Path(".")`
- Wire `run_incremental` into push webhook handling in `app.py`
- Add vector sync to `run_incremental` (delete stale, update modified, insert new)
- Call `clean_code_symbol` from `cleaner.py` before any vector ingestion
- Add `.limit()` to all ChromaDB `.get()` calls
- Remove the three leaked webhook endpoints from `app.py`
- Connect `context/engine.py` to the chat handler and all agents

### 2. Fix the control plane (API Service)
- Replace public diff scraping with authenticated Octokit: `octokit.rest.pulls.get({ mediaType: { format: 'diff' } })`
- Move `executeBackgroundBuild` to a tracked job with DB state transitions: `QUEUED → RUNNING → COMPLETED / FAILED` with a timeout
- Wire `handleIssuesEvent` to the Issue Agent
- Break up the three monolith files into sub-modules

### 3. Fix the frontend
- Delete legacy `(app)/*` routes and `[teamSlug]/projects/[projectSlug]/*` redirect directories
- Remove all direct calls to port 8000 from `lib/api.ts`; proxy everything through Bun
- Fix the sidebar broken-link bug (guard against empty `effectiveProjectSlug`)
- Fix the PR reviews infinite re-render loop (remove `selectedPR` from `useCallback` deps)
- Replace "Build" / "Run a Build" terminology with "Index Knowledge Base"

### 4. Build the missing agents (in order)
1. Investigation Agent — fast path first, then agentic loop
2. Issue Agent — spam filter, duplicate detection, criticality, labels, comment
3. Review Agent upgrades — add missing checks, checklist export
4. Doc Agent — workflow docs and changelogs first
5. Code Agent — fix plan + approval gate first, sandbox execution second

---

## Key Conventions

- **Python agents** never call GitHub. They receive all repo data from Bun via job dispatch.
- **LLM Engine:** Dual-LLM architecture using Gemini (Gemini 2.0 Flash as Primary Orchestrator & Agents) + Groq (Llama 3.3 70B as fast parallel worker & fallback), with an extensible gateway interface to support additional providers in the future.
- **All agent outputs** are validated Pydantic models. No raw LLM strings passed between services.
- **Code Agent** operates on a branch only. Declares `scoped_files` upfront. Any write outside that list aborts the run immediately.
- **Context chain** is accumulated across agents in a workflow and passed forward — never reset between steps.
