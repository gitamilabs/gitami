# AI Service — Technical Specification v3 (Final Year Project)

## 1. Overview

A knowledge-base-backed code review service for a single GitHub repository.
Given a repo link, the service builds a vector + graph knowledge base of the
codebase, then watches incoming pull requests, evaluates them (blast radius,
convention checks, sandbox tests), and either accepts the change or suggests
fixes before a final PR is made.

**Change from v2:** Bun is no longer a passive proxy. Bun owns the entire
GitHub integration surface — auth, repo connection, repo management, and
webhook intake — plus the frontend API. Bun **starts** the Python orchestrator
as a job whenever analysis work is needed (initialization or PR evaluation).
Python holds **no GitHub credentials** and never talks to GitHub directly —
it receives what it needs from Bun, does the analysis, and returns structured
results to Bun, which then acts on GitHub.

Runtime constraint: **Bun and UV only.**

---

## 2. Assumptions & Open Questions

| # | Ambiguity | Assumed resolution |
|---|---|---|
| 1 | "GraphQL [branch-wise]" in original sketch | Interpreted as **GraphDB, kept branch-wise** — a separate graph snapshot per branch. Confirm this wasn't meant as a GraphQL API layer. |
| 2 | "dockerd" step before the OK/not-OK gate | **Sandboxed execution** of the incoming diff, run by the Python orchestrator job. |
| 3 | Who applies an accepted fix to GitHub | Python generates the fix as a **patch/diff** and returns it to Bun; **Bun applies it** via the GitHub API (commit, push, open/update PR) since Bun holds the credentials. Python never writes to GitHub. |
| 4 | Repeated pushes to an already-evaluated PR | Bun receives the webhook, starts a new Python job scoped to the delta since the last-evaluated commit. |
| 5 | GitHub auth model | **GitHub App, owned entirely by Bun** — installation, tokens, webhook registration all live in Bun. |
| 6 | Where do GitHub webhooks land? | **Directly on Bun** — webhooks are part of repo management, which Bun now owns. |
| 7 | How Python gets repo access for cloning | Bun passes a short-lived clone URL/token to the Python job at start time. Python does not persist or manage this credential. |
| 8 | Single repo vs multi-repo | Scoped to single repo per connection for the FYP. |

---

## 3. Tech Stack

| Layer | Tool | Responsibility |
|---|---|---|
| **Bun** (TypeScript) | GitHub App auth & installation, repo connection/management, webhook intake (PR opened/updated/merged), starting Python orchestrator jobs, applying results back to GitHub (comments, commits, PRs), frontend-facing API | Owns all GitHub-facing and control-plane responsibility |
| **Python via UV** | Repo cloning (using a token passed in by Bun), AST parsing, embedding generation, graph construction, blast-radius computation, convention checks, sandbox test execution, decision gate, Knowledge Base reads/writes, fix-patch generation | Owns all analysis/computation — invoked as a job by Bun, returns structured results, holds no GitHub credentials |

**Bun's responsibility list (now the control plane):**
- GitHub App installation and token management
- Repo connect / disconnect / list / status (repo management)
- Receive and validate GitHub webhooks
- Start a Python orchestrator job (subprocess or internal call) for initialization or PR evaluation, passing repo access + event context
- Receive structured results back from the Python job
- Act on GitHub using its own credentials: post PR comments, apply fix patches as commits, open/update PRs
- Serve the frontend API (status, suggestions, accept/deny actions)

**Python's responsibility list (pure computation, no GitHub access):**
- Clone repo using the token/URL handed to it by Bun (not self-managed)
- Parse, embed, build/update the graph, write to the Knowledge Base
- Compute blast radius, run convention checks, run sandbox tests
- Produce a decision object (ACCEPT / SUGGEST) and, for suggestions, a fix patch
- Return everything to Bun and exit — no persistent GitHub-facing role

---

## 4. System Architecture

