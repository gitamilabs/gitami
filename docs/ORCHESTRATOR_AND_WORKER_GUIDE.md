# GitAmi Architecture: Orchestrator and Worker Deep Dive

This document provides a comprehensive, end-to-end technical explanation of how the **Orchestrator** and **Worker** architectural patterns operate within the GitAmi AI-powered Code Review and Repository Intelligence platform.

---

## 1. Executive Summary

GitAmi utilizes the **Orchestrator-Worker** design pattern across two distinct architectural layers:

1. **System-Level Control Plane (Bun ↔ Python Engine)**:
   - **Bun Control Plane (TypeScript)** acts as the *Macro Orchestrator*, managing GitHub App authentication, receiving webhooks, managing repository lifecycle, and invoking computational jobs.
   - **Python AI Service (UV / FastAPI / FastMCP)** acts as the *Analytical Worker*, executing AST parsing, knowledge graph construction, blast-radius computations, and deep reasoning without holding any direct GitHub credentials.

2. **Cognitive-Level Multi-LLM Hierarchy (DualLLMClient)**:
   - **Orchestrator LLM (Gemini / Qwen)** acts as the *Strategic Architect & Decision Maker*, performing high-level planning, knowledge graph/vector RAG synthesis, 5-step defensive falsification of defects, and surgical fix planning.
   - **Worker LLM (Groq / Ollama / Llama-3.3-70B / Qwen2.5-Coder)** acts as the *Tactical High-Speed Operator*, performing line-by-line diff hunk inspections, checking language-specific gotchas, and executing precise surgical file patches.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                SYSTEM-LEVEL ARCHITECTURE                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   GitHub Webhooks ──► ┌────────────────────────────────────────┐                       │
│   (PR open/update)    │          Bun Control Plane             │ ◄── Next.js 16 UI     │
│                       │   (Macro Orchestrator & Auth Guard)    │                       │
│                       └──────────────────┬─────────────────────┘                       │
│                                          │ Dispatches Job / Passes Token               │
│                                          ▼                                             │
│                       ┌────────────────────────────────────────┐                       │
│                       │       Python AI Service (Worker)       │                       │
│                       │   (Tree-sitter, Neo4j, Chroma, CPG)    │                       │
│                       └──────────────────┬─────────────────────┘                       │
│                                          │                                             │
│ ┌────────────────────────────────────────┴───────────────────────────────────────────┐ │
│ │                        COGNITIVE-LEVEL DUAL-LLM HIERARCHY                         │ │
│ ├───────────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                                   │ │
│ │   ┌───────────────────────────────┐       ┌───────────────────────────────────┐   │ │
│ │   │   Primary Orchestrator LLM    │       │         Worker Node LLM           │   │ │
│ │   │     (Gemini 2.0 / Qwen)       │       │    (Groq / Ollama Qwen Coder)     │   │ │
│ │   ├───────────────────────────────┤       ├───────────────────────────────────┤   │ │
│ │   │ • High-level reasoning        │       │ • High-throughput (~250 tok/s)    │   │ │
│ │   │ • Multi-tool MCP planning     │ ◄───► │ • Granular diff hunk inspection   │   │ │
│ │   │ • 5-Step Defect Falsification │       │ • AST & Syntax edge-case scanning │   │ │
│ │   │ • Surgical Fix Architecture   │       │ • Precision 1-5 line code patches │   │ │
│ │   │ • Final Review Verdict        │       │ • Strict structured JSON output   │   │ │
│ │   └───────────────────────────────┘       └───────────────────────────────────┘   │ │
│ └───────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer 1: System-Level Control Plane Orchestration

The system boundary explicitly separates control/auth from heavy compute:

