# Comprehensive Architecture & Technical Interview Guide: AI Service (Code Review & KB Engine)

---

## 1. Executive Summary & System Overview

### 1.1 The Core Problem
- **Traditional Linters (e.g. ESLint, Flake8):** Rely on rigid AST rules or regex patterns. They lack cross-file semantic context, cannot reason about business logic or downstream system impact, and produce high false-positive noise.
- **Naive LLM-based PR Reviewers (e.g. ChatGPT pasted diffs):** Suffer from context-window truncation, hallucinations, and zero architectural awareness. They cannot answer: *"If I alter this function signature in `user_model.py`, what breaks in the upstream controllers or API routes across the repository?"*
- **Pure Vector RAG Reviewers:** Vector databases match textual and semantic similarity, but struggle with strict hierarchical code relationships (e.g. call graphs, import graphs, transitive dependencies, interface implementations).

### 1.2 The Solution: Dual Knowledge-Base Agentic Review Platform
This AI Service is a high-performance Python backend that bridges **AST-level static code graph intelligence (Neo4j)** with **semantic code embedding retrieval (ChromaDB + Gemini)**, orchestrated by an **Agentic Dual-LLM Reviewer & Autonomous Fix Engine (Gemini 2.0 Flash + Groq Llama-3.3-70B)** via the **Model Context Protocol (FastMCP)**.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM LANDSCAPE                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Next.js 16 UI  ◄──►  Bun Control Plane API  ◄──►  FastAPI / FastMCP AI Service │
│   (Port 3000)          (Port 3001)                  (Port 8000)                  │
│                                                          │                       │
│                                       ┌──────────────────┴───────────────────┐   │
│                                       ▼                                      ▼   │
│                             ChromaDB (Vector DB)                     Neo4j (Graph DB)
│                             - Code Signatures                        - File Nodes│
│                             - Docstrings & Bodies                    - Symbol Nodes
│                             - PR / Issue / Commit Context            - CALLS / IMPORTS
│                             - Multi-repo scoped                      - Multi-repo isolated
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. System Architecture & Microservice Responsibilities

| Tier / Service | Technology | Primary Responsibilities |
|---|---|---|
| **Frontend** | Next.js 16, React 19, TailwindCSS | Developer dashboard, interactive diff viewer, streaming AI reasoning visualizer, cited source inspection, one-click fix acceptance. |
| **Control Plane** | Bun, TypeScript, Drizzle ORM, SQLite/Postgres | GitHub App webhook intake, authentication, HMAC signature validation, job dispatching, GitHub comment posting, PR branch patching via Octokit. |
| **AI Intelligence Engine** | Python 3.12, UV, FastAPI, FastMCP | AST code parsing (Tree-sitter), Graph KB (Neo4j), Vector KB (ChromaDB), Blast Radius calculations, ReAct Agent Loop, Dual-LLM review & surgical fix synthesis. |
| **Graph Database** | Neo4j Community (Docker) | Structural code graph: callers, callees, imports, file dependencies, transitive blast radius paths. |
| **Vector Database** | ChromaDB (Persistent) | Semantic code representations: function signatures, docstrings, code bodies, PRs, issues. |

---

## 3. Directory Layout & Module Structure