```
GitHub  ──────────────────────────────┐
   │  (webhooks: PR opened/updated)      │  (App install, API calls: comments, commits, PRs)
   ▼                                       ▼
┌─────────────────────────────────────────┐
│                    Bun                      │
│  - GitHub App auth & installation             │
│  - Repo connect/manage                          │
│  - Webhook intake                                 │
│  - Starts Python orchestrator jobs                  │
│  - Applies results back to GitHub                     │
│  - Frontend-facing API                                  │
└───────────────┬───────────────────────┘
                │ starts job, passes repo token + event context
                ▼
┌─────────────────────────────┐
│      Python (UV) Orchestrator     │
│  - clone repo                        │
│  - AST parse / embed / build graph      │
│  - blast radius / convention check         │
│  - sandbox test execution                     │
│  - decision gate + fix patch generation           │
└───────────────┬─────────────┘
                ▼
┌─────────────────────┐
│   Knowledge Base       │
│  ┌─────────┐ ┌───────┐│
│  │ VectorDB │ │GraphDB││
│  └─────────┘ └───────┘│
└─────────────────────┘
                ▲
                │ read/write, owned by Python only
                (Bun never connects to the KB directly)

Frontend (UI) ──► Bun (status, suggestions, accept/deny)
```

---

## 5. Flow 1 — Repository Initialization (one-time per repo)

1. User connects a GitHub repo via the frontend → Bun.
2. Bun handles GitHub App installation (if not already installed) and stores the repo connection + installation token.
3. Bun **starts a Python orchestrator job**, passing a short-lived clone URL/token and repo metadata.
4. Python job clones the repo and parses it:
   - Extracts function/class-level AST nodes.
   - For each symbol, generates a **brief natural-language description** via LLM call (signature + description stored, never raw code).
   - Builds the call/import graph from AST edges.
5. Python job writes to the Knowledge Base (VectorDB + GraphDB), then reports completion status back to Bun and exits.
6. Bun updates repo status (`initializing` → `indexed`) and relays it to the frontend.

---

## 6. Flow 2 — Pull Request Evaluation

### 6.1 Trigger
GitHub webhook (PR opened or synchronize) fires on **Bun** — Bun owns webhook intake.

### 6.2 Orchestration
1. Bun validates the webhook, extracts the diff/changed files/branch.
2. Bun **starts a Python orchestrator job**, passing the diff context and a scoped repo access token.
3. Python job:
   - Computes **blast radius** from the GraphDB.
   - Runs **convention/pattern check** against embedded signatures/descriptions.
   - Runs the change in a **sandbox**: installs dependencies, runs the test suite.
   - Assembles a structured decision object and exits, returning it to Bun.

### 6.3 Decision gate (evaluated by Python, acted on by Bun)
```
IF sandbox tests pass AND no blocking convention/blast-radius issues:
    → Python returns ACCEPT + updated KB state
    → Bun: no GitHub write needed beyond optional status check / label
ELSE:
    → Python returns SUGGEST + structured suggestions (file, line, description, fix patch)
    → Bun posts the suggestions as PR comment(s) on GitHub
    → Bun pushes suggestion data to the frontend for maintainer review
    → Wait for maintainer accept/deny (via frontend → Bun)
```

### 6.4 Suggestion path
- Maintainer reviews suggestions via the frontend.
- **Accept** → frontend → Bun → Bun applies the fix patch (already generated by Python) as a commit to the PR branch via the GitHub API, updates/opens the PR.
- **Deny** → frontend → Bun → Bun records the dismissal and optionally starts a small Python job to log it against the Knowledge Base for future tuning.
- Any new commit to the branch re-triggers Flow 2 from §6.1 via the webhook.

### 6.5 Incremental re-check
On repeated pushes to an already-evaluated PR, Bun passes the last-evaluated
commit hash to the new Python job so it only re-checks the delta, not the
whole PR again.

