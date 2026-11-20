# ADR 0002: AI Service Architecture Consolidation & Production Hardening

> **Status:** Accepted  
> **Date:** November 2026  
> **Deciders:** Aryan Racha, System Architect  
> **Consulted:** GLOSSARY.md, ADR 0001  

---

## Context & Problem Statement

As the Python Intelligence Service (`apps/ai`) evolved into the canonical V1 architecture, an exhaustive audit revealed multiple critical defects, event-loop starvation bottlenecks, and legacy prototype layers:
1. **Event-Loop Freezes in LLM Adapter:** `DualLLMClient` invoked synchronous SDK calls (`client.models.generate_content` and synchronous `Groq`) inside async FastAPI functions, halting the entire server process during inference. Additionally, `GEMINI_MODELS` listed non-existent models (`gemini-3.5-flash`), triggering three 404 errors and latency spikes on every request.
2. **Neo4j Branch Filtering Leak:** In `src/graph/reader.py::get_entire_graph`, a typo in the Cypher query (`$branch = 'main'` instead of `f.branch = 'main'`) caused queries on the default branch to match every branch in the database, leaking nodes and corrupting graph visualizations.
3. **FastMCP Connection Churn & Synchronous I/O:** Every MCP tool recreated and closed a `Neo4jClient` per call, ignoring pooled connections. Furthermore, `tool_get_file_content` used synchronous `urllib.request.urlopen` in a loop across branches, risking up to 32 seconds of event-loop blocking.
4. **Split-Brain Autonomous Agents:** Legacy prototype agents (`reviewer.py`, `fixer.py`) duplicated the modern Curated Agents (`ReviewAgent`, `CodeAgent`). The public HTTP routes in `src/web/routes/pr.py` were still wired to the legacy prototypes, missing test gap detection, blast radius calculations, security rules, and Claude Code export capabilities.
5. **Dead On-Disk Files & Disk Leaks:** With Zero-Disk Ingestion (ADR 0001) established, local disk cloning and diffing helpers (`src/repo/cloner.py`, `src/repo/differ.py`, `src/jobs/pr_eval_job.py`, `src/jobs/init_job.py`) were obsolete. Furthermore, `GET /api/graph-report/{repo_id}` wrote temporary report files to `/tmp` on every request.
6. **Speculative Vector Store Stubs & Facades:** Unused stubs (`pinecone_store.py`, `qdrant_store.py`, `supabase_store.py`) and an ungoverned hybrid search facade (`src/kb_unified.py`) added unmaintained surface area.

---

## Decision Drivers

- **Zero-Disk Invariant:** Stateless worker containers without persistent volume dependencies or leftover `/tmp` files.
- **Single Seam Principle:** Exactly one authoritative implementation seam for every capability (PR review, remediation, context retrieval, indexing).
- **Asynchronous Hermeticity:** Zero synchronous blocking network/disk calls inside async event loops.
- **Strict Backward Compatibility:** Public API routes (`POST /api/pr/review`, `POST /api/pr/fix`) called by the Bun control plane must preserve their existing contract schema.
- **Scope Discipline:** Focus strictly on architectural cleanup and production hardening. Multi-tenant BYOK/Subscription credential support is deferred to a dedicated subsequent feature.

---

## Considered Options

1. **Option 1: Fix Only PR Routes and Leave Underlying Subsystems Untouched**
   - *Rejected:* Leaves critical event-loop starvation in `DualLLMClient`, the Cypher branch leak in `reader.py`, and FastMCP driver churn intact.

2. **Option 2: Comprehensive Architecture Consolidation & Production Hardening (Selected)**
   - Wire `routes/pr.py` to Curated Agents, maintaining schema compatibility with Bun API while adding enriched metadata.
   - Re-wire `src/benchmark/runner.py` to `ReviewAgent` and delete `reviewer.py` and `fixer.py`.
   - Transition `DualLLMClient` to native async SDKs (`client.aio` for Gemini, `AsyncGroq` for Groq) and official production model names (`gemini-2.5-flash`, `llama-3.3-70b-versatile`).
   - Fix the Cypher branch leak in `reader.py` (`f.branch = 'main'`).
   - Use pooled client singletons in `src/mcp/server.py` and replace `urllib.request` with `httpx.AsyncClient` in `src/mcp/tools.py`.
   - Render graph reports in-memory without `/tmp` file writes.
   - Delete dead on-disk files, speculative vector backends, and ungoverned facades.
   - Defer multi-tenant BYOK / Subscription credentials to a separate session.

---

## Decision Outcome

We selected **Option 2**. The implementation is divided into five tracer-bullet tickets:

1. **Ticket 01: PR Review & Fix Route Consolidation & Prototype Pruning**
   - Wire `routes/pr.py` to `ReviewAgent` and `CodeAgent`.
   - Update `src/benchmark/runner.py` to invoke `ReviewAgent`.
   - Delete `src/agents/reviewer.py`, `src/agents/fixer.py`, and flaky `tests/unit/test_reviewer.py`. Add mock-backed route tests.

2. **Ticket 02: Dead On-Disk Operations, Forwarding Shims & Disk Leaks Pruning**
   - Delete `src/repo/cloner.py`, `src/repo/differ.py`, and `src/jobs/pr_eval_job.py`.
   - Inline `RepositoryIndexer` into `src/cli.py` and delete `src/jobs/init_job.py`.
   - Refactor `render_graph_report` in `src/analysis/report.py` and `routes/graph.py` to return in-memory markdown strings without writing to `/tmp`.

3. **Ticket 03: Governed Retrieval, MCP Connection Pooling & Branch Leak Fix**
   - Fix Cypher branch leak in `src/graph/reader.py` (`f.branch = 'main'`).
   - Repoint MCP `tool_hybrid_search` to `ContextEngine.retrieve(...)` and delete `src/kb_unified.py`.
   - Replace synchronous `urllib.request` in `tool_get_file_content` with non-blocking `httpx.AsyncClient`.
   - Use shared Neo4j driver singletons in `src/mcp/server.py` to eliminate per-tool connection churn.

4. **Ticket 04: Vector Store & Prompt Streamlining**
   - Delete `src/vector/stores/pinecone_store.py`, `qdrant_store.py`, and `supabase_store.py` (and `.sql`).
   - Delete `src/agents/prompts.py` shim; update callers to `src/prompts`.
   - Standardize vector store factory strictly on `chroma_local`, `chroma_cloud`, and `memory`.

5. **Ticket 05: LLM Client Async Unblocking & Production Model Harmonization**
   - Transition `DualLLMClient` to native async SDK calls (`client.aio.models.generate_content` and `AsyncGroq`).
   - Fix model lists to official production models (`gemini-2.5-flash`, `llama-3.3-70b-versatile`), eliminating 404 warnings.
   - Introduce `get_governed_engine(...)` in `src.context` and simplify chat route dispatching.

---

## Consequences & Trade-offs

- **Positive:** Completely eliminates event-loop freezing during LLM calls and MCP file fetches.
- **Positive:** Fixes data leak across branches in Neo4j knowledge graph queries.
- **Positive:** Eliminates 100–300ms connection churn per MCP tool call.
- **Positive:** Preserves container statelessness with zero residual `/tmp` file leaks.
- **Positive:** Reduces `apps/ai` by ~1,300 lines of dead code and duplicate shims.
- **Trade-off / Deferred:** BYOK (Anthropic Claude, custom OpenAI-compatible endpoints) is deferred to a subsequent feature.