```
backend/ai-service/
├── pyproject.toml              # UV / Hatchling dependency configuration
├── docker-compose.yml          # Containerized Neo4j Graph DB service
├── main.py                     # Entry point alias
├── src/ai_service/
│   ├── config.py               # Pydantic Settings (Neo4j, Chroma, API keys)
│   ├── cli.py                  # Click CLI for batch jobs, indexing, visualizer
│   ├── kb_unified.py           # UnifiedKB facade (Hybrid Search: Graph + Vector)
│   ├── visualize.py            # Vis.js interactive HTML dependency graph generator
│   │
│   ├── parsing/                # AST Code Analysis Engine (Tree-sitter)
│   │   ├── models.py           # Dataclasses: SymbolNode, CallEdge, ImportEdge, ParseResult
│   │   ├── parser.py           # CodeParser & LanguageRegistry (multi-language dispatcher)
│   │   └── extractors/
│   │       ├── base.py         # Abstract BaseExtractor class
│   │       ├── python.py       # Python AST Extractor (functions, classes, calls, imports)
│   │       └── mern.py         # MERN Extractor (JS, TS, JSX, TSX, React components, ES6 imports)
│   │
│   ├── graph/                  # Structural Knowledge Base (Neo4j)
│   │   ├── client.py           # Async Neo4j driver client wrapper
│   │   ├── schema.py           # Multi-tenant uniqueness constraints & indexes
│   │   ├── writer.py           # Batch upserts: File, Symbol, CALLS, IMPORTS, DEPENDS_ON
│   │   ├── reader.py           # Cypher queries: get_symbol, get_dependents, get_dependencies
│   │   └── resolver.py         # Post-parse import linker (resolves relative/aliased paths)
│   │
│   ├── vector/                 # Semantic Knowledge Base (ChromaDB)
│   │   └── client.py           # VectorKBClient, GeminiEmbeddingFunction, batch upserts, staleness management
│   │
│   ├── repo/                   # Git Operations Engine
│   │   ├── cloner.py           # Git clone with short-lived tokens & branch checkout
│   │   └── differ.py           # Git diff analyzer (changed files, added/deleted/modified symbols)
│   │
│   ├── analysis/               # Deterministic Code Review Rules & Impact Engine
│   │   ├── blast_radius.py     # Transitive graph traversal & ripple impact risk scoring
│   │   ├── conventions.py      # Static rule engine (function length, docstrings, PascalCase)
│   │   └── decision.py         # Deterministic decision gate (ACCEPT vs SUGGEST)
│   │
│   ├── agent/                  # Multi-Model AI Agent System
│   │   ├── llm_client.py       # DualLLMClient (Gemini 2.0 Flash + Groq Llama 3.3 70B failover)
│   │   ├── prompts.py          # ReAct system prompts, Orchestrator prompts, Worker prompts
│   │   ├── diff_parser.py      # Git diff hunk parser & symbol change extractor
│   │   ├── reviewer.py         # Multi-Agent Reviewer (Gemini Orchestrator + Groq Worker)
│   │   ├── fixer.py            # Autonomous Surgical Patch PR Fixer Agent
│   │   └── agent_loop.py       # AutonomousAgentLoop (ReAct SSE streaming + tool execution)
│   │
│   ├── mcp/                    # Model Context Protocol (MCP) Integration
│   │   ├── server.py           # FastMCP stdio server exposing KB tools to external agents
│   │   └── tools.py            # Core tool implementations (hybrid_search, get_blast_radius, etc.)
│   │
│   ├── jobs/                   # Orchestrated Batch Jobs (called by CLI / Bun API)
│   │   ├── init_job.py         # Flow 1: Repository Ingestion & Dual Indexing
│   │   └── pr_eval_job.py      # Flow 2: PR Evaluation & Incremental Indexing
│   │
│   └── web/                    # FastAPI HTTP & SSE Server
│       └── app.py              # REST API: /api/chat, /api/pr/review, /api/pr/fix, /api/ingest-url
│
└── tests/                      # Pytest Unit & Integration Test Suite
    ├── unit/                   # Unit tests (AST parsing, blast radius, decision, resolver, MCP)
    ├── integration/            # Multi-repo isolation, init job, PR eval job, agent review
    └── fixtures/               # Sample Python & MERN codebases
```

---

## 4. Deep Component-by-Component Breakdown

### 4.1 AST Parsing Engine (`parsing/`)

#### Purpose
Converts raw source code into high-level semantic symbols and relationship edges without executing the code. Uses `tree-sitter`, a concrete syntax tree parser written in C with Python bindings.

#### Key Data Models (`parsing/models.py`):
```python
SymbolKind = Literal["function", "class", "component", "method", "module"]
LanguageType = Literal["python", "javascript", "typescript", "tsx"]

@dataclass
class SymbolNode:
    name: str                   # e.g. "getUserData"
    kind: SymbolKind            # e.g. "function"
    file_path: str              # e.g. "src/services/user.ts"
    language: LanguageType      # e.g. "typescript"
    start_line: int             # e.g. 15
    end_line: int               # e.g. 42
    signature: str              # e.g. "export async function getUserData(userId: string): Promise<User>"
    docstring: str              # Extracted docstrings / comments
    code_body: str              # Full function body string
    qualified_name: str         # Unique symbol ID: "src/services/user.ts::getUserData"

@dataclass
class CallEdge:
    caller_symbol: str          # "src/controllers/auth.ts::loginHandler"
    callee_name: str            # "getUserData"
    file_path: str
    line: int

@dataclass
class ImportEdge:
    importer_file: str          # "src/controllers/auth.ts"
    imported_symbol: str        # "getUserData"
    module_path: str            # "../services/user"
    line: int

@dataclass
class ParseResult:
    file_path: str
    language: LanguageType
    symbols: list[SymbolNode]
    calls: list[CallEdge]
    imports: list[ImportEdge]
    errors: list[str]
```

