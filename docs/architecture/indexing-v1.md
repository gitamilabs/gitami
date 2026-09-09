# Gitami v1 Indexing Architecture

> **Status:** Target Architecture Design  
> **Date:** September 2026  
> **Scope:** Evolution toward a production-grade Project Intelligence Indexing System supporting multi-repository projects, asynchronous job workers, incremental updates, rich graph ontology, and provenance tracking.

---

## 1. System Overview & Conceptual Architecture

The Gitami Project Intelligence Layer transforms raw source code, git history, and GitHub metadata from multiple repositories into an interconnected, queryable intelligence platform.

```
       GitHub Platform
   (Webhooks, Tarballs, REST)
              │
              ▼
   ┌──────────────────────┐
   │    Webhooks / API    │ ◄── User Manual Triggers
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │    Index Manager     │ (PostgreSQL State Machine & Queue)
   └──────────┬───────────┘
              │ Enqueues asynchronous jobs
              ▼
   ┌──────────────────────┐
   │     Index Worker     │ (Python Worker Pool / Consumer)
   └──────────┬───────────┘
              │
   ┌──────────┼──────────────────────┐
   │          │                      │
   ▼          ▼                      ▼
┌───────┐ ┌────────┐           ┌───────────┐
│  Git  │ │  AST   │           │   Docs    │
│History│ │ Graph  │           │ Semantic  │
└───┬───┘ └───┬────┘           └─────┬─────┘
    │         │                      │
    └─────────┼──────────────────────┘
              ▼
┌───────────────────────────────────────────┐
│       Project Intelligence Layer          │
│  (PostgreSQL + Neo4j + Vector Database)   │
└─────────────────────┬─────────────────────┘
                      │
                      ▼
           Context Engine & Agents
  (Review, Investigation, Issue, Code, Docs)
```

---

## 2. Core Components & Responsibilities

### 2.1 Index Manager (Control Plane)
- **Role:** Webhook intake, job scheduling, concurrency coordination, and state machine management.
- **Location:** Bun API Service (`backend/api-service`).
- **Responsibilities:**
  - Ingests GitHub webhooks (`push`, `pull_request`, `issues`).
  - Evaluates debounce rules (e.g. rapid consecutive pushes to the same branch).
  - Enqueues `IndexJob` records into PostgreSQL.
  - Ensures mutual exclusion per repository/branch (no concurrent writes to the same repository branch graph).
  - Tracks job progress and updates `RepositoryIndexState`.

### 2.2 Index Worker (Execution Engine)
- **Role:** Heavy computational processing of code, history, and metadata.
- **Location:** Python AI Service worker (`backend/ai-service`).
- **Responsibilities:**
  - Pulls queued jobs from the job store.
  - Fetches repository code (shallow git clone or in-memory tarball streaming).
  - Orchestrates the three extraction pipelines:
    1. **AST & Structural Analysis:** Tree-sitter parsing, symbol extraction, import resolution, call-graph creation.
    2. **Git History & Metadata:** Commits, branches, tags, PR threads, and issue extraction.
    3. **Documentation & Semantic Embeddings:** Markdown docs, ADRs, symbol summaries, and PR/issue threads.
  - Atomically writes graph nodes/edges into Neo4j and embeddings into Vector DB.
  - Reports fine-grained stage progress (`progress: 0..100`) and logs back to PostgreSQL.

### 2.3 Storage Engines
- **PostgreSQL:** Job state, repository index state, organizational hierarchy, users, access tokens, and relational metadata.
- **Neo4j:** Structural code graph, dependency graph, commit-to-file mappings, PR-to-issue links, and cross-repo dependencies.
- **Vector DB:** Semantic embeddings of code symbols, architecture documents, PR summaries, and issue discussions.
- **Object Storage (S3 / R2):** Raw diffs, large AST serialization dumps, build logs, and tarballs.

---

## 3. Job Lifecycle & Failure Handling

### 3.1 Job State Machine

```
[ CREATED ]
    │
    ▼
 [ QUEUED ] ──────────────► [ CANCELLED ] (superseded by newer push)
    │
    ▼
 [ RUNNING ]
    │
    ├─────────────────────► [ FAILED ] ─── (retry count < 3) ──► [ QUEUED ]
    │                                  ─── (retry count >= 3) ──► [ PERMANENT_FAILURE ]
    ▼
[ COMPLETED ]
    │
    ▼
(Update RepositoryIndexState: status = READY, indexed_commit_sha = target_sha)
```

