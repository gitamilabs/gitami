# GitAmi Benchmarking Framework

> **Full Documentation**: See the detailed guide in [docs/BENCHMARK_GUIDE.md](../../docs/BENCHMARK_GUIDE.md).

## Quick Start Commands

Run all commands from `backend/ai-service`:

```powershell
# 1. Quick smoke test (3 cases across both benchmarks)
python -m ai_service.cli benchmark run --dataset all --sample 3

# 2. Run full evaluation across both suites (Martian + VulnGym)
python -m ai_service.cli benchmark run --dataset all

# 3. Run individual benchmark
python -m ai_service.cli benchmark run --dataset martian
python -m ai_service.cli benchmark run --dataset vulngym

# 4. Filter by language (e.g. Python only)
python -m ai_service.cli benchmark run --dataset all --language python

# 5. Compare two benchmark iterations to measure improvements/regressions
python -m ai_service.cli benchmark compare -b ./benchmark_results/run1.json -c ./benchmark_results/run2.json

# 6. Purge benchmark records from Neo4j & ChromaDB
python -m ai_service.cli benchmark cleanup
```

## Generated Reports
All reports are saved to `backend/ai-service/benchmark_results/`:
- `benchmark_report_<timestamp>.md` (Human-readable Markdown summary with Precision, Recall, F1, Category & Severity tables)
- `benchmark_report_<timestamp>.json` (Full raw evaluation metrics and predictions)