#### Multi-Language Extractors:
1. **`PythonExtractor` (`parsing/extractors/python.py`):**
   - Parses `function_definition` and `class_definition`.
   - Tracks lexical scope hierarchies (`UserClass.get_email` -> `method` under `user.py::UserClass.get_email`).
   - Extracts leading string expression statements as docstrings.
   - Extracts function calls (`node.type == "call"`) and imports (`import_statement`, `import_from_statement`).
2. **`MernExtractor` (`parsing/extractors/mern.py`):**
   - Supports JS, TS, JSX, and TSX.
   - Parses standard function declarations, class declarations, and methods.
   - Detects arrow functions assigned to variables (`const UserService = () => ...`).
   - Automatically classifies uppercase function names as React `component` (e.g. `Header`, `Dashboard`).
   - Parses ES6 named imports (`import { useState, useEffect } from 'react'`), default imports, and namespace imports (`import * as api from './api'`).

---

### 4.2 Structural Graph Knowledge Base (`graph/`)

#### Purpose
Stores the hierarchical topology and dependency relationships of the codebase in Neo4j.

#### Graph Schema & Node Types:
1. `(:File)`: Represents source files. Properties: `file_path`, `repo_id`, `branch`, `language`.
2. `(:Symbol)`: Represents functions, classes, methods, React components. Properties: `qualified_name`, `name`, `kind`, `start_line`, `end_line`, `signature`, `docstring`.
3. `(:Package)`: Represents external dependencies (e.g., `express`, `react`, `numpy`).

#### Relationship Types:
- `(:File)-[:DEFINES]->(:Symbol)`: File contains this symbol definition.
- `(:Symbol)-[:CALLS]->(:Symbol)`: Symbol invokes another symbol (annotated with `line`, `file_path`).
- `(:File)-[:IMPORTS]->(:Symbol)`: File imports an internal symbol.
- `(:File)-[:DEPENDS_ON]->(:Package)`: File imports a 3rd-party package.
- `(:File)-[:DEPENDS_ON_FILE]->(:File)`: Resolved cross-file dependency.

#### Multi-Tenant Isolation & Constraints (`graph/schema.py`):
```cypher
CREATE CONSTRAINT symbol_repo_isolation IF NOT EXISTS
FOR (s:Symbol)
REQUIRE (s.repo_id, s.branch, s.qualified_name) IS UNIQUE;

CREATE CONSTRAINT module_repo_isolation IF NOT EXISTS
FOR (m:Module)
REQUIRE (m.repo_id, m.branch, m.file_path) IS UNIQUE;

CREATE INDEX symbol_repo_idx IF NOT EXISTS
FOR (s:Symbol)
ON (s.repo_id, s.branch);
```

#### Import Resolution Engine (`graph/resolver.py`):
`resolver.py` runs a post-processing resolution pass:
- Resolves relative extensions: `./api` -> `api.js`, `api.ts`, `api/index.ts`.
- Resolves Python module dot-notation: `utils.helpers` -> `utils/helpers.py`.
- Replaces generic `Package` stubs with direct `DEPENDS_ON_FILE` edges to existing internal `File` nodes.

---

### 4.3 Semantic Vector Knowledge Base (`vector/`)

#### Purpose
Stores dense vector embeddings of code symbols and natural language descriptions in ChromaDB, enabling semantic conceptual search.

#### Key Features (`vector/client.py`):
- **ChromaDB Client:** Persistent storage in `./chroma_db`.
- **`GeminiEmbeddingFunction`:** Uses Google's official `google-genai` SDK (`models/gemini-embedding-001` or `text-embedding-004`).
- **Rate-Limit & Error Resilience:** Implements exponential backoff on HTTP 429 (`RESOURCE_EXHAUSTED`) with automatic retry and 3072-dimensional zero-vector fallback.
- **Batch Deduplication:** `add_code_entries_batch()` groups documents into chunks of 40 to avoid ChromaDB batch conflicts.
- **Staleness Tracking & Roll-Forward:**
  - Every document records `commit_hash` and `last_valid_commit`.
  - `roll_forward_commit(repo, branch, old_hash, new_hash)`: Updates valid commits during non-breaking updates.
  - `delete_stale_entries(repo, branch, latest_hash)`: Garbage collects deleted symbols.