### 3.2 Failure Handling & Safe Recovery
- **Crash Recovery:** If an `IndexWorker` dies midway, heartbeats stored in PostgreSQL expire after 5 minutes, marking the job as `STALE` and eligible for re-queueing.
- **Non-Destructive Execution:** Workers write changes inside isolated transactions or stage them before updating the official `RepositoryIndexState.indexed_commit_sha`.
- **Atomic State Roll-Forward:** The repository is only marked `READY` with the new commit SHA *after* both Neo4j and Vector DB writes have succeeded.
- **Rollback / Fallback:** If an incremental index fails due to git divergence or parser errors, the Index Manager automatically schedules a `REINDEX` (full index) for the target commit.

---

## 4. Index Job & State Models

### 4.1 `IndexJob` (PostgreSQL Table: `index_jobs`)

```typescript
export const indexJobs = pgTable("index_jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: uuid("project_id")
    .notNull()
    .references(() => projects.id, { onDelete: "cascade" }),
  repositoryId: uuid("repository_id")
    .notNull()
    .references(() => connectedRepositories.id, { onDelete: "cascade" }),
  type: varchar("type", { length: 32 }).notNull(), // 'INITIAL', 'PUSH', 'MANUAL', 'REINDEX', 'SCHEMA_UPDATE', 'PARSER_UPDATE'
  baseCommitSha: varchar("base_commit_sha", { length: 128 }),
  targetCommitSha: varchar("target_commit_sha", { length: 128 }).notNull(),
  branch: varchar("branch", { length: 255 }).notNull().default("main"),
  status: varchar("status", { length: 32 }).notNull().default("QUEUED"), // 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
  progress: integer("progress").notNull().default(0), // 0 - 100
  stage: varchar("stage", { length: 64 }).notNull().default("PENDING"), // 'CLONING', 'AST_PARSING', 'GRAPH_WRITE', 'EMBEDDING', 'RESOLVING', 'METADATA_SYNC', 'COMPLETED'
  error: text("error"),
  retryCount: integer("retry_count").notNull().default(0),
  heartbeatAt: timestamp("heartbeat_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  startedAt: timestamp("started_at", { withTimezone: true }),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
```

### 4.2 `RepositoryIndexState` (PostgreSQL Table: `repository_index_states`)

```typescript
export const repositoryIndexStates = pgTable("repository_index_states", {
  id: uuid("id").primaryKey().defaultRandom(),
  repositoryId: uuid("repository_id")
    .notNull()
    .references(() => connectedRepositories.id, { onDelete: "cascade" }),
  branch: varchar("branch", { length: 255 }).notNull().default("main"),
  indexedCommitSha: varchar("indexed_commit_sha", { length: 128 }).notNull(),
  indexVersion: varchar("index_version", { length: 32 }).notNull().default("v1"),
  schemaVersion: varchar("schema_version", { length: 32 }).notNull().default("v1"),
  parserVersion: varchar("parser_version", { length: 32 }).notNull().default("1.0.0"),
  status: varchar("status", { length: 32 }).notNull().default("INITIALIZING"), // 'INITIALIZING', 'READY', 'STALE', 'REINDEXING', 'FAILED'
  symbolCount: integer("symbol_count").notNull().default(0),
  fileCount: integer("file_count").notNull().default(0),
  edgeCount: integer("edge_count").notNull().default(0),
  vectorCount: integer("vector_count").notNull().default(0),
  lastIndexedAt: timestamp("last_indexed_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});
```

---

## 5. Initial Indexing Pipeline (Step-by-Step)

```
Repository
   │
   ▼
[1] Clone / Checkout Target SHA
   │
   ▼
[2] File Discovery & Filtering (.gitignore, binary filter)
   │
   ▼
[3] File Content Hashing (SHA-256)
   │
   ▼
[4] AST Parsing (Tree-sitter)
   │
   ▼
[5] Symbol & Entity Extraction (Functions, Classes, Methods, Interfaces)
   │
   ▼
[6] Relationship Extraction (Defines, Calls, Imports, Extends)
   │
   ▼
[7] Graph Construction (Neo4j Batch Write)
   │
   ▼
[8] Import Resolution (Internal linkings, Package stubs)
   │
   ▼
[9] Git History Extraction (Commits, Authors, Modified files)
   │
   ▼
[10] GitHub Metadata Sync (Issues, PRs, Comments)
   │
   ▼
[11] Documentation Extraction & Embeddings (Vector DB)
   │
   ▼
[12] Validation & Verification Gate
   │
   ▼
[13] Mark Index as READY (Update RepositoryIndexState)
```

