# Incremental Repository Indexing

> **Status:** Architecture Design Document  
> **Date:** September 2026  
> **Scope:** Precision incremental re-indexing pipeline for git commits, delta graph updates, vector synchronization, and failure recovery.

---

## 1. Overview & Objectives

Full re-indexing of large repositories on every git push is computationally prohibitive, slow, and expensive. Incremental indexing processes only the **delta** between the previously indexed commit (`A`) and the newly pushed commit (`B`):

$$\Delta = \text{git diff } A \dots B$$

The incremental indexing pipeline updates:
1. **Source Code Knowledge Graph (Neo4j):** Only added/modified/deleted files, symbols, and their immediate relationship neighborhoods.
2. **Vector Knowledge Base:** Only modified or added symbol embeddings, with targeted deletion of stale embeddings.
3. **Git History & Metadata:** Appends new `:Commit` nodes and updates modified PR/Issue links.
4. **State Machine (PostgreSQL):** Atomically rolls forward `indexed_commit_sha` from $A \to B$.

---

## 2. The Incremental Pipeline

```
Commit A (Already Indexed) ──► New Push: Commit B
                                     │
                                     ▼
                       [1] git diff --name-status A B
                                     │
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
          [Added Files]       [Modified Files]     [Deleted / Renamed]
                │                    │                    │
                ▼                    ▼                    ▼
          Parse New AST       Diff AST Symbols     Remove File & Symbols
          Extract Entities    Purge Stale Symbols  Detach Graph Edges
          Create New Edges    Re-link Call Edges   Delete Vector Docs
                │                    │                    │
                └────────────────────┼────────────────────┘
                                     │
                                     ▼
                     [2] Re-resolve Neighborhood
                         (Affected Caller / Importer Nodes)
                                     │
                                     ▼
                     [3] Dual Vector Synchronization
                         (Delete Old Chunks, Batch Embed New)
                                     │
                                     ▼
                     [4] Git & Metadata Append
                         (Add Commit Nodes, Link Commits)
                                     │
                                     ▼
                     [5] Atomic State Roll-Forward
                         (PostgreSQL: indexed_commit_sha = B)
```

---

## 3. File-Level Change Handling

Given `git diff --name-status A B`, every changed file is classified into one of four actions:

### 3.1 Added Files (`status == 'A'`)
1. **AST Extraction:** Parse file via Tree-sitter. Extract classes, functions, methods, interfaces, calls, and imports.
2. **Neo4j Upsert:**
   - Create `:File` node with `file_path`, `language`, and `sha256`.
   - Create all extracted entity nodes (`:Class`, `:Function`, `:Method`).
   - Create `:File -[:DEFINES]-> :Symbol` edges.
   - Create internal `:CALLS` edges where callees exist in the graph.
3. **Import Resolution:** Connect outgoing `IMPORTS` and `DEPENDS_ON_FILE` edges to existing target files/symbols. Connect other files that were waiting on this file.
4. **Vector DB Upsert:** Clean and batch-embed newly extracted symbols.

### 3.2 Modified Files (`status == 'M'`)
A modified file may have gained new functions, altered existing signatures, or deleted obsolete methods.
1. **AST Diffing:** Parse new file version to get `NewSymbols` and `NewEdges`. Fetch existing symbols for `file_path` from Neo4j (`OldSymbols`).
2. **Symbol Reconcile:**
   - **Deleted Symbols:** In `OldSymbols` but not in `NewSymbols`. Delete their `:Symbol` nodes, detach edges, and delete from Vector DB.
   - **Modified Symbols:** In both, but code or signature changed. Update properties (`signature`, `start_line`, `end_line`, `docstring`, `code_body`), re-embed in Vector DB, and re-wire outgoing `CALLS`.
   - **Added Symbols:** In `NewSymbols` but not in `OldSymbols`. Insert node, add `DEFINES` edge, embed in Vector DB, and wire calls.
3. **Edge Re-wiring:** Re-evaluate `CALLS` and `IMPORTS` originating from the file. Remove stale edges and add newly introduced calls.

### 3.3 Deleted Files (`status == 'D'`)
1. **Graph Detachment:**
   - Find all symbols defined by the file:
     ```cypher
     MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $file_path})
     OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
     DETACH DELETE f, s
     ```
   - All incoming and outgoing relationships (`CALLS`, `IMPORTS`, `DEPENDS_ON_FILE`) are safely deleted by `DETACH DELETE`.