---

### 4.4 Unified Knowledge Base & Hybrid Search (`kb_unified.py`)

#### Purpose
Acts as a unified facade over both ChromaDB and Neo4j, executing **Hybrid Retrieval-Augmented Generation (Hybrid RAG)**.
1. Vector similarity search over ChromaDB code/PR/commit/issue embeddings.
2. Tokenized regex & Cypher MATCH search across Neo4j Symbol and File nodes.
3. Merges and deduplicates hits into a single rich context object.

---

### 4.5 Blast Radius & Static Convention Analysis (`analysis/`)

#### Blast Radius Algorithm (`analysis/blast_radius.py`):
1. Takes a list of `changed_symbols` (e.g. `['auth.py::verify_token']`).
2. Performs a reverse transitive traversal across `[:CALLS*1..3]` in Neo4j via `get_dependents()`.
3. Calculates a weighted **Risk Score**:
   - Risk Score formula: `Sum over affected symbols of: (1 / depth) * (1 + 0.5 * (fan_in - 1))`
   - Direct callers (depth=1) contribute weight 1.0.
   - Indirect callers (depth=2, 3) contribute 0.5 and 0.33.
   - High fan-in symbols receive a boost due to compounding ripple risk.

#### Static Convention Engine (`analysis/conventions.py`):
- `RULE-001`: Function length warning if body > 50 lines.
- `RULE-002`: Missing docstring warning on public Python symbols.
- `RULE-003`: PascalCase naming enforcement on Classes and React components.

#### Decision Gate (`analysis/decision.py`):
- If `risk_score > 5.0` or convention violations exist: Verdict = `SUGGEST`.
- Otherwise: Verdict = `ACCEPT`.

---

### 4.6 Multi-Agent LLM Orchestrator & Worker Architecture (`agent/`)

#### Dual-LLM Hierarchy Design:
1. **Gemini 2.0 Flash (Master Orchestrator):**
   - High-level planning, tool selection, knowledge graph reasoning, final RAG synthesis.
2. **Groq Llama-3.3-70B (High-Speed Worker Node):**
   - Ultra-fast token generation (~250 tokens/sec).
   - Line-by-line diff inspection for syntax bugs, invalid property calls (`.size()` vs `.length`), off-by-one errors, null checks.
3. **Automatic Failover:**
   - If Gemini encounters rate limits or network issues, `DualLLMClient` immediately fails over to Groq Llama-3.3-70B.

#### Autonomous PR Reviewer (`agent/reviewer.py`):
1. Parses git diff into structured `DiffHunk` objects via `diff_parser.py`.
2. Queries Neo4j for blast radius impact.
3. Queries ChromaDB for semantic code context.
4. Dispatches Groq Worker for line-level bug auditing (outputs structured JSON issues).
5. Dispatches Gemini Orchestrator for holistic architectural review.
6. Computes composite risk score and outputs actionable review verdict + line comments.

#### Autonomous Surgical PR Fixer (`agent/fixer.py`):
- Operates in **Surgical Patch Mode**:
  1. Fetches exact source file contents from GitHub REST API or local disk.
  2. Numbers every line (`1: import ...`, `2: const ...`).
  3. Plans minimal line replacements rather than rewriting entire files.
  4. Preserves 100% of unedited functions, comments, and structure.
  5. Returns replacement file payload to Bun API service to push directly to a new `ai-fix/pr-<id>` branch.

#### Autonomous ReAct Agent Loop (`agent/agent_loop.py`):
Implements the **Reason + Act (ReAct)** pattern with Server-Sent Events (SSE) streaming:
- `thought`: Explains reasoning step to the user in real time.
- `call_tool`: Invokes FastMCP tools dynamically based on missing context.
- `tool_end`: Streams tool output, latency in milliseconds, and matched citations.
- `final_answer`: Synthesizes verified markdown response with bracketed citations `[1]`, `[2]`.

---

### 4.7 Model Context Protocol (FastMCP) Server (`mcp/`)