```
┌──────────────┐         Webhook         ┌────────────────────────┐
│  GitHub App  ├────────────────────────►│  Bun Control Plane     │
└──────▲───────┘                         │  - Validates HMAC      │
       │                                 │  - Manages short tokens│
       │ Post Comments / Push Commits    │  - Stores PR state     │
       └─────────────────────────────────┤  - Frontend API (3001) │
                                         └───────────┬────────────┘
                                                     │ HTTP / Job Dispatch
                                                     ▼
                                         ┌────────────────────────┐
                                         │  Python AI Engine      │
                                         │  - No GitHub secrets   │
                                         │  - Git clone via token │
                                         │  - Neo4j & ChromaDB    │
                                         │  - Joern CPG Engine    │
                                         │  - Decision Gate       │
                                         └────────────────────────┘
```

### Why This Separation?
1. **Security Isolation**: The Python engine never stores long-lived GitHub secrets. Bun issues scoped, short-lived tokens for repo cloning.
2. **Crash Resilience**: CPU-intensive operations (AST parsing with Tree-sitter, Cypher graph algorithms, vector embedding generation) execute in the Python worker without blocking the Bun HTTP event loop.
3. **Stateless Scalability**: The Python AI service operates as a stateless computational worker that ingests data, updates Neo4j/ChromaDB, synthesizes verdicts, and returns JSON payloads to Bun.

---

## 3. Layer 2: Cognitive-Level Multi-LLM Architecture

In the AI engine (`backend/ai-service/src/ai_service/agent/`), single-model approaches either become too slow/expensive for diff scanning or lack the reasoning capacity for architectural blast-radius assessment. GitAmi solves this via a **Dual-LLM Client** (`llm_client.py`).

### 3.1 Node Responsibilities Matrix

| Dimension | Primary Orchestrator | Worker Node |
| :--- | :--- | :--- |
| **Default Models** | Google Gemini 2.0 / 3.6 Flash / Qwen 2.5 Coder (Ollama/Groq) | Groq Llama-3.3-70B / Qwen 3.8-27B / Ollama `qwen2.5-coder:latest` |
| **Latency Profile** | Strategic reasoning (1.5s – 5.0s) | Sub-second high-throughput (200–800ms, ~250 tok/s) |
| **Input Context** | Blast radius, Joern CPG taint analysis, vector passages, worker issue candidates, full diff summary | Scoped git diff hunks (chunked up to 22,000 characters per file group) |
| **Primary Task** | Strategic verdict (`ACCEPT` vs `SUGGEST`), 5-step falsification, surgical repair planning | Tactical scanning (syntax bugs, unhandled promises, invalid method names) |
| **Output Format** | Markdown architectural rationale + verified issue array | Strict machine-readable JSON schema |

---

### 3.2 DualLLMClient Failover & Circuit Breakers

The `DualLLMClient` class in [`src/ai_service/agent/llm_client.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/llm_client.py) coordinates execution across cloud APIs and local inference engines. It features built-in cooldown tracking:

```
                      ┌────────────────────────────┐
                      │    run_orchestrator(...)   │
                      └─────────────┬──────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        [orchestrator_provider]             [orchestrator_provider]
               == 'ollama'                          != 'ollama'
                  │                                   │
                  ▼                                   ▼
        ┌──────────────────┐                ┌──────────────────┐
        │  Ollama (Local)  │                │    Groq Qwen     │
        └─────────┬────────┘                └─────────┬────────┘
                  │ (Fails / Cooldown)                │ (Fails / Cooldown)
                  ▼                                   ▼
        ┌──────────────────┐                ┌──────────────────┐
        │    Groq Qwen     │                │  Gemini Flash    │
        └─────────┬────────┘                └─────────┬────────┘
                  │ (Fails / Cooldown)                │ (Fails / Cooldown)
                  ▼                                   ▼
        ┌──────────────────┐                ┌──────────────────┐
        │  Gemini Flash    │                │  Ollama (Local)  │
        └─────────┬────────┘                └─────────┬────────┘
                  │ (All Failed)                      │ (All Failed)
                  ▼                                   ▼
        ┌──────────────────────────────────────────────────────┐
        │      Local Intelligent RAG Synthesis (Offline)       │
        └──────────────────────────────────────────────────────┘
```

#### Cooldown & Quota Mechanics:
- **Ollama Cooldown (`_ollama_cooldown_until`)**: If a connection drops (HTTP 404, 500, or connection refused), Ollama is placed on a **30-second cooldown** to prevent blocking subsequent requests.
- **Gemini Cooldown (`_gemini_model_cooldowns`)**: If an HTTP 429 (`RESOURCE_EXHAUSTED` or `quota exceeded`) is returned, the affected model is put on a **60-second cooldown**, automatically falling back to the next model in `GEMINI_MODELS`.
- **Groq Cooldown (`_groq_model_cooldowns`)**: On rate-limiting, Groq attempts a 2.0-second backoff. If exhausted, it applies a **60-second cooldown** and delegates to Gemini or Ollama.

---

## 4. Deep Dive: PR Review Pipeline (`reviewer.py`)

The PR review workflow ([`src/ai_service/agent/reviewer.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/reviewer.py)) illustrates the concurrent coordination between Orchestrator and Worker nodes.

