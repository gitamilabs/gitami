# Gitami V1 Incremental Indexing Architecture Specification

> **Document Version:** 1.0.0  
> **Status:** Approved Target Architecture  
> **Domain:** Project Intelligence — Incremental Repository Indexing  
> **Date:** September 2026  
> **Target Services:** `apps/ai` (Python Intelligence Worker), `apps/api` (Control Plane), Neo4j Graph DB, Vector DB

---

## 1. Goals & Principles

Full repository re-indexing on every git push is computationally prohibitive, slow ($O(N)$ where $N$ is repository size), and wasteful. Incremental indexing reduces this complexity to $O(\Delta + \text{affected})$, indexing only the precise delta of code modified between two commits.

### Primary Goals
1. **Precision Delta Processing:** Given commit $A$ (currently indexed) and commit $B$ (new push target), process only files and AST entities that were added, modified, deleted, or affected by changes.
2. **Deterministic Convergence:** Running an incremental index from $A \to B$ must produce the exact same graph and vector state as a full re-index of commit $B$ from scratch.
3. **Strict Graph Integrity:** No orphaned nodes, dangling edges, stale versions of deleted functions, or duplicate relationships may remain in Neo4j after an incremental run.
4. **Decoupled Semantic Synchronization:** Deterministic AST/code graph updates are executed first; vector database embeddings for affected symbols are synchronized second without blocking core graph consistency.
5. **Robust Concurrency & Ordering:** Prevent out-of-order execution (e.g. an older push to commit $B$ completing after a newer push to commit $C$).

---

## 2. Non-Goals

1. **Temporal Graph Event Sourcing:** We are **not** building a bi-temporal or append-only graph that preserves every version of every function across all historical commits inside Neo4j. The code graph represents the **current canonical state** of a repository branch. Git itself remains the immutable versioned storage engine.
2. **Heuristic Fuzzy Rename Detection:** We do not attempt deep AST semantic similarity matching to detect moved functions across files if git did not recognize the file rename. Renames follow deterministic git change status.
3. **Cross-Repository Dynamic Linking in V1:** Incremental indexing operates at the Repository boundary; cross-repository symbol resolution across the Project Intelligence layer is executed as a separate post-index aggregation step.
4. **Interactive Graph Rollbacks:** We do not compute reverse diffs for historical rollback; if a branch rolls back to a previous commit, the indexer applies standard incremental delta or falls back to full indexing.

---

## 3. Full vs. Incremental Indexing

| Property | Full Indexing (`IndexJobType.INITIAL / REINDEX`) | Incremental Indexing (`IndexJobType.PUSH`) |
| :--- | :--- | :--- |
| **Input** | Explicit commit SHA $B$ + complete tree snapshot | Previous commit $A$ + Target commit $B$ + Git diff delta |
| **Discovery** | Exhaustive filesystem walk via `FileDiscovery` | `git diff --name-status A B` |
| **Parsing** | Every eligible source file parsed into AST | Only added, modified, and impacted dependent files |
| **Graph Operations** | Complete repository schema setup & mass upsert | Targeted node upserts, stale entity deletions, edge rewiring |
| **Complexity** | $O(N)$ files, $O(S)$ symbols | $O(\Delta)$ changed files + $O(K)$ affected files |
| **Duration (100k LOC)** | ~15–45 seconds | ~200ms–1.5 seconds |
| **When Used** | Repository onboarding, schema migration, disaster recovery | Continuous CI / Git push webhooks / PR synchronizations |

---

## 4. Commit Tracking & Entity Identity Audit

### 4.1 Entity Identity vs. Entity Observation

A fundamental architectural pitfall is conflating **Entity Identity** with an **Entity Observation**:
- **Entity Identity (`uid`):** The stable, logical identity of a code artifact within a repository. A function `validate_user` in `apps/api/src/auth.ts` remains the *same logical entity* across commits even when its signature or implementation changes.
- **Entity Observation / Version:** The transient state of an entity at commit $B$ (e.g. `commit_sha = B`, `start_line = 45`, `lines_of_code = 22`).

