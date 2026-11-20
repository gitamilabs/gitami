# Current Indexing Architecture & Implementation Baseline

> **Status:** Current State Analysis (Pre-Migration)  
> **Date:** September 2026  
> **Target Scope:** Document existing indexing implementation, data models, limitations, and technical debt.

---

## 1. Executive Summary

Gitami currently operates as a **single-repository-centric** prototype. The indexing flow extracts code structure (AST) via Tree-sitter and stores it into **Neo4j** (code graph) and a pluggable **Vector DB** (semantic code symbols).

While functional for local demonstrations and single-repository PR evaluations, the current implementation is **monolithic, synchronous, and destructive**:
- Indexing is triggered synchronously via HTTP or CLI commands.
- Initial indexing wipes out existing graph and vector data for a branch rather than versioning or updating it incrementally.
- PR evaluation mutates the live branch graph directly in Neo4j during analysis.
- There is no concept of a `Project` spanning multiple repositories, no Git history indexing (commits, authors, parents), no GitHub issue/PR metadata indexing, no background worker/queue infrastructure, and zero provenance or confidence tracking.

---

## 2. Current Indexing Entry Points

| Entry Point | Protocol / Mechanism | Path / Command | Behavior |
|---|---|---|---|
| **CLI Init** | Python CLI (`click`) | `uv run ai-service init --repo-id <id> --branch <branch> --repo-dir <dir>` | Calls `run_init_job()` directly on local directory. Blocks terminal until complete. |
| **AI Service Web API** | HTTP POST | `POST /api/ingest` on `backend/ai-service` | Accepts `{ repo_id, full_name, access_token, branch, repo_dir, extraction_mode }`. Executes `run_init_job()` synchronously in the request thread. |
| **API Service Control Plane** | HTTP POST | `POST /repositories/:id/ingest` on `backend/api-service` | Bun route checks user permissions, gets GitHub App token, and performs a synchronous HTTP `fetch` to `ai-service /api/ingest`. |
| **Local Ingest API** | HTTP POST | `POST /ingest-local` on `backend/api-service` | Bun route forwards local folder path to `ai-service /api/ingest`. |
| **PR Evaluation Job** | Python CLI / HTTP | `uv run ai-service eval-pr` or `POST /api/pr/review` | Invokes `run_pr_eval_job()`, which computes a git diff and mutates the branch graph directly. |

---

## 3. Important Files & Modules

### Python AI Service (`backend/ai-service/src/ai_service/`)

- **`jobs/init_job.py`**: The core repository initialization routine (`run_init_job`). Coordinates schema enforcement, data purging, AST parsing, Neo4j upserting, vector batch upserting, and import resolution.
- **`jobs/pr_eval_job.py`**: PR evaluation runner (`run_pr_eval_job`). Computes changed files using git diff, deletes changed files from Neo4j, re-inserts symbols, and evaluates blast radius.
- **`parsing/parser.py`**: `CodeParser` and `LanguageRegistry`. Manages Tree-sitter grammars for Python, JavaScript, TypeScript, JSX, and TSX.
- **`parsing/models.py`**: Data structures: `SymbolNode`, `CallEdge`, `ImportEdge`, and `ParseResult`.
- **`parsing/extractors/python.py`**: Tree-sitter extractor for Python functions, classes, methods, docstrings, calls, and imports.
- **`parsing/extractors/mern.py`**: Tree-sitter extractor for JavaScript/TypeScript functions, arrow functions, classes, React components, calls, and imports.
- **`graph/client.py`**: `Neo4jClient`. Async Neo4j driver wrapper with retry logic and exponential backoff.
- **`graph/schema.py`**: Neo4j uniqueness constraints and index definitions (`symbol_repo_isolation`, `module_repo_isolation`, `symbol_repo_idx`).
- **`graph/writer.py`**: Cypher write queries (`upsert_file_and_symbols`, `upsert_call_edges`, `upsert_import_edges`, `delete_file_data`, `delete_repo_data`).
- **`graph/resolver.py`**: Post-processing step (`resolve_repo_imports`) that resolves relative JS/TS and Python module paths against known repository files and converts external `Package` stubs to internal `DEPENDS_ON_FILE` and `IMPORTS` edges.
- **`graph/reader.py`**: Cypher query functions (`get_symbol`, `get_dependents`, `get_dependencies`, `get_entire_graph`).
- **`vector/client.py`**: `VectorKBClient`. Facade over vector stores and embedding models. Handles chunking, batching, upserting, and querying.
- **`vector/cleaner.py`**: Filters boilerplate and cleans symbol code bodies before vector ingestion.
- **`vector/cache.py`**: `VectorCacheManager`. Local JSON file manifest caching based on HEAD commit hash.
- **`repo/streamer.py`**: `stream_and_parse_github_repo`. In-memory download and extraction of GitHub repository tarballs without writing to disk.
- **`repo/cloner.py`**: Local git clone wrapper using GitPython.
- **`repo/differ.py`**: Git diff utilities (`get_changed_files`, `get_changed_symbols`) comparing commits via GitPython.
- **`web/app.py`**: FastAPI HTTP server exposing endpoints for chat, prompt management, ingestion, and PR review.

