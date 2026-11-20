# GitAmi Benchmarking Framework Guide

A standardized, industry-grade evaluation framework for testing and measuring the accuracy, recall, and reliability of the **GitAmi Pull Request Review & Vulnerability Detection Agent**.

---

## 1. Overview & Purpose

When modifying agent prompts, Knowledge Base retrieval logic, graph traversal heuristics, or LLM models, how do you verify if the changes actually improve code review quality without causing regressions?

The **GitAmi Benchmarking Framework** solves this by evaluating GitAmi against verified, industry-standard ground truth datasets:
- **No Mocking**: Repositories are **actually indexed into the real Knowledge Base** (Neo4j AST graph + ChromaDB vector embeddings) via `run_init_job()`.
- **Autonomous Review Pipeline**: Pull requests and defect commits are reviewed by the live `run_agentic_pr_review` agent using FastMCP tools and dual LLMs.
- **Guaranteed Cleanup**: The Knowledge Base is automatically purged after each test case, preventing data contamination.
- **Quantitative Metrics**: Measures Precision, Recall, F1 Score, category breakdowns (Security, Bug, Performance, Convention), severity detection rates, and latency.
- **Iterative Comparison**: Built-in diff mode compares run results across code revisions to identify improvements and regressions.

---

## 2. Benchmark Datasets

The framework integrates two complementary benchmarks:

