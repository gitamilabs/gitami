# GitAmi Rate-Limit-Safe Router & Stateful Orchestrator: Implementation Plan

A comprehensive architectural specification and implementation roadmap for GitAmi's **Deterministic Router** and **Stateful Orchestrator with Batched Falsification**, designed to maximize **Recall** and **Precision** while strictly adhering to **Free-Tier API constraints** (Google Gemini: 15 RPM; Groq: 30 RPM & strict burst TPM ceilings; Ollama: local/unlimited).

---

## 1. Executive Summary & Core Objective

The GitAmi PR Review Agent analyzes pull requests using AST graphs (Neo4j), vector search, and Code Property Graphs (Joern CPG). The goal of this architecture is to transition from a static, blind fan-out pipeline to an intelligent, multi-stage routing and verification system without exceeding free-tier LLM rate limits.

### Core Problems Solved:
1. **Attention Dilution (Hurts Recall)**: A generic worker inspecting for security, async, gotchas, and memory leaks in a single prompt frequently misses subtle concurrency and taint defects.
2. **Self-Confirmation Bias (Hurts Precision)**: When the same model proposes and falsifies a defect, it tends to rationalize false positives.
3. **Context Starvation (Hurts Recall & Costs Tokens)**: Unfiltered diffs including 10,000-line lockfiles or generated bundles saturate context windows, truncating actual code hunks.
4. **Rate-Limit Exhaustion (Breaks Free-Tier APIs)**: Naive $Files \times Specialists$ Cartesian fan-outs fire 20+ parallel requests, instantly tripping Groq's burst TPM ceiling and Gemini's 15 RPM cap.

---

## 2. Free-Tier Rate & Token Budget Blueprint

Every PR review operates within a strict **Hard Call Ceiling**:

| Stage | Target Provider | Max Calls Per PR | Concurrency Limit |
| :--- | :--- | :--- | :--- |
| **1. Tier-1 Router** | Pure Python (No LLM) | **0 calls** | Instantaneous |
| **2. Specialist Worker Scan** | Groq (or Local Ollama) | **1–3 calls** | `asyncio.Semaphore(2)` |
| **3. Stateful Planner Loop** | Gemini (Orchestrator) | **1–2 calls** | Sequential |
| **4. Batched Verifier (5-Step)**| Gemini (or Ollama Fallback) | **1 call (batched)** | Sequential |
| **5. Final Aggregator & Verdict**| Gemini (Orchestrator) | **1 call** | Sequential |
| **TOTAL EXTERNAL API CALLS:** | — | **4 to 6 calls max** | **Safely below 15 RPM / 6k TPM** |

---

## 3. Architecture & Data Flow

```
                               Incoming PR Diff
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │  Phase 1: Pure-Python │
                          │   Tier-1 AST Router   │
                          └───────────┬───────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                ▼                     ▼                     ▼
          [All 'skip']           ['light']             ['standard' / 'deep']
          (Lockfiles/Docs)     (Tests/Styles)          (Application Logic)
                │                     │                     │
                ▼                     ▼                     ▼
           Short-Circuit       Single Generic        Sparse Specialist Dispatch
          ACCEPT (0 calls)     Worker (1 call)       (Max 2 workers, Semaphore=2)
                                                            │
                                                            ▼
                                                 Candidate Issues Aggregated
                                                            │
                                                            ▼
                                                 ┌─────────────────────┐
                                                 │ Phase 4: Bounded    │
                                                 │ Stateful Loop       │
                                                 │ (Max 2 tool steps)  │
                                                 └──────────┬──────────┘
                                                            │ Fetches CPG/Graph Evidence
                                                            ▼
                                                 ┌─────────────────────┐
                                                 │ Batched 5-Step      │
                                                 │ Verifier (1 call)   │
                                                 └──────────┬──────────┘
                                                            │ Falsifies Non-Issues
                                                            ▼
                                                 Final Verdict & Report
```

---

## 4. Phased Implementation Roadmap

### Phase 0: Baseline & Measurement Harness (2 Days)

Without an empirical baseline, it is impossible to verify whether routing improves precision or harms recall.