### Bun API Service (`backend/api-service/src/`)

- **`db/schema/`**: Drizzle schema definitions for PostgreSQL:
  - `users.ts`: User authentication records.
  - `github_installations.ts`: GitHub App installations.
  - `connected_repositories.ts`: Connected GitHub repositories.
  - `pull_requests.ts`: Tracked PR metadata (state, SHAs, status).
  - `pr_reviews.ts`: PR evaluation results and risk scores.
  - `pr_issues.ts`: Discovered PR issues, line numbers, and suggestions.
- **`modules/github/webhook.service.ts`**: Webhook intake for GitHub events (`installation`, `installation_repositories`, `issues`, `pull_request`). Dispatches async PR evaluations.
- **`modules/github/github.routes.ts`**: Endpoints for listing repos, connecting repos, and triggering repository ingestion (`/repositories/:id/ingest`).
- **`modules/pr/pr.service.ts`**: PR synchronization from GitHub and caller to AI Service `/api/pr/review`.

---

## 4. Current Data Flow (End-to-End)

```
[ User / Webhook ]
        │
        ▼
[ API Service (Bun) ] ── (sync HTTP fetch /api/ingest) ──► [ AI Service (FastAPI) ]
                                                                     │
                                           ┌─────────────────────────┴─────────────────────────┐
                                           ▼                                                   ▼
                                 GitHub Tarball Stream                                Local Directory
                               (repo/streamer.py, in-memory)                        (parsing/parser.py)
                                           └─────────────────────────┬─────────────────────────┘
                                                                     ▼
                                                          Tree-sitter AST Parser
                                                       (Python & MERN Extractors)
                                                                     │
                                                   ┌─────────────────┴─────────────────┐
                                                   ▼                                   ▼
                                           Neo4j Graph Writer                  Vector KB Client
                                       - Delete existing repo/branch       - Delete existing repo/branch
                                       - Upsert File nodes                 - Filter boilerplate
                                       - Upsert Symbol nodes               - Batch embed symbols
                                       - Upsert CALLS edges                - Upsert doc chunks
                                       - Upsert IMPORTS edges                          │
                                       - Run resolve_repo_imports()                    │
                                                   │                                   │
                                                   ▼                                   ▼
                                          [ Neo4j Database ]                  [ Vector Database ]
                                      (File, Symbol, Package)             (Chroma / Qdrant / etc.)
```

---

## 5. Current Neo4j Graph Model

### Existing Node Types

| Node Label | Identifying Properties | Other Properties | Description |
|---|---|---|---|
| `:File` | `repo_id`, `branch`, `file_path` | `language` | Represents a source code file. |
| `:Symbol` | `repo_id`, `branch`, `qualified_name` | `name`, `kind` (`function`, `class`, `method`, `component`), `file_path`, `language`, `start_line`, `end_line`, `signature`, `docstring` | A code declaration extracted from AST. |
| `:Package` | `repo_id`, `branch`, `name` | *(none)* | External dependency stub created when an import cannot be resolved internally. |

### Existing Relationship Types

