# ADR 0001: Unified Zero-Disk Incremental Ingestion Engine

> **Status:** Accepted  
> **Date:** November 2026  
> **Deciders:** Aryan Racha, System Architect  
> **Consulted:** `docs/architecture/solutions-and-implementation-guide.md`  

---

## Context & Problem Statement

Gitami indexes codebases into a dual-engine Knowledge Base (Neo4j structural AST graph + ChromaDB semantic vector embeddings). 

Prior to this decision, incremental reindexing was fractured:
1. `RepositoryIndexer.run_incremental(...)` strictly required an on-disk Git clone (`git.Repo`), while remote GitHub repositories streamed in-memory tarballs in `routes/ingest.py`.
2. PR merge webhooks in `apps/api/src/modules/github/webhook.service.ts` bypassed job tracking, omitted GitHub installation tokens, and either failed or triggered full $O(N)$ wiping rebuilds.
3. Partial failures in third-party embedding APIs (e.g. Gemini 429 quota exhaustion) risked corrupting the dual-store state without a self-healing consistency model.

---

## Decision Drivers

- **Zero-Disk Invariant:** The Python AI intelligence service must remain a stateless worker container without volume provisioning or local disk cleanup overhead.
- **Sub-3s PR Re-Indexing:** Merged PRs touching a handful of files must update AST nodes, caller edges, and vector embeddings in under 3 seconds without full repo rebuilds.
- **Dual-Store Resilience:** Graph queries (blast radius, security linting) must remain available even if third-party vector embedding quotas are temporarily throttled.
- **Unified Observability:** Both manual UI builds and automated webhook re-indexing must report real-time stage progress through the same database state machine.

---

## Considered Options

1. **Option 1: Ephemeral Local Git Clones with Global Re-resolution**
   - Workers clone repositories into `/tmp` and run local `git diff`.
   - On change, wipe and re-resolve all cross-file call edges repo-wide.
   - *Rejected:* Heavy disk churn, container storage exhaustion risks, and $O(N)$ graph traversal on every PR merge.

2. **Option 2: Unified Zero-Disk Ingestion with Two-Phase Edge Reconciliation (Selected)**
   - Use GitHub Compare Commits API (`GET /repos/{owner}/{repo}/compare/{base}...{head}`) to fetch changed file lists and stream modified contents into memory over HTTPS.
   - Reconcile caller edges in two phases: query Neo4j for incoming callers, re-parse the delta, and re-link only the affected caller files ($O(\Delta + \text{affected})$).
   - Use a compensating state pointer (`DEGRADED_VECTOR`) to handle ChromaDB embedding throttles without invalidating Neo4j graph integrity.
   - Stream real-time stage progress over NDJSON to Bun control plane.

---

## Decision Outcome

We selected **Option 2**. The ingestion engine will be implemented with the following specifications:

### 1. Zero-Disk Remote Differ & Snapshot
- Implement `GitHubApiDiffer` implementing `IDiffProvider` to compute file deltas (`added`, `modified`, `deleted`, `renamed`) via GitHub Compare Commits API.
- Implement `RemoteGitHubSnapshot` implementing `ISnapshotProvider` to stream only modified and added file bytes directly into memory via raw GitHub contents API.

### 2. Two-Phase Graph Edge Reconciliation
- Phase 1: Query Neo4j for all callers pointing to symbols in the modified/deleted files:
  ```cypher
  MATCH (caller:Symbol)-[r:CALLS]->(target:Symbol)
  WHERE target.file_path IN $modified_paths
  RETURN DISTINCT caller.file_path AS affected_caller_file
  ```
- Phase 2: Delete old file symbols and outgoing edges. Re-parse the modified files and re-parse *only* the affected caller files to re-link incoming `[:CALLS]` relationships.

### 3. Self-Healing Dual-Store Consistency Contract
- Write Neo4j first, then batch embeddings into ChromaDB.
- Advance `indexed_commit_sha` in `RepositoryIndexState` only when both succeed.
- If ChromaDB fails (e.g. 429 quota exhaustion), mark state as `status = 'DEGRADED_VECTOR'`. Neo4j graph queries remain 100% active, and a background retry task pushes the pending embedding batch without re-parsing ASTs.

### 4. Dynamic Safety Threshold
- The engine automatically falls back to a clean full rebuild if:
  - More than 50 files or >25% of repository files were modified.
  - A force-push / non-fast-forward merge occurred.
  - Root project module configuration (`tsconfig.json`, `package.json`, `pyproject.toml`) was altered.

### 5. Unified NDJSON Stage Streaming Protocol
- Bun control plane triggers incremental sync via `POST /api/reindex` passing `{ repo_id, full_name, access_token, base_commit_sha, target_commit_sha, branch }`.
- Bun creates an `index_jobs` row with `type = "INCREMENTAL"` and consumes FastAPI's NDJSON stream (`DIFF` ➔ `AST_PARSE` ➔ `GRAPH_SYNC` ➔ `VECTOR_SYNC` ➔ `COMPLETED`) to update PostgreSQL in real time.

---

## Consequences

### Positive
- **Stateless Infrastructure:** Python worker containers require zero persistent storage or volume mounts.
- **Fast PR Reindexing:** Incremental sync completes in <2.5 seconds on average PR merges.
- **Fault-Tolerant Vector Storage:** Transient third-party LLM embedding limits do not cause graph downtime or PR review blockages.
- **Single Observable Pipeline:** Full UI builds and webhook incremental syncs share the exact same progress streaming and database state transitions.

### Negative / Trade-Offs
- Dependent on GitHub API availability and rate limits (mitigated by using GitHub App installation tokens with 5,000 req/hr quotas).
- Transient eventual consistency window for semantic vector queries if embedding APIs are experiencing 429 rate limits.