In Gitami V1:
- Node UIDs **must not** contain commit SHAs or line numbers.
- Node properties (`commit_sha`, `signature`, `docstring`, `indexed_at`) record the observation at the target commit.
- Edge UIDs (where applicable) and relationships connect stable entity UIDs.

### 4.2 Comprehensive UID Strategy Audit

The current V1 UID formula:
$$\text{UID} = \text{kind} : \text{repo\_id} : \text{norm\_path} :: [\text{parent}.]\text{name}$$

#### Audit Case Matrix

| Case | Scenario | Current Behavior | Verdict & Corrective Design |
| :--- | :--- | :--- | :--- |
| **Overloaded Functions** | TypeScript: 2 signatures + 1 implementation in same file | Collides: both produce `func:repo:file::parse` | **Corrected:** Disambiguate overloads by parameter arity/signature index: `func:repo:file::parse#0`, `#1`. Implementation takes canonical root UID. |
| **Methods in Different Classes** | `User.save()` vs `Order.save()` in `models.py` | `method:repo:models.py::User.save`<br>`method:repo:models.py::Order.save` | **Robust:** No collision. Class parent qualification separates them. |
| **Nested Classes** | `class Outer:` $\to$ `class Inner:` | Current code only passes `parent` for methods | **Corrected:** Support hierarchical parents for classes: `class:repo:file::Outer.Inner`. |
| **Nested / Local Functions** | `def outer():`<br>`  def helper():` | `func:repo:file::helper` collides if multiple scopes define `helper` | **Corrected:** Parent scope qualification: `func:repo:file::outer.helper`. |
| **Anonymous Functions** | Callback: `items.map(x => x)` | Ignored or assigned `<anonymous>` | **Robust:** Anonymous callbacks without variable bindings are excluded from top-level graph entities; arrow functions assigned to `const foo = () => {}` are named `foo`. |
| **Interfaces & Types** | `interface User` and `type User` in same file | `interface:repo:file::User`<br>`type:repo:file::User` | **Robust:** Distinct `kind` prefixes prevent collision. |
| **Tests** | `test("renders")` in 2 different suites in same file | Collides if test name is identical | **Corrected:** Qualify with describe suite: `test:repo:file::HeaderSuite.renders`. |
| **Moved Symbol** | `func foo` moved from `a.py` $\to$ `b.py` | Old UID in `a.py` deleted, new UID in `b.py` created | **Correct:** Lexical residence changes; edges rewire cleanly. |
| **Renamed Symbol** | `calculate()` $\to$ `compute()` in `math.py` | Old deleted, new created | **Correct:** Reconciled via AST diffing. |
| **Renamed File** | `utils.ts` $\to$ `tools.ts` | Old file + symbols deleted, new created | **Correct:** Managed via git rename detection. |

---

## 5. Changed-File Detection & Classification

The incremental pipeline executes `git diff --name-status -M A B` to inspect changes between commit $A$ and $B$.

```
                        git diff --name-status -M A B
                                      │
         ┌───────────────┬────────────┴───┬───────────────┐
         ▼               ▼                ▼               ▼
      Added          Modified          Deleted         Renamed
    [Status A]      [Status M]       [Status D]      [Status R]
```

### Action Matrix per File Status

| Git Status | Pipeline Action | Graph Node Impact | Relationship Impact |
| :--- | :--- | :--- | :--- |
| **ADDED (`A`)** | 1. Parse AST.<br>2. Extract symbols & calls.<br>3. Stage vector embeddings. | Create `:File`, `:Class`, `:Function`, `:Method`. | Wire `:Repository -[:CONTAINS]-> :File`, `:File -[:DEFINES]-> :Symbol`, outgoing `:CALLS` & `:IMPORTS`. |
| **MODIFIED (`M`)** | 1. Parse new AST.<br>2. Diff against existing symbols.<br>3. Update modified nodes.<br>4. Delete stale nodes. | Update properties (`signature`, `lines`). Purge removed symbols. | Recalculate outgoing `:CALLS` and `:IMPORTS`. Existing incoming edges to unmodified symbols remain intact. |
| **DELETED (`D`)** | 1. Stage symbol deletions.<br>2. Purge from vector DB.<br>3. Delete file and defined entities. | `DETACH DELETE` `:File` and all child symbols. | All relationships (`CONTAINS`, `DEFINES`, `CALLS`, `IMPORTS`) cascade deleted. |
| **RENAMED (`R`)** | 1. Git reports `old_path -> new_path`.<br>2. If content changed, re-parse.<br>3. Re-index under new path. | Delete old `:File` & symbols; create new `:File` & symbols (or atomic rename). | Rewire `:IMPORTS` pointing to old module path to new module path. |
| **COPIED (`C`)** | Treat as `ADDED` at target destination path. | Create separate `:File` and symbol nodes. | Independent new relationships. |

