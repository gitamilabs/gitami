"""Report generator for benchmark results (Markdown, JSON, and comparison mode)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_service.benchmark.scorer import AggregateScore, TestCaseScore


class BenchmarkReportGenerator:
    """Formats benchmark evaluation metrics into Markdown and JSON artifacts."""

    @staticmethod
    def generate_json(
        aggregate_score: AggregateScore,
        case_scores: List[TestCaseScore],
        metadata: Dict[str, Any],
        out_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Produce structured JSON dictionary and optionally save to disk."""
        data = {
            "metadata": {
                **metadata,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "aggregate": {
                "total_cases": aggregate_score.total_cases,
                "total_ground_truth": aggregate_score.total_ground_truth,
                "total_predicted": aggregate_score.total_predicted,
                "true_positives": aggregate_score.total_tp,
                "false_positives": aggregate_score.total_fp,
                "false_negatives": aggregate_score.total_fn,
                "precision": aggregate_score.precision,
                "recall": aggregate_score.recall,
                "f1_score": aggregate_score.f1_score,
                "mean_duration_seconds": aggregate_score.mean_duration_seconds,
                "category_breakdown": aggregate_score.category_breakdown,
                "severity_detection_rates": aggregate_score.severity_detection_rates,
            },
            "cases": [
                {
                    "case_id": c.case_id,
                    "dataset": c.dataset_name,
                    "tp": c.true_positives,
                    "fp": c.false_positives,
                    "fn": c.false_negatives,
                    "precision": c.precision,
                    "recall": c.recall,
                    "f1_score": c.f1_score,
                    "duration_seconds": c.duration_seconds,
                    "matched_count": len(c.matched_pairs),
                    "matched_issues": [
                        {
                            "predicted_title": m.predicted.get("title", ""),
                            "predicted_file": m.predicted.get("file_path", ""),
                            "predicted_line": m.predicted.get("line"),
                            "gt_title": m.ground_truth.title,
                            "gt_file": m.ground_truth.file_path,
                            "gt_line": m.ground_truth.line_start,
                            "match_score": m.match_score,
                        }
                        for m in c.matched_pairs
                    ],
                    "unmatched_predictions": c.unmatched_predictions,
                    "unmatched_ground_truth": [
                        {
                            "title": gt.title,
                            "file": gt.file_path,
                            "line": gt.line_start,
                            "category": gt.category,
                            "severity": gt.severity,
                        }
                        for gt in c.unmatched_ground_truth
                    ],
                }
                for c in case_scores
            ],
        }

        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        return data

    @staticmethod
    def generate_markdown(
        aggregate_score: AggregateScore,
        case_scores: List[TestCaseScore],
        metadata: Dict[str, Any],
        out_path: Optional[Path] = None,
    ) -> str:
        """Generate human-readable GitHub-flavored Markdown evaluation report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datasets_str = ", ".join(metadata.get("datasets", []))

        lines = [
            f"# GitAmi Benchmark Evaluation Report",
            f"",
            f"**Run Timestamp**: `{timestamp}`  ",
            f"**Datasets Evaluated**: `{datasets_str}`  ",
            f"**Total Cases**: `{aggregate_score.total_cases}`  ",
            f"**Mean Latency**: `{aggregate_score.mean_duration_seconds}s per case`  ",
            f"",
            f"## 1. Overall Performance Metrics",
            f"",
            f"| Metric | Value | Description |",
            f"| :--- | :--- | :--- |",
            f"| **Precision** | **{aggregate_score.precision * 100:.1f}%** | True Positives / Total Predictions ({aggregate_score.total_tp}/{aggregate_score.total_predicted}) |",
            f"| **Recall** | **{aggregate_score.recall * 100:.1f}%** | True Positives / Ground Truth Issues ({aggregate_score.total_tp}/{aggregate_score.total_ground_truth}) |",
            f"| **F1 Score** | **{aggregate_score.f1_score:.4f}** | Harmonic mean of Precision and Recall |",
            f"| **True Positives (TP)** | `{aggregate_score.total_tp}` | Successfully detected ground-truth defects |",
            f"| **False Positives (FP)** | `{aggregate_score.total_fp}` | Spurious or hallucinated issues |",
            f"| **False Negatives (FN)** | `{aggregate_score.total_fn}` | Missed ground-truth defects |",
            f"",
            f"## 2. Category Breakdown",
            f"",
            f"| Category | Detected | Total Ground Truth | Detection Rate |",
            f"| :--- | :--- | :--- | :--- |",
        ]

        for cat, stats in sorted(aggregate_score.category_breakdown.items()):
            det = stats.get("detected", 0)
            tot = stats.get("total", 0)
            rate = stats.get("recall", 0.0) * 100
            lines.append(f"| **{cat.capitalize()}** | {det} | {tot} | {rate:.1f}% |")

        lines.extend([
            f"",
            f"## 3. Severity Breakdown",
            f"",
            f"| Severity | Detection Rate |",
            f"| :--- | :--- |",
        ])

        for sev, rate in sorted(aggregate_score.severity_detection_rates.items()):
            lines.append(f"| **{sev.capitalize()}** | {rate * 100:.1f}% |")

        lines.extend([
            f"",
            f"## 4. Per-Testcase Summary",
            f"",
            f"| Case ID | Dataset | Precision | Recall | F1 Score | TP/FP/FN | Latency |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for c in case_scores:
            p_pct = f"{c.precision * 100:.0f}%"
            r_pct = f"{c.recall * 100:.0f}%"
            f1_str = f"{c.f1_score:.2f}"
            counts = f"{c.true_positives}/{c.false_positives}/{c.false_negatives}"
            lines.append(
                f"| `{c.case_id}` | {c.dataset_name} | {p_pct} | {r_pct} | {f1_str} | {counts} | {c.duration_seconds:.2f}s |"
            )

        lines.append("")
        content = "\n".join(lines)

        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)

        return content


def compare_benchmark_runs(baseline_json_path: Path, candidate_json_path: Path) -> str:
    """Compare two benchmark runs to measure regressions or improvements."""
    with open(baseline_json_path, "r", encoding="utf-8") as f:
        base = json.load(f)
    with open(candidate_json_path, "r", encoding="utf-8") as f:
        cand = json.load(f)

    b_agg = base.get("aggregate", {})
    c_agg = cand.get("aggregate", {})

    b_p, c_p = b_agg.get("precision", 0.0), c_agg.get("precision", 0.0)
    b_r, c_r = b_agg.get("recall", 0.0), c_agg.get("recall", 0.0)
    b_f1, c_f1 = b_agg.get("f1_score", 0.0), c_agg.get("f1_score", 0.0)
    b_dur, c_dur = b_agg.get("mean_duration_seconds", 0.0), c_agg.get("mean_duration_seconds", 0.0)

    delta_p = (c_p - b_p) * 100
    delta_r = (c_r - b_r) * 100
    delta_f1 = c_f1 - b_f1
    delta_dur = c_dur - b_dur

    lines = [
        f"# GitAmi Benchmark Comparison Report",
        f"",
        f"- **Baseline Run**: `{baseline_json_path.name}` ({base.get('metadata', {}).get('generated_at', 'N/A')})",
        f"- **Candidate Run**: `{candidate_json_path.name}` ({cand.get('metadata', {}).get('generated_at', 'N/A')})",
        f"",
        f"## Aggregate Metrics Comparison",
        f"",
        f"| Metric | Baseline | Candidate | Delta | Status |",
        f"| :--- | :--- | :--- | :--- | :--- |",
        f"| **Precision** | {b_p * 100:.1f}% | {c_p * 100:.1f}% | {delta_p:+.1f}% | {'📈 Improved' if delta_p > 0 else '📉 Regressed' if delta_p < 0 else '➖ Unchanged'} |",
        f"| **Recall** | {b_r * 100:.1f}% | {c_r * 100:.1f}% | {delta_r:+.1f}% | {'📈 Improved' if delta_r > 0 else '📉 Regressed' if delta_r < 0 else '➖ Unchanged'} |",
        f"| **F1 Score** | {b_f1:.4f} | {c_f1:.4f} | {delta_f1:+.4f} | {'📈 Improved' if delta_f1 > 0 else '📉 Regressed' if delta_f1 < 0 else '➖ Unchanged'} |",
        f"| **Mean Latency** | {b_dur:.2f}s | {c_dur:.2f}s | {delta_dur:+.2f}s | {'⚡ Faster' if delta_dur < 0 else '⏳ Slower' if delta_dur > 0 else '➖ Same'} |",
        f"",
        f"## Case-Level Deltas",
        f"",
    ]

    # Map candidate cases by case_id
    cand_cases = {c["case_id"]: c for c in cand.get("cases", [])}
    regressions = []
    improvements = []

    for b_case in base.get("cases", []):
        cid = b_case["case_id"]
        if cid in cand_cases:
            c_case = cand_cases[cid]
            b_case_f1 = b_case.get("f1_score", 0.0)
            c_case_f1 = c_case.get("f1_score", 0.0)
            if c_case_f1 > b_case_f1:
                improvements.append((cid, b_case_f1, c_case_f1))
            elif c_case_f1 < b_case_f1:
                regressions.append((cid, b_case_f1, c_case_f1))

    if improvements:
        lines.append(f"### 🎉 Improvements ({len(improvements)} cases)")
        for cid, bf, cf in improvements:
            lines.append(f"- **`{cid}`**: F1 improved from `{bf:.2f}` to `{cf:.2f}` (+{cf-bf:.2f})")
        lines.append("")

    if regressions:
        lines.append(f"### ⚠️ Regressions ({len(regressions)} cases)")
        for cid, bf, cf in regressions:
            lines.append(f"- **`{cid}`**: F1 dropped from `{bf:.2f}` to `{cf:.2f}` ({cf-bf:.2f})")
        lines.append("")

    if not improvements and not regressions:
        lines.append("No case-level score changes observed between the two benchmark runs.")

    return "\n".join(lines)
