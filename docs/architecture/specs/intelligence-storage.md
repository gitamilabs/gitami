# Project Intelligence Storage Boundaries

> **Status:** Architecture Design Document  
> **Date:** September 2026  
> **Scope:** Definition of data storage boundaries across PostgreSQL, Neo4j, Vector DB, and Object Storage.

---

## 1. Storage Architecture Overview

Gitami uses a **polyglot persistence architecture**. Each storage engine is chosen for its specific strengths:
- **PostgreSQL:** ACID transactional state, relational hierarchies, job orchestration, security, and auth.
- **Neo4j:** Multi-hop structural code graphs, call/import dependencies, cross-repository topologies, and blast-radius graph traversals.
- **Vector DB:** High-dimensional semantic search over documentation, code summaries, and unstructured discussion threads.
- **Object Storage (S3/R2):** Ephemeral artifacts, raw diff patches, large CI/build logs, and snapshot backups.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Gitami Data Subsystems                            │
└──────┬───────────────────┬──────────────────────┬────────────────────┬──────┘
       │                   │                      │                    │
       ▼                   ▼                      ▼                    ▼
 ┌────────────┐     ┌─────────────┐        ┌─────────────┐      ┌─────────────┐
 │ PostgreSQL │     │    Neo4j    │        │  Vector DB  │      │ Object Store│
 │ (Relational│     │ (Knowledge  │        │ (Semantic   │      │ (Blobs &    │
 │  & State)  │     │   Graph)    │        │  Embeddings)│      │  Artifacts) │
 └────────────┘     └─────────────┘        └─────────────┘      └─────────────┘