```
                  Git Diff (Raw Text)
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
1. Diff Parser (Hunks)              2. File-Based Chunking
   Changed Symbols & Files             (Max 22,000 chars/chunk)
       │                                       │
       └───────────────────┬───────────────────┘
                           │
         ┌─────────────────┼─────────────────┬─────────────────┐
         ▼                 ▼                 ▼                 ▼
   Neo4j Graph       ChromaDB Vector     Joern CPG         Worker Nodes
   Blast Radius      Semantic Search     Guards/Callers    (Parallel Hunk
   Calculation       (Top-3 Passages)    Taint Analysis     Inspection)
         │                 │                 │                 │
         └─────────────────┼─────────────────┴─────────────────┘
                           │ (All gathered via asyncio.gather)
                           ▼
              Worker Candidate Issues Parsed
              & Deduplicated (Line Window = 15)
                           │
                           ▼
        ┌─────────────────────────────────────────┐
        │       Gemini / Qwen Orchestrator        │
        │   - 5-Step Defensive Falsification      │
        │   - Zero-False-Negative Protocol        │
        │   - Architectural Synthesis             │
        └──────────────────┬──────────────────────┘
                           │
                           ▼
          Composite Risk Score & Final Decision
                Verdict: ACCEPT or SUGGEST
```

### Step 1: Diff Chunking & Preparation
Large PRs with multiple files often overflow token windows if analyzed in a single prompt. 
`_chunk_diff_by_files()` partitions the git patch into distinct multi-file chunks (up to 22,000 characters each) to guarantee complete file coverage.

### Step 2: Concurrent Fan-Out (`asyncio.gather`)
Four independent analysis tasks run simultaneously:
1. **Blast Radius (`tool_get_blast_radius`)**: Neo4j traverses `[:CALLS*1..3]` paths to score downstream ripple risk (`0.0`–`10.0`).
2. **Vector Similarity (`tool_vector_search`)**: ChromaDB fetches top semantic context passages for modified logic.
3. **Joern CPG Analysis (`_run_cpg_analysis`)**: Concurrently inspects Control Property Graph ASTs for dominating conditional guards, input sanitizers, and call-site arguments.
4. **Worker Inspections (`_inspect_chunk`)**: Worker instances evaluate each chunk in parallel.

### Step 3: Worker Node Inspection (`pr_reviewer_worker.py`)
Each worker evaluates:
- **Language Gotchas**: Incorrect property invocations (e.g., calling `.size()` instead of `.length` on JS arrays, or `.length` instead of `len()` in Python).
- **Async Pitfalls**: Missing `await`, unhandled Promise rejections, or `Array.forEach(async ...)` loops.
- **Lifecycle & Memory Leaks**: Uncleaned `URL.createObjectURL` or dangling event listeners.
- **Dynamic Imports & I/O**: Unhandled exceptions around `import(...)` or HTTP fetch calls.