2. **Neighborhood Invalidation:** Incoming `IMPORTS` from other files are transformed into unresolved external `:Package` stubs or marked as broken references.
3. **Vector DB Deletion:** Purge all vector entries matching `{ repo: $repo_id, branch: $branch, file_path: $file_path }`.

### 3.4 Renamed Files (`status == 'R'`)
Git provides `old_path` and `new_path`.
1. **Atomic Path Migration:**
   ```cypher
   MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $old_path})
   SET f.file_path = $new_path
   WITH f
   MATCH (f)-[:DEFINES]->(s:Symbol)
   SET s.file_path = $new_path,
       s.qualified_name = replace(s.qualified_name, $old_path + "::", $new_path + "::")
   ```
2. **Edge Path Updates:** Update `file_path` properties on all outgoing and incoming call edges.
3. **Import Graph Fixup:** Rerun `resolve_repo_imports` for files that imported `old_path`.
4. **Vector Document ID Migration:** Delete entries for `old_path` and insert with updated `new_path` keys.

---

## 4. Graph Neighborhood Re-Resolution

When a symbol signature or file path changes, downstream callers in other files may be affected.

1. **Find Direct Inbound Dependents:**
   ```cypher
   MATCH (caller:Symbol)-[r:CALLS]->(target:Symbol {qualified_name: $changed_symbol})
   RETURN DISTINCT caller.file_path AS affected_file
   ```
2. **Re-validate Calls:**
   - If `target` was deleted, remove `CALLS` relationship.
   - If `target` parameter signature changed, flag potential type/signature mismatches for the Code/Review Agent.

---

## 5. Vector Database Delta Synchronization

Vector databases must remain in lockstep with Neo4j to prevent stale retrieval (e.g. retrieving code for a function that was deleted).

### 5.1 Deterministic Document Keys
Each vector entry uses a deterministic ID:
$$\text{doc\_id} = \text{code}\_\{repo\}\_\{branch\}\_\{file\_path\}\_\{symbol\}\_\{start\_line\}$$

### 5.2 Atomic Batch Update Sequence
1. Collect list of `stale_doc_ids` (from deleted symbols and files).
2. Collect list of `upsert_entries` (new or modified symbols).
3. Execute:
   ```python
   if stale_doc_ids:
       vector_client.delete_by_ids(stale_doc_ids)
   if upsert_entries:
       vector_client.add_code_entries_batch(upsert_entries)
   ```

---

## 6. Safe Recovery & Atomicity Guarantees

### 6.1 Atomic State Roll-Forward
Incremental updates must be all-or-nothing.
1. All Neo4j writes for the batch execute inside an active Cypher transaction or explicit rollback block.
2. Vector DB writes execute with automatic single-batch retry.
3. Only when both writes report `SUCCESS`, the Index Worker commits the new state to PostgreSQL:
   ```sql
   UPDATE repository_index_states
   SET indexed_commit_sha = $target_commit_sha,
       status = 'READY',
       last_indexed_at = NOW(),
       updated_at = NOW()
   WHERE repository_id = $repo_id AND branch = $branch;
   ```

### 6.2 Failure Scenarios & Fallbacks

| Failure Mode | Cause | Recovery Strategy |
|---|---|---|
| **Base Commit Missing** | Shallow clone lacks base commit `A` | Worker runs `git fetch --depth=100` or full clone; if still unavailable, trigger full `REINDEX`. |
| **Git History Divergence** | Force push (`git push --force`) rewrote commit history | `git merge-base A B` fails. Index Manager marks job as `REINDEX_REQUIRED` and launches full `INITIAL` indexing. |
| **AST Parser Crash** | Syntax error in partial or malformed file | Skip problematic file, record error in `IndexJob.error`, index remaining files, and report partial success. |
| **Neo4j Network Error** | Database connection dropped during Cypher execution | Exponential backoff retry (3x). If database unreachable, mark job `FAILED` and release queue lock. State in Postgres remains at `A`. |
| **Vector DB Rate Limit** | Embedding API quota exceeded | Pause worker with exponential backoff (e.g. 30s). Resume from failed batch index. |
