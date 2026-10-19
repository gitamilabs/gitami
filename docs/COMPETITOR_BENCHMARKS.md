# Competitor & Ablation Benchmark Guide

This guide describes how to run and evaluate rival architectures against GitAmi to produce rigorous empirical research results for paper submission.

---

## 1. Configurations Under Evaluation

| Configuration ID | Strategy | Knowledge Base | LLM Architecture | Conv. Gate | Simulation Philosophy |
|---|---|---|---|---|---|
| **B1** | Baseline 1 (Standard LLM) | None (Raw Diff Only) | Single (Gemini 2.0 Flash) | Disabled | Pure zero-shot diff review directly prompting Gemini 2.0 Flash. No Neo4j, no Chroma, no ReAct, no convention checks. Exactly 1 Gemini call per case. |
| **B2** | Baseline 2 (Vector RAG Only) | ChromA (Only) | Dual-LLM (Groq Worker + Gemini Orch) | Enabled | Ingests into Chroma only. Performs semantic vector retrieval. Runs convention gate. Groq Worker analyzes hunks + vector chunks; Gemini Orchestrator synthesizes review. No Neo4j. |
| **A1** | Ablation 1 (Graph Only) | Neo4j Only (No Vector) | Dual-LLM (Groq Worker + Gemini Orch) | Enabled | Ingests into Neo4j only. Traverses call graph for blast radius & dependents. Runs convention gate. Groq Worker analyzes hunks + blast radius; Gemini Orchestrator synthesizes review. No Chroma. |
| **A2** | Ablation 2 (Worker Only) | Dual KB (Neo4j + Chroma) | Worker Only (Llama-70B) | Enabled | Ingests into both Neo4j & Chroma. Retrieves blast radius + vector context. Runs convention gate. **Evaluated solely by Groq Llama-3.3-70B**. Zero Gemini API calls! |
| **A3** | Ablation 3 (Orchestrator Only) | Dual KB (Neo4j + Chroma) | Orch. Only (Gemini 2.0) | Enabled | Ingests into both Neo4j & Chroma. Retrieves blast radius + vector context. Runs convention gate. **Evaluated solely by Gemini 2.0 Flash**. Zero Groq API calls! |
| **GitAmi (Proposed)** | Proposed System | Dual KB (Neo4j + Chroma) | Dual-LLM + ReAct Agent | Enabled | Reference baseline: 4-step autonomous ReAct agent loop, hybrid search, bidirectional blast radius, surgical fixer. |

---

## 2. API Key Rotation & Token Budget (Free Tier)

All 5 competitor simulations are designed to complete across 443 test cases (50 Martian PRs + 393 VulnGym cases) within 24 hours on free API keys:

- **Gemini Free Tier**: 15 RPM, 1,500 RPD per key.
- **Groq Free Tier**: 30 RPM, 14,400 RPD per key.
- Total Gemini calls across all 5 configs = ~1,772 calls (Configuration A2 consumes 0 Gemini tokens!).
- Total Groq calls across all 5 configs = ~1,329 calls (<10% of 1 Groq key daily quota).

### Multi-Key Configuration in `.env`:
```env
# Provide multiple free Gemini keys separated by commas for automatic round-robin rotation & 429 failover
GEMINI_API_KEYS="key_alpha,key_beta,key_gamma"

# Provide multiple free Groq keys
GROQ_API_KEYS="gsk_key1,gsk_key2"
```

You can also pass keys directly at runtime:
```bash
python -m ai_service.cli benchmark-competitors run --config B1 --gemini-keys "key1,key2" --groq-keys "groq1"
```

---

## 3. Team Member Division & Independent Execution

Because each configuration has its **own isolated checkpoint file**, teammates can run benchmarks in parallel without collision.

### Step 1: Check out the branch
```bash
git checkout competitor-benchmarks
cd backend/ai-service
```

### Step 2: Run a Specific Configuration

#### Teammate 1: Baseline B1 (Standard LLM / Raw Diff)
```bash
# 5-case pilot test:
python -m ai_service.cli benchmark-competitors run --config B1 --pilot

# Full Martian (50 PRs):
python -m ai_service.cli benchmark-competitors run --config B1 --dataset martian

# Full VulnGym (393 Cases):
python -m ai_service.cli benchmark-competitors run --config B1 --dataset vulngym
```

#### Teammate 2: Baseline B2 (Vector RAG Only) & Ablation A1 (Graph Only)
```bash
# Run B2:
python -m ai_service.cli benchmark-competitors run --config B2 --pilot
python -m ai_service.cli benchmark-competitors run --config B2 --dataset martian
python -m ai_service.cli benchmark-competitors run --config B2 --dataset vulngym

# Run A1:
python -m ai_service.cli benchmark-competitors run --config A1 --pilot
python -m ai_service.cli benchmark-competitors run --config A1 --dataset martian
python -m ai_service.cli benchmark-competitors run --config A1 --dataset vulngym
```

#### Teammate 3: Ablation A2 (Worker Only) & Ablation A3 (Orchestrator Only)
```bash
# Run A2 (Uses Groq Llama-3.3-70B only, ZERO Gemini quota consumed):
python -m ai_service.cli benchmark-competitors run --config A2 --pilot
python -m ai_service.cli benchmark-competitors run --config A2 --dataset martian
python -m ai_service.cli benchmark-competitors run --config A2 --dataset vulngym

# Run A3:
python -m ai_service.cli benchmark-competitors run --config A3 --pilot
python -m ai_service.cli benchmark-competitors run --config A3 --dataset martian
python -m ai_service.cli benchmark-competitors run --config A3 --dataset vulngym
```

---

## 4. Checkpointing & Resumption

Each configuration checkpoints to:
`backend/ai-service/benchmark_results/competitors/checkpoints/checkpoint_<CONFIG_ID>.json`

- **Automatic Resume**: Runs automatically resume by default (`--resume`). If interrupted by rate limits or closed terminals, simply rerun the same command to pick up from the exact test case where it left off.
- **Restart Fresh**: If you need to restart a specific configuration from scratch:
  ```bash
  python -m ai_service.cli benchmark-competitors clear --config B1
  ```

---

## 5. Live Status & Comparison Matrix

### Check Live Progress across all 5 Configurations:
```bash
python -m ai_service.cli benchmark-competitors status
```

### Compile & Display the Comparison Matrix:
```bash
python -m ai_service.cli benchmark-competitors matrix
```

This compiles all completed checkpoints and baseline reports into:
- `backend/ai-service/benchmark_results/competitors/matrix/competitor_comparison_matrix_latest.md`
- `backend/ai-service/benchmark_results/competitors/matrix/competitor_comparison_matrix_latest.json`