The worker responds in strict JSON:
```json
{
  "issues": [
    {
      "title": "Invalid .size() method call on TypeScript Array",
      "description": "Calling .size() on an Array produces undefined at runtime. Use .length instead.",
      "category": "bug",
      "severity": "error",
      "file_path": "src/services/payment.ts",
      "line": 48,
      "suggested_fix": "items.length > 0"
    }
  ]
}
```

### Step 4: Issue Deduplication (`deduplicate_issues`)
Before passing candidates to the Orchestrator, overlapping issues on the same file within a **15-line window** that share semantic token overlap ($\ge 25\%$) are merged to prevent redundant warnings.

### Step 5: Orchestrator 5-Step Defensive Falsification
The Orchestrator receives:
- All candidate issues from the worker nodes
- The Joern CPG structural taint summary
- Neo4j blast radius score
- ChromaDB semantic code cards
- The raw diff patch

It applies the **Zero False Negative Protocol**:
1. **Inspect Target**: Examines candidate flaws reported by worker nodes.
2. **Verify Cryptographic/Mathematical Sanitization**: Injection candidates (`db.execute`, `eval`, `subprocess`) can **only** be dismissed if mathematical neutralization exists (e.g., SQL parameterized bindings, DOMPurify).
   > *Rule*: Presence checks (`if (x)`), null checks (`x != null`), and auth annotations (`@login_required`) do **NOT** neutralize payloads and must **NOT** be used to falsify an issue.
3. **Verify Upstream Callers**: Check if callers pass compile-time hardcoded string literals. If arguments are dynamic or ambiguous, the finding is retained.
4. **Verify Framework Guarantees**: Confirm whether the runtime framework provides automatic context escaping (e.g. React JSX expressions).
5. **Ground Confirmed Issues**: Finalize surviving issues and determine the verdict (`ACCEPT` vs `SUGGEST`).

---

## 5. Deep Dive: Autonomous Surgical Fixer (`fixer.py`)

