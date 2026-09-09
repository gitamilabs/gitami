import pytest
from ai_service.benchmark.dataset import BENCHMARK_CASES, BenchmarkCase
from ai_service.benchmark.evaluator import BenchmarkEvaluator, EvaluationMetrics


def test_benchmark_dataset_integrity():
    assert len(BENCHMARK_CASES) >= 10
    for case in BENCHMARK_CASES:
        assert case.case_id
        assert case.language in ("python", "javascript")
        assert case.cwe.startswith("CWE-")
        assert case.vulnerable_diff
        assert case.patched_diff
        assert len(case.vulnerable_evidence_nodes) > 0
        assert len(case.patched_falsification_nodes) > 0


def test_metrics_calculation():
    # 4 pairs:
    # 2 true positives (both flagged vuln and safe)
    # 1 false positive
    # 1 true negative
    metrics = EvaluationMetrics(
        mode="test",
        total_pairs=4,
        true_positives=3,
        false_negatives=1,
        false_positives=1,
        true_negatives=3,
        pair_wise_correct=3,
        graph_grounding_hits=2,
        graph_grounding_total=4,
    )

    assert metrics.pair_wise_correct_rate == 0.75
    assert metrics.false_positive_rate == 0.25
    assert metrics.false_negative_rate == 0.25
    assert metrics.precision == 0.75
    assert metrics.recall == 0.75
    assert metrics.f1_score == 0.75
    assert metrics.graph_grounding_rate == 0.5


@pytest.mark.asyncio
async def test_benchmark_evaluator_simulated_run():
    evaluator = BenchmarkEvaluator(simulated=True)
    sample_cases = BENCHMARK_CASES[:2]
    results = await evaluator.run_benchmark(cases=sample_cases, mode="both")

    assert "baseline" in results["modes"]
    assert "agentic" in results["modes"]
    assert "comparison" in results

    agent_sum = results["modes"]["agentic"]["summary"]
    assert agent_sum["pair_wise_correct_rate"] == "100.0%"
    assert agent_sum["false_positive_rate"] == "0.0%"