### Stage Specifications

| Stage | Input | Output | Target Storage | Failure Behavior | Mode | Incremental? |
|---|---|---|---|---|---|---|
| **1. Clone / Checkout** | `repo_url`, `target_sha`, auth token | Local git checkout or in-memory tarball | Temp filesystem / memory | Retry with backoff (3x), then FAIL job | Deterministic | Yes |
| **2. File Discovery & Filtering** | Directory tree, `.gitignore` rules | List of valid source file paths | Memory | Skip unreadable files with warning | Deterministic | Yes |
| **3. File Hashing** | File content | `{ file_path: sha256_hash }` map | Memory & PostgreSQL | Log error, skip file | Deterministic | Yes |
| **4. AST Parsing** | Raw source bytes | Tree-sitter AST syntax trees | Memory | Fallback to raw text representation | Deterministic | Yes |
| **5. Symbol Extraction** | AST syntax tree | `SymbolNode` structures (functions, classes, interfaces) | Memory | Record extraction warnings in job log | Deterministic | Yes |
| **6. Relationship Extraction** | AST syntax tree | `CallEdge`, `ImportEdge`, inheritance edges | Memory | Record partial edges | Deterministic | Yes |
| **7. Graph Construction** | Nodes & Edges | Neo4j nodes (`:File`, `:Class`, `:Function`) and edges | Neo4j | Transaction abort and rollback | Deterministic | Yes |
| **8. Import Resolution** | File list, import edges | Resolved `IMPORTS`, `DEPENDS_ON_FILE` edges | Neo4j | Leave as unresolved `Package` stub | Deterministic | Yes |
| **9. Git History** | Git commit log (`HEAD~100..HEAD`) | `:Commit` nodes, `:MODIFIES` edges | Neo4j & PostgreSQL | Warning; continue remaining indexing | Deterministic | Yes |
| **10. GitHub Metadata** | GitHub REST / GraphQL API | `:PullRequest`, `:Issue` nodes, comments | Neo4j & PostgreSQL | Rate-limit pause/retry; continue if non-fatal | Deterministic | Yes |
| **11. Embeddings** | Cleaned symbols, docstrings, markdown docs | Dense vector vectors + metadata | Vector DB | Batch retry once; record failed chunks | Deterministic (Embedder) | Yes |
| **12. Validation Gate** | Node counts, graph connectivity | Sanity check pass/fail status | Memory | Mark job FAILED if zero nodes written | Deterministic | Yes |
| **13. Finalization** | Final counts & target SHA | `RepositoryIndexState` set to `READY` | PostgreSQL | Atomic DB update | Deterministic | Yes |

---

## 6. Target v1 Graph Ontology

### 6.1 Canonical Node Types

| Node Label | Key Properties | Description |
|---|---|---|
| `:Repository` | `project_id`, `repo_id`, `name`, `full_name`, `default_branch` | Top-level repository entity. |
| `:Directory` | `repo_id`, `path` | Folder structure container. |
| `:File` | `repo_id`, `branch`, `file_path`, `language`, `sha256` | Source code file. |
| `:Module` | `repo_id`, `branch`, `module_path` | Logical namespace or module. |
| `:Class` | `repo_id`, `branch`, `qualified_name`, `name`, `start_line`, `end_line` | Class declaration. |
| `:Function` | `repo_id`, `branch`, `qualified_name`, `name`, `signature`, `docstring`, `start_line`, `end_line` | Standalone function declaration. |
| `:Method` | `repo_id`, `branch`, `qualified_name`, `name`, `signature`, `docstring`, `start_line`, `end_line` | Function defined within a class/interface. |
| `:Interface` | `repo_id`, `branch`, `qualified_name`, `name`, `start_line`, `end_line` | TypeScript/Java interface or abstract type. |
| `:Type` | `repo_id`, `branch`, `qualified_name`, `name` | Type alias or enum. |
| `:Test` | `repo_id`, `branch`, `qualified_name`, `framework` | Unit or integration test function/suite. |
| `:Commit` | `repo_id`, `commit_sha`, `author_name`, `author_email`, `message`, `committed_at` | Git commit object. |
| `:PullRequest` | `repo_id`, `pr_number`, `title`, `state`, `author_login`, `html_url` | GitHub Pull Request. |
| `:Issue` | `repo_id`, `issue_number`, `title`, `state`, `author_login`, `html_url` | GitHub Issue. |
| `:Service` | `project_id`, `name`, `runtime`, `entry_point` | Top-level microservice or app component. |
| `:Database` | `project_id`, `name`, `engine` | Database or persistence system referenced in code. |