```

---

## 2. Storage Boundaries & Classification Matrix

| Data Entity / Domain | Primary Storage | Secondary / Projected | Rationale & Consistency Model |
|---|---|---|---|
| **Organizations & Workspaces** | PostgreSQL | Neo4j (virtual node) | Strict RBAC, billing, relational consistency, and tenant isolation. |
| **Users & Credentials** | PostgreSQL | None | Sensitive security data, OAuth tokens, password hashes. Must never touch graph or vector stores. |
| **Teams & Memberships** | PostgreSQL | Neo4j (Ownership edge) | User authorization and RBAC managed relationally; team code-ownership edges projected to Neo4j. |
| **Projects** | PostgreSQL | Neo4j (`:Project` node) | Project is the central boundary uniting multiple repositories. Projected into Neo4j for cross-repo queries. |
| **Connected Repositories** | PostgreSQL | Neo4j (`:Repository`) | GitHub App credentials & webhooks in Postgres; topological root node in Neo4j. |
| **Index Jobs & State** | PostgreSQL | None | Job queue, progress counters, retries, and atomic `indexed_commit_sha` tracking. Relational transactions required. |
| **Agent Runs & Feedback** | PostgreSQL | Vector DB (summaries) | Audit logs, token consumption, run status in Postgres; high-level summaries embedded for historical agent retrieval. |
| **Code Entities (Classes, Funcs)** | Neo4j | Vector DB (summaries) | Structural hierarchy and call graphs require fast multi-hop traversal in Neo4j. Symbol signatures & bodies embedded in Vector DB. |
| **Dependencies & Imports** | Neo4j | PostgreSQL (package lock) | File-to-file, file-to-symbol, and package dependency links belong strictly in the graph. |
| **Commit Relationships** | Neo4j | PostgreSQL (PR commit list) | `:Commit` nodes, `:MODIFIES` edges to `:File`, and parent-child commit DAGs require graph traversals. |
| **Cross-Repo Relationships** | Neo4j | None | API contracts, shared client libraries, and cross-repo event producers/consumers are graph traversals across `:Repository` nodes. |
| **Service & Database Topologies** | Neo4j | None | Architecture diagrams, god nodes, circular service dependencies, and community clusters. |
| **Documentation & ADRs** | Vector DB | Object Storage (raw md) | Semantic search for answering architectural and design questions. Raw markdown backed up in object store. |
| **Issue & PR Discussions** | Vector DB | PostgreSQL (metadata) | Thread comments, code review comments, and rationales embedded for semantic context search. |
| **Runbooks & Guidelines** | Vector DB | None | Coding standards, operational runbooks, and convention guidelines for agent prompt augmentation. |
| **Large CI / Test Logs** | Object Storage | PostgreSQL (URL pointer) | Large raw logs (1MB - 100MB+) should not bloat relational tables or graph nodes. |
| **Raw Diff Patches & Dumps** | Object Storage | PostgreSQL (short diffs) | Multi-megabyte pull request diffs and raw tarballs stored in S3/R2 with signed URLs. |

---

## 3. Detailed Engine Specifications

### 3.1 PostgreSQL (Relational Control Plane)

**Core Schema Groups:**
1. **Tenancy & Auth:**
   - `organizations`, `users`, `teams`, `organization_memberships`, `team_memberships`.
2. **Project & Repo Topology:**
   - `projects` (ID, org_id, name, slug, settings).
   - `connected_repositories` (ID, project_id, installation_id, github_repo_id, full_name, default_branch, is_active).
3. **Indexing State Machine:**
   - `index_jobs` (ID, project_id, repository_id, type, base_sha, target_sha, status, progress, error, retry_count, timestamps).
   - `repository_index_states` (repository_id, branch, indexed_commit_sha, status, counts, schema_version).
4. **Pull Requests & Agents:**
   - `pull_requests` (repo_id, pr_number, title, base_sha, head_sha, state, status).
   - `pr_reviews` (pull_request_id, verdict, risk_score, summary, rationale, raw_json).
   - `pr_issues` (review_id, title, category, severity, file_path, line, suggested_fix).
   - `agent_runs` (id, agent_type, trigger, input_context, output_response, token_cost).

**Key Indexing Patterns:**
- B-Tree on `(project_id, repository_id)`.
- Unique constraints on `(repository_id, branch)` for `repository_index_states`.
- Index on `(status, created_at)` for fast queue polling by workers.

---

### 3.2 Neo4j (Project Knowledge Graph)

**Primary Responsibilities:**
- Code Structure: AST hierarchy (`:File -> :Class -> :Method`), inheritance (`:Class -[:EXTENDS]-> :Class`), and interface implementation.
- Call & Import Graph: `:Function -[:CALLS]-> :Function`, `:File -[:IMPORTS]-> :Symbol`.
- Git Topology: `:Commit -[:MODIFIES]-> :File`, `:Commit -[:PARENT]-> :Commit`.
- GitHub Links: `:PullRequest -[:CHANGES]-> :File`, `:PullRequest -[:FIXES]-> :Issue`.
- Cross-Repository Links: `:Service -[:DEPENDS_ON]-> :Service`, `:File -[:CALLS_API]-> :Endpoint`.

**Tenant & Scope Isolation Rules:**
- Every node must carry `repo_id` and `branch`.
- Top-level entities (`:Repository`, `:Service`, `:Database`) carry `project_id`.
- Graph queries use strict parameter scoping:
  ```cypher
  MATCH (s:Symbol {repo_id: $repo_id, branch: $branch}) ...
  ```

---

### 3.3 Vector Database (Semantic Knowledge)

**Supported Backends:** ChromaDB, Qdrant, Pinecone, Supabase pgvector.

**Content Collections & Partitioning:**
1. **`code_symbols` Collection:**
   - Embedded content: Symbol signature, docstring, parameter types, and cleaned implementation body.
   - Metadata filter: `{ project_id, repo, branch, file_path, content_type: "code", commit_hash }`.
2. **`documentation` Collection:**
   - Embedded content: Markdown files (`README.md`, `docs/**/*.md`, ADRs, architecture specs).
   - Chunking: Markdown semantic chunking (headers and code blocks preserved).
   - Metadata filter: `{ project_id, repo, file_path, content_type: "doc" }`.
3. **`github_threads` Collection:**
   - Embedded content: Issue problem descriptions, PR summaries, review discussions, and resolution notes.
   - Metadata filter: `{ project_id, repo, issue_id, pr_id, content_type: "issue" | "pr" }`.

---

### 3.4 Object Storage (S3 / Cloudflare R2)

**Bucket Organization:**
- `gitami-diffs/{project_id}/{repo_id}/{pr_number}_{head_sha}.diff`
- `gitami-tarballs/{repo_id}/{commit_sha}.tar.gz`
- `gitami-logs/{job_id}/execution.log`
- `gitami-snapshots/{project_id}/{timestamp}_graph_backup.json`

**Access Pattern:** Pre-signed URLs generated by API Service with short (15-minute) TTLs.

---

## 4. Cross-System Consistency & Synchronization

1. **Dual-Write Orchestration:**
   - The `IndexWorker` manages updates to Neo4j and Vector DB.
   - Updates are non-destructive and staged against the target `commit_sha`.
2. **Atomic Roll-Forward:**
   - The PostgreSQL `repository_index_states.indexed_commit_sha` is updated only when both Neo4j and Vector DB writes report success.
   - Read queries from Agents always read the knowledge base using the commit SHA confirmed in `repository_index_states`.
3. **Orphan Cleanup:**
   - A weekly background garbage collection job scans Neo4j and Vector DB for document IDs and nodes belonging to inactive repositories or deleted branches.
