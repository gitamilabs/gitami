# Domain Glossary

The ubiquitous language of **Gitami**. Use these exact terms when discussing domain concepts, naming modules, authoring specs, or writing tests.

---

### Core Intelligence & Knowledge Storage

- **Knowledge Base (KB):** The dual-engine storage layer comprising the Neo4j Structural Knowledge Graph and the ChromaDB Semantic Vector Store.
- **Knowledge Map:** The visualization and structural graph of an indexed repository. _Avoid:_ "Build", "Project Dump".
- **Indexing:** The pipeline that checks out code, parses ASTs with Tree-sitter, extracts symbols/calls/imports, and populates the Knowledge Base. _Avoid:_ "Building", "Compiling".
- **Incremental Indexing:** Differential sync between two Git commit SHAs, updating only modified symbols, pruning deleted nodes, and re-linking caller edges without a full wipe.
- **Zero-Disk Ingestion:** Remote repository synchronization that fetches commit diffs and modified files in-memory via GitHub APIs, keeping worker containers completely stateless.
- **Selective Caller Rewiring:** Two-phase edge reconciliation that identifies incoming callers to modified symbols in Neo4j and re-parses only the affected caller files ($O(\Delta + \text{affected})$).
- **Degraded Vector State:** A self-healing index state (`DEGRADED_VECTOR`) where the structural Neo4j graph is up to date with the latest commit, but pending vector embeddings are awaiting an async retry due to transient embedding quota exhaustion.
- **Symbol:** A first-class syntactic entity (function, method, class, interface, type alias) extracted from code with source line boundaries and docstrings.
- **Call Edge (`CALLS`):** A directed relationship in Neo4j representing a caller invoking a callee symbol.
- **Blast Radius:** The computed set of downstream symbols, files, and tests impacted by a change, derived via recursive Cypher graph traversal.
- **Context Engine:** The governed retrieval subsystem that classifies query intent, parallel-queries graph/vector/source retrievers, ranks results deterministically, and bounds output within LLM token budgets.

---

### Curated Autonomous Agents

- **Investigation Agent:** Multi-step hypothesis-testing agent that navigates the Knowledge Base to diagnose incidents and answer codebase architecture queries with confidence scores and reasoning traces.
- **Issue Agent:** Webhook-triggered triage agent that scores criticality, detects open/closed duplicates, tags domains, and flags suspicious AI-generated code.
- **Review Agent:** PR evaluation agent that measures risk scores (0–100), detects security anti-patterns, checks convention linting, measures test gaps, and exports actionable checklists for human maintainers or Claude Code.
- **Code Agent:** Autonomous remediation agent that operates test-first in two stages: Stage 1 creates a fix plan for maintainer approval; Stage 2 synthesizes reproduction tests and implementation patches.
- **Doc Agent:** Documentation generation agent producing onboarding guides, domain overviews, and changelogs, continuously monitoring code changes to mark stale documentation.

---

### Control Plane & Infrastructure

- **Control Plane (`apps/api`):** The Bun/Hono service managing authentication, GitHub App OAuth/webhooks, team/project RBAC, and background task queues.
- **Intelligence Worker (`apps/ai`):** The Python/FastAPI service hosting Tree-sitter extractors, the Context Engine, Neo4j drivers, and Curated Agents.
- **Index Job:** A durable task tracking repository ingestion progress across lifecycle stages (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`).