| Relationship | Source Node | Target Node | Properties | Description |
|---|---|---|---|---|
| `DEFINES` | `:File` | `:Symbol` | *(none)* | File contains the symbol declaration. |
| `CALLS` | `:Symbol` | `:Symbol` | `file_path`, `line` | Symbol invokes another symbol within the same repository. |
| `IMPORTS` | `:File` | `:Symbol` | `module_path`, `line` | File imports an internal symbol. |
| `DEPENDS_ON` | `:File` | `:Package` | `imported_symbol`, `line` | File imports an unresolved/external package. |
| `DEPENDS_ON_FILE` | `:File` | `:File` | *(none)* | File imports another file within the repository (created by resolver). |

### Current Identifiers & Scoping
- **Repository Identity:** Stored as `repo_id` (a string, typically GitHub `full_name` such as `"gitamilabs/gitami"`).
- **Branch Scoping:** Every node has a `branch` property (defaults to `"main"`). Graph queries filter by `repo_id` and `branch`.
- **Symbol Identity:** `qualified_name` formatted as `{file_path}::{scope_path}` (e.g., `src/utils.py::format_date`).
- **Source Locations:** Stored as `file_path`, `start_line`, and `end_line` on `:Symbol` and `line` on edges.

### How Graph Updates Currently Happen
- **On `run_init_job`:** Destructive wipe. Executes:
  ```cypher
  MATCH (n {repo_id: $repo_id, branch: $branch}) DETACH DELETE n
  ```
  Then re-inserts all files and symbols, connects calls, and runs `resolve_repo_imports`.
- **On `run_pr_eval_job`:** Destructive per-file wipe. Executes:
  ```cypher
  MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $file_path})
  OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
  DETACH DELETE f, s
  ```
  Then re-inserts only modified files directly into the branch graph.

---

## 6. Current Vector DB Model

### Supported Backends & Embedders
- **Vector Stores:** ChromaDB (Local / Cloud), Qdrant, Pinecone, Supabase pgvector, In-Memory (`vector/stores/`).
- **Embedder Models:** Google Gemini (`models/gemini-embedding-001`), OpenAI (`text-embedding-3-small`), FastEmbed local ONNX (`BAAI/bge-small-en-v1.5`) (`vector/embedders/`).

### What Gets Embedded
1. **Code Symbols:** Only individual symbols (`SymbolNode`) are embedded.
   - Text document format:
     ```text
     File: {file_path} (lines {start_line})
     Symbol: {symbol}
     Signature:
     {signature}
     Description:
     {docstring or fallback}
     Implementation Code:
     {code_body}
     ```
2. **Fallback File Content:** If a file has 0 symbols (e.g. config or empty file), an entry is created with file path and language.
3. **PR Descriptions, Commits, Issues:** Methods exist on `VectorKBClient` (`add_pr_entry`, `add_commit_entry`, `add_issue_entry`), but **none of these are called during repo initialization (`run_init_job`)**.

### Metadata & Document IDs
- **Document ID Format:**
  - Code: `code_{repo}_{branch}_{file_path}_{symbol}_{start_line}`
  - PR: `pr_{repo}_{branch}_{pr_id}_chunk_{idx}`
  - Commit: `commit_{repo}_{branch}_{commit_hash}_chunk_{idx}`
  - Issue: `issue_{repo}_{issue_id}_chunk_{idx}`
- **Metadata Fields:** `repo`, `branch`, `file_path`, `symbol`, `content_type` (`code` | `pr` | `commit` | `issue`), `commit_hash`, `last_valid_commit`.
- **Chunking Strategy:**
  - Code symbols: 1 chunk per symbol (filtered by `clean_code_symbol` and `filter_repetitive_boilerplate`).
  - PR / Issues / Commits: Markdown recursive splitter (`chunk_size=800, chunk_overlap=80`).

### Update and Delete Behavior
- During `init_job`, all documents matching `{"$and": [{"repo": repo_id}, {"branch": branch}]}` are deleted before re-indexing.
- `roll_forward_commit()` and `delete_stale_entries()` exist on `VectorKBClient` for rolling forward commits, but are **not connected to any git webhook or pipeline**.