### A. Martian Code Review Benchmark
- **Source**: [withmartian/code-review-benchmark](https://github.com/withmartian/code-review-benchmark)
- **Scale**: 50 real-world Pull Requests with **173 golden comments** authored and audited by human engineers.
- **Repositories**: Production codebases including Sentry (Python), Cal.com (TypeScript), Grafana (Go), Discourse (Ruby), and Keycloak (Java).
- **Categories Covered**: `bug`, `security`, `concurrency`, `perf`, `data`, `api`, `style`, `doc_defect`, `test_gap`.
- **Severity Levels**: `Critical`, `High`, `Medium`, `Low`.
- **Focus**: Evaluates PR-level code review thoroughness, false-positive suppression, and actionable suggestions.

### B. Tencent VulnGym Benchmark
- **Source**: [Tencent/VulnGym](https://github.com/Tencent/VulnGym)
- **Scale**: **408 vulnerability entries** across **184 GitHub Advisories** (CVEs/GHSAs) in 23 AI/developer repositories.
- **Repositories**: Open-WebUI, FastMCP, LiteLLM, MLflow, Langflow, AutoGPT, Apache Airflow, NLTK, Flowise, etc.
- **Quality**: Filtered for human-verified (`verify: 1`) ground truth entries with exact defect locations (`critical_operation`), entry points, and taint-flow traces.
- **Categories Covered**: XSS, SQL Injection, RCE, SSRF, CSRF, Path Traversal, Authentication Bypass, Insecure Deserialization, etc.
- **Focus**: Evaluates vulnerability detection recall, critical issue severity classification, and precise defect location pinpointing.

---

## 3. Architecture & Key Features

```
                                  GitAmi Benchmarking Suite
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
         Martian Adapter (PRs)                                VulnGym Adapter (CVEs)
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              ▼
                                   BenchmarkTestCase Units
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
           1. Ingest into Real KB                         2. Staged Repository Dir
         (Neo4j Graph + ChromaDB)                      (D:\gitami-benchmark-repos)
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                                  run_agentic_pr_review()
                                 (FastMCP Tools + Dual LLM)
                                              │
                                              ▼
                                 Predicted Issues & Verdict
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
          BenchmarkKBContext.__aexit__                       BenchmarkScorer
          - Neo4j DETACH DELETE nodes                    - Bipartite issue matching
          - ChromaDB vector deletion                     - Precision / Recall / F1
          - Invalidate vector manifests                  - Category & Severity metrics
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                                  Markdown & JSON Reports
                                 (./benchmark_results/)
```

### Storage Isolation
- Cloned benchmark repositories are stored outside the GitAmi project directory at **`D:\gitami-benchmark-repos`** (configurable).
- You can delete this directory at any time without impacting GitAmi.

### Knowledge Base Safety
- All benchmark runs use isolated namespace IDs (`benchmark_<case_id>`).
- The `BenchmarkKBContext` async context manager guarantees that all Neo4j nodes/edges and ChromaDB embeddings are purged upon completion or failure.

---

## 4. Prerequisites & Environment Setup

Ensure your environment is configured before executing benchmarks:

1. **Configure `.env`** in `apps/ai/.env`:
   ```env
   # Neo4j Graph Database
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=neo4j

   # Vector Database & Embeddings
   VECTOR_DB=chroma_cloud       # or chroma_local
   EMBEDDER=gemini              # or sentence-transformers
   GEMINI_API_KEY=your_gemini_api_key

   # Dual LLM Orchestrator
   GROQ_API_KEY=your_groq_api_key
   ```

2. **Navigate to the AI Service Directory**:
   ```powershell
   cd "backend\ai-service"
   ```

3. **Activate the Virtual Environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

---

## 5. How to Run the Benchmarks

All benchmark commands are available under `python -m ai_service.cli benchmark`.

### A. Quick Smoke Test (Recommended First)
Before running hundreds of cases, test with a small sample (e.g., 3 cases) to verify that the Knowledge Base, models, and scoring pipeline are functioning:

```powershell
python -m ai_service.cli benchmark run --dataset all --sample 3
```

### B. Run Full Benchmark Suite
To evaluate the complete dataset across both Martian and VulnGym:

```powershell
python -m ai_service.cli benchmark run --dataset all
```

### C. Run Individual Datasets
You can run Martian or VulnGym independently:

```powershell
# Run only Martian PR Review benchmark
python -m ai_service.cli benchmark run --dataset martian

# Run only VulnGym Vulnerability Detection benchmark
python -m ai_service.cli benchmark run --dataset vulngym
```

### D. Filter by Programming Language
Evaluate only test cases matching specific languages:

```powershell
# Evaluate Python test cases only
python -m ai_service.cli benchmark run --dataset all --language python

# Evaluate Python and TypeScript test cases
python -m ai_service.cli benchmark run --dataset all -l python -l typescript
```

### E. Retain Knowledge Base for Manual Inspection
By default, the Knowledge Base is automatically purged after each test case. To keep the indexed graph and vectors in Neo4j/ChromaDB for inspection:

```powershell
python -m ai_service.cli benchmark run --dataset martian --sample 1 --no-cleanup
```

### F. Custom Repos and Results Directories
```powershell
python -m ai_service.cli benchmark run `
  --dataset all `
  --repos-dir "D:\my-benchmark-repos" `
  --results-dir "./my_results"
```

---

## 6. Output & Reports

Benchmark results are automatically saved to `apps/ai/benchmark_results/`:

### 1. Markdown Report (`benchmark_report_YYYYMMDD_HHMMSS.md`)
Human-readable summary containing:
- **Overall Performance Metrics**: Precision, Recall, F1 Score, True Positives (TP), False Positives (FP), False Negatives (FN).
- **Category Breakdown Table**: Detection rates for *Security*, *Bug*, *Performance*, and *Convention*.
- **Severity Breakdown Table**: Detection rates for *Critical/Error*, *Warning*, and *Info*.
- **Per-Testcase Summary Table**: Breakdown of predictions, ground-truth matches, and latency for each test case.

#### Sample Markdown Report Excerpt:
```markdown
# GitAmi Benchmark Evaluation Report

**Run Timestamp**: `2026-09-09 13:50:00`
**Datasets Evaluated**: `martian, vulngym`
**Total Cases**: `20`
**Mean Latency**: `4.25s per case`

## 1. Overall Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **78.6%** | True Positives / Total Predictions (22/28) |
| **Recall** | **73.3%** | True Positives / Ground Truth Issues (22/30) |
| **F1 Score** | **0.7586** | Harmonic mean of Precision and Recall |
| **True Positives (TP)** | `22` | Successfully detected ground-truth defects |
| **False Positives (FP)** | `6` | Hallucinated or spurious issues |
| **False Negatives (FN)** | `8` | Missed ground-truth defects |

## 2. Category Breakdown

| Category | Detected | Total Ground Truth | Detection Rate |
| :--- | :--- | :--- | :--- |
| **Security** | 12 | 14 | 85.7% |
| **Bug** | 8 | 11 | 72.7% |
| **Performance** | 2 | 3 | 66.7% |
| **Convention** | 0 | 2 | 0.0% |
```

### 2. JSON Report (`benchmark_report_YYYYMMDD_HHMMSS.json`)
Machine-readable dataset containing:
- Full configuration parameters and timestamps.
- Aggregate metrics.
- Complete per-testcase predictions, raw issues, ground-truth objects, bipartite match pairs, and unpredicted items.

---

## 7. Regression Testing & Iteration Comparison

When making changes to reviewer prompts (`ai_service/agent/prompts.py`), scoring logic, or model parameters, compare the new candidate run against a baseline run:

```powershell
python -m ai_service.cli benchmark compare `
  --baseline ./benchmark_results/benchmark_report_20260901_100000.json `
  --candidate ./benchmark_results/benchmark_report_20260909_120000.json `
  --output ./benchmark_results/comparison_prompt_v2.md
```

### Comparison Output Example:
```markdown
# GitAmi Benchmark Comparison Report

- **Baseline Run**: `benchmark_report_20260901_100000.json`
- **Candidate Run**: `benchmark_report_20260909_120000.json`

## Aggregate Metrics Comparison

| Metric | Baseline | Candidate | Delta | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Precision** | 65.0% | 78.6% | +13.6% | 📈 Improved |
| **Recall** | 60.0% | 73.3% | +13.3% | 📈 Improved |
| **F1 Score** | 0.6240 | 0.7586 | +0.1346 | 📈 Improved |
| **Mean Latency** | 5.10s | 4.25s | -0.85s | ⚡ Faster |

## Case-Level Deltas

### 🎉 Improvements (3 cases)
- **`martian_sentry_1`**: F1 improved from `0.50` to `1.00` (+0.50)
- **`vulngym_entry-00057`**: F1 improved from `0.00` to `0.80` (+0.80)

### ⚠️ Regressions (0 cases)
No regressions observed.
```

---

## 8. Maintenance & Cleanup

To manually purge any orphaned benchmark data or wipe downloaded repositories:

```powershell
# 1. Purge all orphaned benchmark data from Neo4j & ChromaDB
python -m ai_service.cli benchmark cleanup

# 2. Purge Knowledge Base entries with a custom prefix
python -m ai_service.cli benchmark cleanup --prefix benchmark_

# 3. Purge Knowledge Base AND delete all cloned repos from D:\gitami-benchmark-repos
python -m ai_service.cli benchmark cleanup --purge-repos
```

---

## 9. Running Automated Tests

The benchmarking framework includes a comprehensive test suite in `apps/ai/tests/unit/test_benchmark.py`:

```powershell
python -m pytest tests/test_benchmark.py -v
```

Tests cover:
- Configuration defaults and directory creation.
- Line span and range parser normalization.
- Normalized file path matching heuristics.
- Jaccard token text similarity.
- Ground truth proximity tolerance checks.
- Bipartite issue matching (True Positives, False Positives, False Negatives).
- Aggregate score computation and category/severity breakdown.
- Report generation (Markdown and JSON).
- Run comparison diff calculation.
- Knowledge Base lifecycle manager cleanup and teardown.
- End-to-end benchmark runner orchestration.

---

## 10. Summary CLI Reference

| Command | Description |
| :--- | :--- |
| `python -m ai_service.cli benchmark run --help` | Show all run options |
| `python -m ai_service.cli benchmark run -d all -s 3` | Run 3 sample cases across all datasets |
| `python -m ai_service.cli benchmark run -d martian` | Run Martian Code Review benchmark |
| `python -m ai_service.cli benchmark run -d vulngym` | Run Tencent VulnGym benchmark |
| `python -m ai_service.cli benchmark run -d all -l python` | Run all benchmarks for Python codebases |
| `python -m ai_service.cli benchmark run -d martian --no-cleanup` | Run without purging Neo4j/ChromaDB |
| `python -m ai_service.cli benchmark compare -b <base.json> -c <cand.json>` | Compare two benchmark runs |
| `python -m ai_service.cli benchmark cleanup` | Purge all benchmark entries from Neo4j/ChromaDB |
| `python -m ai_service.cli benchmark cleanup --purge-repos` | Purge KB and delete cloned repos from disk |