---

## 6. Affected-File & Dependency Impact Analysis

When a file `B.py` is modified or deleted, files that depend on `B.py` may become syntactically or semantically invalid even if they were not touched in the git commit.

```
┌────────────────────────────────────────────────────────┐
│                   Impact Layering                      │
├────────────────────────────────────────────────────────┤
│ Layer 0: DIRECTLY CHANGED FILES                        │
│          Files appearing in git diff (A, M, D, R).     │
├────────────────────────────────────────────────────────┤
│ Layer 1: DIRECT DEPENDENTS (Immediate Fan-In)          │
│          Files that directly IMPORT or EXTEND Layer 0. │
├────────────────────────────────────────────────────────┤
│ Layer 2: INDIRECT CALLERS (Transitive Call Neighborhood)│
│          Methods/Functions invoking modified symbols.  │
└────────────────────────────────────────────────────────┘
```

### Affected Set Algorithm

```python
def compute_affected_files(graph_client, repo_id: str, directly_changed_files: List[str]) -> Set[str]:
    """
    Computes the set of affected files requiring relationship re-resolution.
    Uses Neo4j graph traversal of IMPORTS, EXTENDS, and IMPLEMENTS edges.
    """
    query = """
    UNWIND $changed_files AS changed_path
    MATCH (target:File {repo_id: $repo_id, file_path: changed_path})
    OPTIONAL MATCH (target)<-[:DEFINES]-(:Symbol)<-[:IMPORTS]-(importer:File {repo_id: $repo_id})
    OPTIONAL MATCH (target)<-[:DEFINES]-(:Class)<-[:EXTENDS|IMPLEMENTS]-(:Class)<-[:DEFINES]-(child_file:File {repo_id: $repo_id})
    RETURN collect(DISTINCT importer.file_path) + collect(DISTINCT child_file.file_path) AS affected_paths
    """
```

### Reprocessing Policy for Affected Files
- **Directly Changed Files:** Full AST re-parse, symbol diffing, entity upsert/delete, outgoing and incoming edge rewiring.
- **Affected Files (Layer 1):** Do **not** re-extract internal symbols. Only re-evaluate their **outgoing** `IMPORTS`, `CALLS`, and `EXTENDS` edges against the updated target symbols to maintain graph consistency.

---

## 7. AST & Graph Reconciliation (Stale Entity Detection)

When a file `service.py` is modified, we must reconcile the old symbol set with the new symbol set.

### 7.1 Reconciliation Mathematical Model

Let $S_{\text{old}}$ be the set of entity UIDs previously defined by `file_path` in Neo4j.  
Let $S_{\text{new}}$ be the set of entity UIDs extracted from the new commit AST.

$$\Delta_{\text{reconcile}} = \begin{cases}
S_{\text{create}} = S_{\text{new}} \setminus S_{\text{old}} & \text{(New symbols to insert)} \\
S_{\text{delete}} = S_{\text{old}} \setminus S_{\text{new}} & \text{(Stale symbols to DETACH DELETE)} \\
S_{\text{update}} = S_{\text{new}} \cap S_{\text{old}} & \text{(Existing symbols to update properties)}
\end{cases}$$

### 7.2 Cypher Reconciliation Queries

#### Step 1: Query Old UIDs for the File
```cypher
MATCH (f:File {repo_id: $repo_id, file_path: $file_path})-[:DEFINES]->(s)
RETURN s.uid AS uid, labels(s) AS labels
```