### 6.6 Merge
On merge to the base branch (webhook event on Bun), Bun starts a Python job
scoped to the final merged diff to update the Knowledge Base.

---

## 7. Knowledge Base Schema

*(Unchanged — owned and accessed only by Python. Bun never connects to the
VectorDB or GraphDB directly; it only receives structured results from
Python jobs.)*

### 7.1 VectorDB entries

| Content type | What's embedded | Notes |
|---|---|---|
| Code | Function/class signature + brief LLM-generated description — never raw file content | |
| PR descriptions | Description text + linked issue thread summary | |
| Commit messages | Filtered — skip trivial commits | |
| Issues | Full issue text, open and closed | |

### 7.2 Metadata fields

| Field | Purpose |
|---|---|
| `repo` | Which repo this entry belongs to |
| `file_path`, `symbol` | Scope filtering |
| `content_type` | `code` \| `pr` \| `commit` \| `issue` |
| `branch` | Which branch this entry is valid for |
| `commit_hash` | For staleness tracking |
| `last_valid_commit` | When the referenced code last matched this entry |

### 7.3 GraphDB entries

- **Nodes:** symbols (functions/classes/modules), tagged with `branch`, `file_path`.
- **Edges:** `calls`, `imports`.
- Graph is branch-scoped: a feature branch's graph reflects that branch's own AST.

---

## 8. API / Service Boundaries

**Bun (GitHub integration + control plane + frontend API):**
- `POST /auth/github/install` — GitHub App installation callback.
- `POST /repos/connect` — connect a repo (from frontend), stores connection, starts init job.
- `GET /repos` / `GET /repos/:id` — repo management/listing.
- `DELETE /repos/:id` — disconnect a repo.
- `POST /webhooks/github` — GitHub webhook intake (PR events, merge events).
- `GET /repos/:id/prs/:prId/suggestions` — suggestions for the frontend to display.
- `POST /repos/:id/prs/:prId/decision` — maintainer accept/deny from the frontend.
- Internal: `start_python_job(type, context, repo_token)` — spawns/calls the Python orchestrator.

**Python orchestrator (invoked as a job by Bun, not a standing GitHub-facing service):**
- `run_init_job(clone_url, token, repo_meta)` — Flow 1.
- `run_pr_eval_job(diff, changed_files, branch, token, last_evaluated_commit)` — Flow 2.
- `run_dismissal_log_job(item, reason)` — optional, stretch goal.
- Internal-only functions: `parse_repo()`, `embed_and_store()`, `compute_blast_radius()`, `run_sandbox()`, `generate_fix_patch()`.
- Returns a structured result object to Bun on completion; holds no long-lived GitHub state.

---

## 9. Suggested Scope for a Final Year Project

**MVP (build this first):**
- Bun: GitHub App auth, single repo connect, webhook intake, job-starting, applying results to GitHub
- Python: Flow 1 init job, Flow 2 eval job (blast radius + sandbox tests), fix patch generation
- Basic VectorDB (code + PR + commits)
- Frontend: connect repo, view status, view suggestions, accept/deny

**Stretch (only if time remains):**
- Incremental re-check on repeated pushes (§6.5)
- Dismissal-reason capture feeding back into convention checks
- Multi-branch graph handling beyond basic per-branch scoping
- Real-time job status push from Bun to frontend (WebSocket) instead of polling

---

## 10. Open Items to Resolve Before Prompting a Build Tool

- [ ] Confirm assumption #1 (GraphDB branch-wise, not GraphQL)
- [ ] Confirm how Bun starts Python jobs in practice — subprocess per job vs a persistent Python service Bun calls into (affects deployment complexity)
- [ ] Pick concrete VectorDB and GraphDB tools based on available infra
- [ ] Decide how short-lived the clone token passed to Python should be, and how it's scoped
- [ ] Decide MVP cutoff line from §9 given remaining timeline