#### Purpose
Implements Anthropic's **Model Context Protocol (MCP)** specification using `FastMCP`. Enables external AI agents (like Claude Desktop, Cursor, Gemini CLI) to connect via `stdio` transport and query the repository's Knowledge Base.

#### Exposed MCP Tools (`mcp/server.py` & `mcp/tools.py`):
1. `get_repo_structure(repo_id, branch)`: Full file tree & symbol map.
2. `get_symbol_details(repo_id, qualified_name, branch)`: Callers, callees, signature, docstring.
3. `get_blast_radius(repo_id, changed_symbols, branch)`: Downstream ripple impact.
4. `get_file_dependencies(repo_id, file_path, branch)`: Imports and imported-by files.
5. `search_symbols(repo_id, query, branch)`: Fuzzy symbol finder.
6. `vector_search(query, repo_id, n_results)`: Semantic similarity search.
7. `hybrid_search(repo_id, query, branch, n_results)`: Combined Graph + Vector search.

---

### 4.8 Core Workflows & Execution Flows (`jobs/`)

#### Flow 1: Repository Initialization (`jobs/init_job.py`)
1. Neo4j Schema Setup (Indexes & Constraints).
2. Purges stale data for `(repo_id, branch)`.
3. `Tree-sitter` CodeParser traverses directory and extracts symbols, calls, and imports.
4. Batch Graph write to Neo4j (`File`, `Symbol`, `CALLS`, `IMPORTS`).
5. Batch Vector write to ChromaDB with Gemini embeddings.
6. Post-processing `resolve_repo_imports()` links relative paths to internal File nodes.

#### Flow 2: PR Evaluation Job (`jobs/pr_eval_job.py`)
1. Git Differ computes changed files & symbols.
2. Incremental Graph & Vector update for changed files.
3. Neo4j Blast Radius Calculation (Transitive dependents).
4. Static Convention Checks (`RULE-001`, `RULE-002`, `RULE-003`).
5. Groq Worker line-by-line Diff Analysis (JSON issues).
6. Gemini Orchestrator architectural review.
7. Decision Gate: `ACCEPT` (clean) or `SUGGEST` (issues/high risk).

---

### 4.9 FastAPI Web Server & SSE Endpoints (`web/app.py`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service health status check |
| `GET` | `/api/repos` | List all indexed repositories in Graph & Vector DB |
| `POST` | `/api/chat` | Non-streaming single-turn RAG chat endpoint |
| `POST` | `/api/chat/stream` | **SSE Streaming ReAct Agent endpoint** with real-time tool execution visualization |
| `POST` | `/api/pr/review` | Full Agentic PR Review endpoint |
| `POST` | `/api/pr/fix` | Autonomous Surgical PR Fixer endpoint |
| `POST` | `/api/ingest-url` | Clones public GitHub repo and indexes into KB |
| `POST` | `/api/tools/execute` | Direct tool invocation endpoint for UI inspection |

---

## 5. End-to-End System Walkthrough (Interview Script)

### Step 1: Repository Onboarding & Indexing
1. User connects a GitHub repo via frontend -> Bun.
2. Bun calls `/api/ingest-url` or starts an init job.
3. Python clones repo, parses AST with Tree-sitter, builds call/import graph in Neo4j, generates embeddings in ChromaDB, and resolves imports.

### Step 2: Developer Submits a Pull Request
1. GitHub webhook fires on Bun -> Bun calls `/api/pr/review`.
2. AI Service computes Blast Radius in Neo4j, fetches ChromaDB context, dispatches Groq Llama-3.3-70B for hunk bug auditing, and Gemini 2.0 Flash for architectural synthesis.
3. Bun posts suggestions directly to GitHub and updates Next.js UI.

### Step 3: Autonomous One-Click Fix
1. Maintainer clicks **"Apply AI Fix"** in Next.js.
2. Frontend calls `/api/pr/fix`.
3. `fixer.py` performs surgical line replacement on exact source files.
4. Bun pushes a commit to a new `ai-fix/pr-<id>` branch on GitHub.

---

## 6. Technical Interview Q&A / Defense Guide