---

## 7. Current Limitations & Technical Debt

1. **No Project Hierarchy:** Everything is scoped to a single `repo_id`. Multi-repo projects, shared services, and cross-repo dependencies cannot be represented.
2. **Synchronous Ingestion Bottleneck:** Both `backend/api-service` and `backend/ai-service` handle indexing synchronously inside HTTP request handlers. A large repo clone or embedding run causes HTTP 504 Gateway Timeouts or dropped connections.
3. **No Background Worker or Queue:** No Redis, BullMQ, Celery, or ARQ job queue exists. Jobs are either in-memory async tasks or run in-process.
4. **Destructive Re-indexing:** Ingestion purges existing graph and vector databases completely (`DETACH DELETE n`). If indexing fails midway, the entire knowledge base is lost and left empty.
5. **No Commit-Level Graph Isolation:** The graph is keyed only by `(repo_id, branch)`. There is no immutable commit SHA scoping. If a PR is evaluated, it directly mutates the branch graph with unmerged code.
6. **Ambiguous Call Graph Matching:**
   - Cypher in `upsert_call_edges` matches callees by bare name:
     ```cypher
     MATCH (callee:Symbol {repo_id: $repo_id, branch: $branch})
     WHERE callee.name = item.callee_name
     ```
   - If multiple classes or files have a method named `execute()` or `render()`, the caller gets connected to **all** of them, generating false edges and corrupting blast radius calculations.
7. **Missing Graph Entity Types:** The ontology only has `File`, `Symbol`, and `Package`. Missing critical concepts: `Directory`, `Module`, `Class`, `Function`, `Method`, `Interface`, `Type`, `Test`, `Commit`, `PullRequest`, `Issue`, `Service`, `Database`.
8. **No Git History or Metadata Indexing:** Commits, commit parents, authors, tags, PR discussions, issue threads, and CI statuses are ignored during repository indexing.
9. **Zero Provenance & Confidence:** Relationships in Neo4j have no confidence score or source attribution. An AST-extracted call and an LLM-inferred relationship look identical.
10. **Missing Deployment Config:** `docker-compose.yml` referenced in `Readme.md` is missing from the repository.

---

## 8. What Should Be Preserved vs What Should Change

### What to Preserve
- **Tree-sitter Parser Foundation (`parsing/`):** The Python and JavaScript/TypeScript tree-sitter extractors are fast, robust, and well-tested.
- **Pluggable Vector DB Architecture (`vector/`):** The factory pattern supporting Chroma, Qdrant, Pinecone, Supabase, and local FastEmbed embeddings is well-designed and should be retained.
- **Import Resolution Logic (`graph/resolver.py`):** The relative path resolution algorithm for JavaScript and Python imports is solid and should be integrated into the incremental pipeline.
- **In-Memory GitHub Streaming (`repo/streamer.py`):** Streaming tarballs directly into memory without disk IO is valuable for ephemeral indexing environments.
- **PostgreSQL Database Schema (`backend/api-service/src/db/schema/`):** Existing tables for users, GitHub installations, connected repositories, PR reviews, and issues are clean and can be extended.

### What Must Change
- **Introduce `Project` Entity:** Relate organizations, projects, and multiple repositories in PostgreSQL and Neo4j.
- **Decouple Ingestion from HTTP:** Move indexing to asynchronous, persistent background jobs (`IndexJob`) with state machines and progress tracking.
- **True Incremental Indexing:** Track `indexed_commit_sha`. When new commits arrive, compute `git diff A..B`, selectively delete affected symbols and edges, re-parse only changed files, and atomically update the indexed commit SHA.
- **Refined Graph Ontology:** Differentiate `Class`, `Function`, `Method`, `Interface`, `Test`, `Commit`, `PullRequest`, and `Issue`.
- **Qualified Call Resolution:** Disambiguate call targets using imports and file scopes rather than global name matching.
- **Provenance & Confidence Tracking:** Add `source` (`DETERMINISTIC`, `INFERRED`, `SEMANTIC`), `confidence` (0.0–1.0), and extraction metadata to all relationships.