#### Step 2: Delete Stale Entities ($S_{\text{delete}}$)
```cypher
UNWIND $stale_uids AS stale_uid
MATCH (s {uid: stale_uid})
DETACH DELETE s
```

#### Step 3: Upsert Active Entities ($S_{\text{create}} \cup S_{\text{update}}$)
Execute standard `UNWIND $batch AS item MERGE (e:Label {uid: item.uid}) SET ...`

---

## 8. Graph Deletion & Cascade Semantics

When code is removed, graph cleanup must follow strict cascade semantics:

```
[Deleted File] 
     │ (DETACH DELETE)
     ├──► Deletes :File node
     ├──► Deletes all :CONTAINS relationships from :Repository
     ├──► Deletes all child symbols (:Class, :Function, :Method)
     ├──► Deletes all outgoing :CALLS and :IMPORTS edges
     └──► Deletes all incoming :CALLS to deleted symbols
```

### Invalidation vs Deletion for External Callers
If function `foo()` in `a.py` called `bar()` in `b.py`, and `b.py` deletes `bar()`:
- The edge `(foo)-[:CALLS]->(bar)` is deleted when `bar` is `DETACH DELETE`d.
- Caller `foo` remains intact.
- An indexing warning is recorded: `"Dangling invocation from a.py::foo to deleted target b.py::bar"`.

---

## 9. Idempotency & Convergence

### The Idempotency Invariant
For any repository $R$, base commit $A$, and target commit $B$:
$$\text{Index}(R, A \to B) \equiv \text{Index}(R, \emptyset \to B)$$
Executing an incremental indexing run multiple times with the same input parameters must yield identical graph and database states:
1. `MERGE` statements on unique `uid` properties guarantee that repeat executions do not create duplicate nodes.
2. Relationships are merged on source UID, target UID, and relationship type (`MERGE (source)-[r:TYPE]->(target)`), with volatile metadata applied via `SET`.
3. Retrying a failed incremental run cleans up partial writes because it re-computes $S_{\text{delete}}$ and re-applies $S_{\text{update}}$.

---

## 10. RepositoryIndexState & State Machine Review

### 10.1 Audit of Existing Model
The current V1 `RepositoryIndexState` in `apps/ai/src/indexer/contracts.py`:
```python
class RepositoryIndexState(BaseModel):
    repository_id: str
    branch: str = "main"
    indexed_commit_sha: str
    index_version: str = "v1"
    schema_version: str = "v1"
    parser_version: str = "1.0.0"
    status: IndexStateStatus = IndexStateStatus.INITIALIZING
    stats: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
```

### 10.2 Required State Additions for Incremental Indexing

| New Field | Type | Purpose & Reasoning |
| :--- | :--- | :--- |
| `previous_commit_sha` | `Optional[str]` | Tracks the base commit used for the delta calculation ($A$ in $A \to B$). Essential for debugging roll-forwards. |
| `last_successful_index_at` | `Optional[datetime]` | Timestamp of the last verified `READY` index, distinct from `updated_at` which changes during transitional states. |
| `generation` | `int` | Monotonically increasing sequence number per branch. Prevents stale async workers from overwriting newer states. |
| `indexing_error` | `Optional[str]` | Preserves error diagnostics when `status == FAILED`. |

---

## 11. Concurrency, Ordering & Race Condition Mitigation

### The Out-of-Order Commit Problem
Consider two developer pushes in rapid succession:
- **Push 1:** Commit $B$ at $T_1$
- **Push 2:** Commit $C$ at $T_2$ ($T_2 > T_1$)

If Job 1 (indexing $B$) is delayed and finishes *after* Job 2 (indexing $C$), Job 1 must **not** set `indexed_commit_sha = B` on the repository index state!

### Concurrency Controls
1. **Branch-Level Mutex (PostgreSQL Advisory Lock):**
   ```sql
   SELECT pg_try_advisory_xact_lock(hashtext('repo:' || repository_id || ':branch:' || branch));
   ```
   Only one indexing worker may execute for a given `(repository_id, branch)` at any time.
2. **Superseded Job Cancellation:**
   If a new push arrives for branch `main` while an earlier commit is still queued or running, the earlier job transitions to `CANCELLED`. The new job's delta is recomputed from the current `RepositoryIndexState.indexed_commit_sha` directly to the newest head commit.