### Q1: Why did you design a Dual Knowledge Base (Graph + Vector) instead of just using Vector RAG?
**Answer:**
> *"Vector search is great for semantic similarity—answering questions like 'Where is user billing handled?'. But code is relational and deterministic. If a PR alters a database function signature, vector similarity cannot reliably discover all transitive callers across 10 files. By combining Neo4j (structural call graph, import graph, blast radius traversal) with ChromaDB (semantic code descriptions), we achieve deterministic dependency guarantees + semantic understanding."*

### Q2: How do you prevent multi-tenant data leaks and collision across multiple repos or branches?
**Answer:**
> *"We enforce multi-tenant isolation at three levels:
> 1. Neo4j Constraints & Compound Keys: Every Symbol node has a composite uniqueness constraint on `(repo_id, branch, qualified_name)`. Cypher queries strictly filter by `repo_id` and `branch`.
> 2. ChromaDB Metadata Filtering: Every vector entry includes `repo` and `branch` metadata. Queries enforce `where` clause filters.
> 3. Staleness Roll-forward: Modified files trigger isolated node deletions and vector roll-forward updates without affecting other branches or repos."*

### Q3: Why did you use Tree-sitter instead of Python's built-in ast module or regex?
**Answer:**
> *"Python's built-in `ast` module only parses Python and fails on syntax errors in partial diffs. Tree-sitter is an incremental, error-tolerant parser written in C that supports dozens of languages (Python, JavaScript, TypeScript, TSX, React). It extracts accurate concrete syntax trees even on incomplete code snippets or mixed TSX/JSX constructs."*

### Q4: Explain your Blast Radius formula and why depth weighting matters.
**Answer:**
> *"Our blast radius traverses incoming call edges up to depth 3 in Neo4j. The formula is:
> $$	ext{Risk Score} = \sum rac{1}{	ext{depth}} 	imes (1 + 0.5 	imes (	ext{fan\_in} - 1))$$
> Direct callers ($	ext{depth}=1$) have immediate break risk and get full weight (1.0). Downstream callers at depth 2 and 3 receive decaying weights (0.5, 0.33). High fan-in symbols get boosted because changing them has a compounding ripple effect."*

### Q5: Why did you use a Dual-LLM architecture (Gemini + Groq)?
**Answer:**
> *"We pair Google Gemini 2.0 Flash with Groq Llama-3.3-70B:
> 1. Gemini 2.0 Flash: Master Orchestrator for complex planning, tool invocation, and hybrid RAG synthesis.
> 2. Groq Llama-3.3-70B: High-throughput Worker node at ~250 tokens/sec for fast, parallel diff auditing without API rate limit bottlenecks.
> 3. Failover: Automatic fallback if either provider has rate limits or network issues."*

### Q6: How does your Autonomous Fixer avoid hallucinating whole-file rewrites?
**Answer:**
> *"Rather than generating entire 500-line files from scratch, `fixer.py` uses Surgical Patch Mode: it line-numbers the real existing source file, plans minimal line replacements, and splices the replacement directly into the original file buffer. Unmodified lines remain byte-for-byte identical."*

---

## 7. Key Technology Stack Summary Table

| Category | Technology | Version / Spec | Justification |
|---|---|---|---|
| **Language & Runtime** | Python | `>= 3.12` | Modern typing, `asyncio`, performance improvements |
| **Package Manager** | UV | `>= 0.1.0` | Ultra-fast Rust-based Python dependency resolver |
| **AST Parser** | Tree-sitter | `tree-sitter 0.22`, `python`, `javascript`, `typescript` | Polyglot, incremental, error-tolerant AST parsing |
| **Graph Database** | Neo4j | `>= 5.18.0` (Community Docker) | Cypher query language, transitive relationship traversal |
| **Vector Database** | ChromaDB | `>= 1.5.9` | Embeddings store with metadata filtering & persistence |
| **AI Protocol** | FastMCP | `>= 3.4.6` | Anthropic Model Context Protocol standard integration |
| **LLM Orchestration** | Google Gemini 2.0 Flash | `google-genai 0.1.0` | Master orchestration, hybrid RAG synthesis, embeddings |
| **LLM Worker** | Groq Llama-3.3-70B | `groq 0.9.0` | Ultra-fast line-level diff auditing and failover |
| **Web Framework** | FastAPI & Uvicorn | `fastapi 0.141.1` | Asynchronous REST & Server-Sent Events (SSE) streaming |
| **Testing** | Pytest & pytest-asyncio | `>= 8.0.0` | Async unit and integration test coverage |