- **Eval Harness**: Utilize the existing Martian PR Benchmark (50 PRs, 173 golden comments) and Tencent VulnGym (408 CVEs) documented in [BENCHMARK_GUIDE.md](file:///c:/Users/sumed/PycharmProjects/final-year-project/docs/BENCHMARK_GUIDE.md).
- **Telemetry Record**: Add `ReviewTrace` in `backend/ai-service/src/ai_service/agent/telemetry.py`:
  ```python
  @dataclass
  class ReviewTrace:
      pr_id: str
      tier_plan: dict
      llm_calls_by_provider: dict[str, int]  # e.g., {"gemini": 2, "groq": 3, "ollama": 0}
      tokens_in: int
      tokens_out: int
      latency_ms: float
      candidates_proposed: int
      candidates_verified: int
      dismissal_reasons: list[str]
  ```
- **Replay Script**: Implement `scripts/eval_reviews.py` to run 15 representative PRs and output a baseline summary table (Precision, Recall, F1, API Call Count, Latency).

**Done when:** One command (`python scripts/eval_reviews.py`) outputs baseline metrics and per-provider API call counts.

---

### Phase 1: Deterministic Tier-1 Router (3 Days)

Pure-function classification that eliminates token waste and short-circuits zero-risk PRs with **0 LLM calls**.

**Target File:** `backend/ai-service/src/ai_service/agent/router.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class FileRoute:
    path: str
    tier: Literal["skip", "light", "standard", "deep"]
    specialists: list[str]
    reasons: list[str]

@dataclass
class RoutePlan:
    files: list[FileRoute]
    run_graph: bool
    run_cpg: bool
    run_vector: bool
    all_skipped: bool
```

#### Classification Rules:
- **`skip`** (0 LLM calls $\rightarrow$ short-circuit directly to `ACCEPT`):
  - Lockfiles: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`, `composer.lock`.
  - Static assets: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`, `.woff`, `.ttf`.
  - Minified/Generated bundles: `*.min.js`, `*.min.css`, `*.pb.go`, `*_pb2.py`.
- **`light`** (1 generic worker call, skip graph & CPG):
  - Pure documentation (`*.md`, `*.rst`, `LICENSE`), formatting, and test-only modifications without production logic changes.
- **`deep`** (Full specialist inspection + Joern CPG taint analysis + Neo4j blast radius):
  - Sensitive sinks detected: `eval\(`, `exec\(`, `subprocess`, `db\.execute`, `innerHTML`, raw SQL string formatting.
  - Critical paths: `auth/`, `payments/`, `security/`, `crypto/`, `api/v1/billing/`.
- **`standard`**: All other application code.

#### Integration in `reviewer.py`:
- Call `build_route_plan(diff)` immediately after diff parsing.
- If `route_plan.all_skipped` is `True`, immediately return `ACCEPT` with an explanatory note (0 API calls).
- Gate CPG and Neo4j queries on `route_plan.run_cpg` and `route_plan.run_graph`.
- Gate behind environment flag `ROUTER_ENABLED=true`.

**Done when:** Lockfile-only PRs exit in $<100\text{ms}$ with 0 LLM calls, and source PRs route correctly without dropping security-sensitive files.

---

### Phase 2: Rate-Limited Specialist Workers (3–4 Days)

Eliminates prompt attention dilution by using targeted worker prompts while avoiding Cartesian fan-out explosion.

#### Prompt Decoupling in `src/ai_service/prompts/`:
- `pr_worker_security`: Specializes in OWASP Top 10, sanitization sinks, and dynamic parameter taint.
- `pr_worker_async`: Specializes in unhandled Promises, race conditions, async loops, and missing `await`.
- `pr_worker_resources`: Specializes in unclosed file descriptors, memory leaks, and dangling event listeners.
- `pr_worker_generic`: Fallback logic for general syntax and language-specific gotchas.

#### Sparse Specialist Selection (Anti-429 Constraint):
Instead of fanning out all specialists on every file, select **at most 1 specialist per chunk** (or 2 if security sinks are present):
```python
def select_specialists_for_chunk(chunk_content: str, file_path: str) -> list[str]:
    specialists = []
    if SINK_REGEX.search(chunk_content) or is_auth_path(file_path):
        specialists.append("pr_worker_security")
    elif ASYNC_REGEX.search(chunk_content):
        specialists.append("pr_worker_async")
    elif RESOURCE_REGEX.search(chunk_content):
        specialists.append("pr_worker_resources")
    
    if not specialists:
        specialists.append("pr_worker_generic")
    return specialists[:2]  # Strict cap of 2 specialists maximum per chunk
```

#### Worker Concurrency Semaphore:
In [reviewer.py](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/reviewer.py):
```python
WORKER_SEMAPHORE = asyncio.Semaphore(2)  # Never more than 2 parallel worker requests

async def _safe_inspect_chunk(client, chunk, prompt_key):
    async with WORKER_SEMAPHORE:
        return await client.run_worker(chunk, prompt_key=prompt_key)
```

**Done when:** A 5-file PR dispatches $\le 3$ total worker calls, respects the concurrency limit, and produces zero Groq 429 rate limit errors.

---

### Phase 3: Provider Optimization & Offloading in `DualLLMClient` (2 Days)

Intelligent model assignment in [llm_client.py](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/llm_client.py) to preserve cloud quotas.

1. **Local Offloading**:
   - If local Ollama is active (`OLLAMA_BASE_URL`), automatically route **all worker inspection tasks** to local Ollama (`qwen2.5-coder`). Local Ollama has 0 rate limits and 0 cost.
   - If Ollama is unavailable, route workers to Groq, strictly regulated by `WORKER_SEMAPHORE`.
2. **Asymmetric Verification Pairing**:
   - Proposer: Groq (`llama-3.3-70b` / `qwen3.8-27b`) or Ollama (`qwen2.5-coder`).
   - Verifier: Google Gemini (`gemini-3.5-flash-lite` or `gemini-3.6-flash`).
   - Asymmetric pairing breaks self-confirmation bias without burning additional calls.

**Done when:** Telemetry demonstrates workers running on Groq/Ollama and verifiers running on Gemini without cross-quota interference.

---

### Phase 4: Bounded Stateful Orchestrator with Batched Verification (4–5 Days)

On-demand evidence gathering coupled with a single-call 5-step falsification engine.

**Target File:** `backend/ai-service/src/ai_service/agent/orchestrator.py`

#### Bounded State Machine:
```python
@dataclass
class ReviewState:
    plan: RoutePlan
    candidates: list[Issue]
    evidence: dict[str, Any]
    verified: list[Issue]
    dismissed: list[tuple[Issue, str]]
    steps_used: int = 0
    max_steps: int = 2   # Hard limit for Free-Tier!
    status: Literal["running", "done", "escalate"] = "running"
```

#### Loop Execution (Max 2 Steps):
1. **Planner Step (Gemini - 1 call)**:
   - Given the candidates and diff, the planner decides if external evidence is required.
   - Allowed actions: `fetch_cpg_guards`, `fetch_cpg_callers`, `fetch_blast_radius`, or `verify_and_finalize`.
   - Tool execution runs against FastMCP tools.
2. **Batched 5-Step Falsifier (Gemini - 1 call)**:
   - **Critical Rule**: All candidate issues are sent together in a **single prompt**, eliminating per-candidate round trips:
   ```json
   {
     "candidates": [...],
     "cpg_guards": [...],
     "upstream_callers": [...]
   }
   ```
   - Verifier applies the **Zero False Negative Protocol**: Presence checks (`if (x)`) and auth checks do **not** dismiss issues. Only mathematical/cryptographic neutralization or compile-time static safety falsifies a candidate.
3. **Escalation Valve**:
   - If `steps_used >= max_steps` and a critical candidate remains unresolved, flag as `needs_human_review` instead of guessing or auto-dismissing.

**Done when:** Complex multi-file PRs with 5+ candidates are verified in **a single batched verification call**, cutting false positives while consuming $\le 3$ Gemini calls.

---

### Phase 5: Deterministic Fixer & AST Grammar Validation (3 Days)

Eliminates LLM usage for mechanical syntax adjustments and guarantees valid patches.

**Target File:** `backend/ai-service/src/ai_service/agent/fixer.py`

1. **Mechanical Fix Classifier**:
   - Known deterministic patterns (`.size()` $\rightarrow$ `.length`, missing `await` before known async methods) execute via regex/Tree-sitter (**0 LLM calls**).
   - Only non-trivial logic bugs route to the worker LLM patcher.
2. **Tree-sitter Syntax Guardrail**:
   - Parse patched code with Tree-sitter before returning. If `tree.root_node.has_error` is `True`, reject the patch and fall back to the review comment.

**Done when:** 100% of generated fixes are syntactically valid code, and mechanical fixes consume 0 tokens.

---

### Phase 6: Chat Agent Intent Router (2 Days)

Optimizes codebase chat in [agent_loop.py](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/src/ai_service/agent/agent_loop.py):
- Classifies user questions into `symbol_lookup`, `file_deps`, `blast_radius`, or `open_ended`.
- Single-intent questions dispatch directly to the matching FastMCP tool without entering the iterative ReAct loop.

---

## 5. Environment Configuration Reference

Add these controls to [`backend/ai-service/.env`](file:///c:/Users/sumed/PycharmProjects/final-year-project/backend/ai-service/.env):

```ini
# =============================================================================
# RATE-LIMIT & ORCHESTRATION PROFILE
# =============================================================================
RATE_LIMIT_PROFILE=free_tier         # 'free_tier' or 'pro'
MAX_ORCHESTRATOR_STEPS=2            # Max tool loop steps (free_tier: 2, pro: 5)
WORKER_CONCURRENCY_LIMIT=2          # Max parallel Groq requests (Semaphore)
BATCH_VERIFICATION_ENABLED=true     # Always verify all candidates in 1 call

# Feature Flags
ROUTER_ENABLED=true
SPECIALISTS_ENABLED=true
STATEFUL_ORCH_ENABLED=true

# Providers
WORKER_PROVIDER=groq                # 'groq' or 'ollama' (set to 'ollama' for zero rate limits)
ORCHESTRATOR_PROVIDER=gemini        # 'gemini'
```

---

## 6. Metric Improvement Summary

| Metric | Mechanism | Expected Outcome |
| :--- | :--- | :--- |
| **Recall** ($\frac{TP}{TP + FN}$) | Specialist worker prompts + targeted Joern CPG caller evidence | **+20% to +35%** increase on complex concurrency and taint bugs. |
| **Precision** ($\frac{TP}{TP + FP}$) | Asymmetric Proposer-Verifier model pairing + 5-step falsification | **+15% to +25%** reduction in false alarms and hallucinations. |
| **Free-Tier Stability** | Pure Tier-1 Router + Concurrency Semaphore + Batched Verification | **0 HTTP 429 rate limit errors** across Groq and Gemini. |