### 6.2 Reliable v1 Relationships

| Relationship | Source Node | Target Node | Meaning | Extraction Method | Default Confidence | Provenance | Incremental Update |
|---|---|---|---|---|---|---|---|
| `CONTAINS` | `:Repository` | `:Directory` | Directory belongs to repo | Directory walk | 1.0 | `DETERMINISTIC` | Yes |
| `CONTAINS` | `:Directory` | `:File` | File is inside directory | File walk | 1.0 | `DETERMINISTIC` | Yes |
| `DEFINES` | `:File` | `:Class` / `:Function` / `:Interface` | File declares entity | Tree-sitter AST | 1.0 | `DETERMINISTIC` | Yes |
| `HAS_METHOD` | `:Class` / `:Interface` | `:Method` | Class declares method | Tree-sitter AST | 1.0 | `DETERMINISTIC` | Yes |
| `EXTENDS` | `:Class` | `:Class` | Inheritance hierarchy | Tree-sitter AST | 1.0 | `DETERMINISTIC` | Yes |
| `IMPLEMENTS` | `:Class` | `:Interface` | Interface implementation | Tree-sitter AST | 1.0 | `DETERMINISTIC` | Yes |
| `IMPORTS` | `:File` | `:Module` / `:File` / `:Function` | Source code import statement | Tree-sitter + Path Resolver | 1.0 | `DETERMINISTIC` | Yes |
| `CALLS` | `:Function` / `:Method` | `:Function` / `:Method` | Invocation of callee by caller | Tree-sitter AST + Call Resolver | 0.95 (internal resolved) / 0.70 (bare name) | `DETERMINISTIC` / `INFERRED` | Yes |
| `TESTS` | `:Test` | `:Function` / `:Method` / `:Class` | Test suite targets entity | AST test pattern + imports | 0.85 | `INFERRED` | Yes |
| `MODIFIES` | `:Commit` | `:File` | Commit touched file | `git log --raw` | 1.0 | `DETERMINISTIC` | Yes |
| `CONTAINS` | `:PullRequest` | `:Commit` | PR contains git commit | GitHub PR Commits API | 1.0 | `DETERMINISTIC` | Yes |
| `CHANGES` | `:PullRequest` | `:File` | PR diff touches file | GitHub PR Files API | 1.0 | `DETERMINISTIC` | Yes |
| `FIXES` | `:PullRequest` | `:Issue` | PR closes or fixes issue | Commit message / PR body regex (e.g. `Fixes #12`) | 0.95 | `DETERMINISTIC` | Yes |
| `RELATED_TO`| `:Issue` | `:PullRequest` | Issue and PR cross-referenced | GitHub timeline event / LLM | 0.80 | `INFERRED` | Yes |

---

## 7. Provenance & Confidence Architecture

Every relationship in the knowledge graph must carry metadata describing its origin and confidence score:

```cypher
(:Function {name: "executePayment"})-[:CALLS {
  source: "DETERMINISTIC",
  confidence: 1.0,
  file_path: "src/billing/service.py",
  line: 42,
  extractor: "tree-sitter-python",
  commit_sha: "9a2f1b..."
}]->(:Function {name: "chargeCard"})
```

### Provenance Classification Levels

1. **`DETERMINISTIC` (Confidence: 1.0):**
   - Grounded in strict AST syntax, package manifests, or Git plumbing commands.
   - Examples: `DEFINES`, `CONTAINS`, `MODIFIES`, `IMPORTS` (resolved to file), `CONTAINS_COMMIT`.
2. **`INFERRED` (Confidence: 0.60 – 0.95):**
   - Grounded in deterministic heuristics or pattern matching that may have ambiguity.
   - Examples: Call matching by bare name without complete type information, `TESTS` mapping via naming convention (`test_foo -> foo`), or `FIXES` extracted via regex from PR bodies.
3. **`SEMANTIC` (Confidence: 0.50 – 0.89):**
   - Inferred by an LLM or embedding similarity search.
   - Examples: Architecture boundary detection, Issue affecting a microservice, or PR similarity clusters.
   - Must include `model`, `evidence_snippet`, and `created_at` in edge properties.