3. **Optimistic Generation Check:**
   State updates check:
   ```sql
   UPDATE repository_index_states 
   SET indexed_commit_sha = $new_sha, generation = generation + 1
   WHERE repository_id = $repo_id AND branch = $branch AND generation = $expected_gen;
   ```

---

## 12. Full Rebuild Triggers (Safety Decision Matrix)

The system automatically switches from an incremental update to a full rebuild when any of the following safety triggers fire:

```
                             New Commit Trigger
                                      │
                         Is previous index READY?
                                ├── No ───► FULL REBUILD
                                │
                               Yes
                                │
                 Does previous commit exist in git?
                                ├── No ───► FULL REBUILD
                                │
                               Yes
                                │
                 Has schema or parser version changed?
                                ├── Yes ──► FULL REBUILD
                                │
                                No
                                │
                 Is diff file count > threshold (e.g. 50%)?
                                ├── Yes ──► FULL REBUILD
                                │
                                No
                                │
                                ▼
                       INCREMENTAL INDEX
```

### Safety Decision Matrix

| Condition | Action | Rationale |
| :--- | :--- | :--- |
| `status != IndexStateStatus.READY` | **Full Rebuild** | Cannot incrementally build on a corrupted or unverified index. |
| `previous_commit_sha` not in git history | **Full Rebuild** | Force-push or rebase rewrote history; no valid common ancestor. |
| `schema_version` changed (e.g. `v1 -> v2`) | **Full Rebuild** | Node/relationship definitions altered. |
| `parser_version` changed (e.g. Tree-sitter update) | **Full Rebuild** | AST extraction rules produce different symbol shapes. |
| Delta exceeds 50% of total repo files | **Full Rebuild** | Full rebuild is faster than massive piecemeal graph reconciliation. |
| Manual user trigger with `--force-reindex` | **Full Rebuild** | Explicit administrative override. |

---

## 13. Telemetry & Performance Targets

### Target Performance Benchmarks (V1)
- **Full Indexing Baseline (1,000 files, 50,000 LOC):** $\le 20 \text{ seconds}$.
- **Incremental Indexing (1–5 changed files):** $\le 1.0 \text{ second}$.
- **Incremental Indexing (20 changed files + 10 affected):** $\le 3.5 \text{ seconds}$.

### Monitored Metrics (`IndexingStats`)
```python
class IncrementalIndexingStats(IndexingStats):
    base_commit: str
    target_commit: str
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0
    files_affected: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    relationships_created: int = 0
    relationships_deleted: int = 0
    reconciliation_duration_seconds: float = 0.0
    total_duration_seconds: float = 0.0
```

---

## 14. Failure Recovery & Rollback

1. **Worker Crash Mid-Pipeline:**
   If a worker crashes while processing diff $A \to B$:
   - The `IndexJob` heartbeats expire; control plane marks job `FAILED`.
   - `RepositoryIndexState.indexed_commit_sha` remains pointing to $A$.
   - Next retry attempts $A \to B$ again. Because all graph operations use `MERGE` and exact reconciliation, partial state from the crashed job is overwritten cleanly.
2. **Graph Connection Timeout:**
   - Neo4j queries execute with exponential backoff (1s, 2s, 4s).
   - If retries fail, the transaction aborts, the job transitions to `FAILED`, and the repository index state is marked `STALE` or `FAILED`.
3. **Partial Vector Sync Failure:**
   - Vector database failures are classified as **non-fatal** warnings. The code graph reaches `READY` status, and a background sync task reconciles vector embeddings asynchronously.

---

## 15. Future Evolution

1. **Bi-Temporal Edge Validations (V2):** Add `valid_from_commit` and `valid_to_commit` properties to relationships for historical graph time-travel queries without node duplication.
2. **LSP-Assisted Precise Resolution:** Integrate language server protocol indexing (SCIP / LSIF) for cross-file type-accurate references.
3. **Cross-Repository Project Linking:** Aggregate separate repository code graphs under a unified `:Project` node in the Project Intelligence Layer.