When a pull request triggers a `SUGGEST` verdict, the maintainer can trigger the **Autonomous Surgical PR Fixer** ([`src/ai_service/agent/fixer.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/fixer.py)).

```
                       Reported Issues & File Paths
                                    │
                                    ▼
                 Full File Content Retrieved & Line-Numbered
                    (From Bun API / GitHub or Local Disk)
                                    │
                                    ▼
               ┌─────────────────────────────────────────┐
               │    Step 1: Orchestrator Fix Planner     │
               │         (Gemini / fixer_orchestrator)   │
               └────────────────────┬────────────────────┘
                                    │ Generates Minimal Plan:
                                    │ - Target File & Lines
                                    │ - Current Code vs Replacement
                                    │ - Zero Collateral Refactoring
                                    ▼
               ┌─────────────────────────────────────────┐
               │    Step 2: Worker Surgical Patcher      │
               │         (Ollama/Groq / fixer_worker)    │
               └────────────────────┬────────────────────┘
                                    │ Outputs full file in blocks:
                                    │ <<<FILE: ...>>> ... <<<ENDFILE>>>
                                    ▼
                         Safety & Drift Verification
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
             Line Drift <= 40%                   Line Drift > 40%
        (Accepted Surgical Patch)        (Flagged: Over-rewriting detected)
                  │                                   │
                  │                                   ▼
                  │                        Fallback: `_apply_simple_fix`
                  │                        Direct Regex String Replacement
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    ▼
                       Surgical Fix File Payload
                       Returned to Bun Control Plane
```

### The Principle of Minimum Effective Change
- **Targeted Line Replacement**: Edits only 1 to 5 lines per defect.
- **Zero Collateral Refactoring**: Does not reformat untouched functions, reorder imports, or change coding styles.
- **Preserve All Artifacts**: Comments, docstrings, type annotations, and license headers remain 100% intact.

### Automated Drift Guardrail
If a worker LLM attempts to rewrite or reformat the entire file instead of making a surgical change, the line drift ratio is calculated:

$$\text{Drift Ratio} = \frac{|\text{Fixed Line Count} - \text{Original Line Count}|}{\max(\text{Original Line Count}, 1)}$$

- If $\text{Drift Ratio} > 0.40$ (i.e. more than 40% of the file changed), the patch is **rejected**.
- The system automatically triggers the `_apply_simple_fix` regex fallback, executing direct string substitution using the issue's `suggested_fix` property.

---

## 6. Deep Dive: Dynamic Tool Planning & ReAct Agent Loop

For interactive codebase chat and exploration ([`src/ai_service/agent/agent_loop.py`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/agent_loop.py)), the Orchestrator dynamically queries knowledge base tools:

```
User Question ──► Orchestrator (plan_tool_calls) ──► FastMCP Tool Execution
                        ▲                                    │
                        │                                    ▼
                 Next Turn Decision ◄──────────────── Observation & Citations
                        │
                        ▼ (Once sufficient context collected)
                 Final Cited Answer
```

### FastMCP Tools Orchestrated by the Agent
1. `tool_hybrid_search`: Combines vector semantic search (ChromaDB) with graph symbol lookup (Neo4j).
2. `tool_get_blast_radius`: Traverses call graphs to assess downstream ripple effects.
3. `tool_get_file_dependencies`: Explores incoming and outgoing file-level imports.
4. `tool_get_symbol_details`: Retrieves function signatures, docstrings, and callers.
5. `tool_cpg_reachable_guards`: Retrieves dominating control-flow guards from Joern CPG.
6. `tool_cpg_callers_with_args`: Inspects arguments passed at call sites.

All steps stream via Server-Sent Events (SSE) directly to the Next.js frontend with millisecond latency metrics.

---

## 7. Configuration & Environment Reference

The Orchestrator and Worker can be configured independently via `.env`:

```ini
# Orchestrator Configuration
ORCHESTRATOR_PROVIDER=gemini        # 'gemini', 'ollama', or 'groq'
ORCHESTRATOR_MODEL=gemini-3.6-flash # Model ID when using Ollama/Groq

# Worker Configuration
WORKER_PROVIDER=ollama              # 'ollama', 'groq', or 'gemini'
OLLAMA_MODEL=qwen2.5-coder:latest   # Local Ollama model tag
OLLAMA_BASE_URL=http://localhost:11434

# API Keys
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

### Modifying Prompts at Runtime
System prompts are decoupled into dedicated templates in `src/ai_service/prompts/` and can be customized via the REST API without redeploying:
- `GET /api/prompts`: List all active prompt templates.
- `GET /api/prompts/{key}`: View prompt text (e.g., `pr_orchestrator`, `pr_reviewer_worker`, `fixer_orchestrator`, `fixer_worker`).
- `PUT /api/prompts/{key}`: Update prompt text with immediate in-memory persistence.
- `POST /api/prompts/{key}/reset`: Reset to factory defaults.

---

## 8. Summary Comparison

```
┌─────────────────────────────────┬─────────────────────────────────┐
│       ORCHESTRATOR ROLE         │          WORKER ROLE            │
├─────────────────────────────────┼─────────────────────────────────┤
│ • Macro decision-maker          │ • Micro hunk scanner            │
│ • Knowledge graph reasoning     │ • High-throughput execution     │
│ • Multi-tool MCP planning       │ • Line-level bug localization   │
│ • Defensive falsification       │ • Syntax & gotcha detection     │
│ • Surgical fix architect        │ • Precision file patching       │
│ • Final PR review verdict       │ • Strict JSON / Delimiters      │
└─────────────────────────────────┴─────────────────────────────────┘
```

By decoupling high-level architectural reasoning (Orchestrator) from high-speed, line-by-line inspection and patching (Worker), GitAmi achieves high-precision defect detection with zero false negatives while keeping token consumption and review latency low.
