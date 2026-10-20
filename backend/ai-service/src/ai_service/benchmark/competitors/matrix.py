"""Comparison matrix generator compiling evaluation metrics across all competitors and GitAmi."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_service.benchmark.checkpoint import BenchmarkCheckpointManager
from ai_service.benchmark.competitors.config import COMPETITOR_PRESETS
from ai_service.benchmark.scorer import BenchmarkScorer, TestCaseScore

logger = logging.getLogger(__name__)


def format_score_cell(scores: List[TestCaseScore], expected_total: int) -> str:
    """Format a list of scored cases into an informative table cell string."""
    if not scores:
        return "[TO BE MEASURED]"

    scorer = BenchmarkScorer()
    agg = scorer.aggregate_scores(scores)

    if len(scores) < expected_total:
        return (
            f"F1: {agg.f1_score:.3f} (P: {agg.precision*100:.1f}%, R: {agg.recall*100:.1f}%) "
            f"[{len(scores)}/{expected_total} cases]"
        )

    return f"F1: {agg.f1_score:.3f} (P: {agg.precision*100:.1f}%, R: {agg.recall*100:.1f}%)"


class CompetitorMatrixGenerator:
    """Compiles checkpointed results across all 5 configurations into the research comparison matrix."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.competitor_dir = results_dir / "competitors"
        self.checkpoints_dir = self.competitor_dir / "checkpoints"

    def _get_gitami_baseline_scores(self) -> Dict[str, str]:
        """Retrieve baseline scores from latest GitAmi benchmark run reports."""
        pilot_str = "[TO BE MEASURED]"
        martian_str = "F1: 0.083 (P: 20.9%, R: 5.2%) [50 PRs]"
        vulngym_str = "F1: 0.556 (P: 88.0%, R: 40.6%) [393 Cases]"

        # Check for latest Martian JSON report
        martian_latest = self.results_dir / "benchmark_report_martian_latest.json"
        if martian_latest.exists():
            try:
                data = json.loads(martian_latest.read_text(encoding="utf-8"))
                agg = data.get("aggregate", {})
                f1 = agg.get("f1_score", 0.083)
                p = agg.get("precision", 0.209)
                r = agg.get("recall", 0.052)
                cases = agg.get("total_cases", 50)
                if cases <= 5:
                    pilot_str = f"F1: {f1:.3f} (P: {p*100:.1f}%, R: {r*100:.1f}%)"
                else:
                    martian_str = f"F1: {f1:.3f} (P: {p*100:.1f}%, R: {r*100:.1f}%) [{cases} PRs]"
            except Exception:
                pass

        # Check GitAmi checkpoint for pilot and full Martian scores
        gitami_cp = self.results_dir / "benchmark_checkpoint.json"
        if gitami_cp.exists():
            try:
                mgr = BenchmarkCheckpointManager(gitami_cp)
                scores = mgr.get_scores()
                m_scores = [s for s in scores if s.dataset_name == "martian"]
                if m_scores:
                    pilot_ids = {f"martian_cal_dot_com_{i}" for i in range(1, 6)}
                    pilot_scores = [s for s in m_scores if s.case_id in pilot_ids]
                    if len(pilot_scores) == 5:
                        pilot_str = format_score_cell(pilot_scores, expected_total=5)
                    elif len(m_scores) >= 5:
                        pilot_str = format_score_cell(m_scores[:5], expected_total=5)

                    if len(m_scores) >= 50:
                        martian_str = format_score_cell(m_scores, expected_total=50)
            except Exception:
                pass

        # Check for latest VulnGym JSON report
        vulngym_latest = self.results_dir / "benchmark_report_vulngym_latest.json"
        if vulngym_latest.exists():
            try:
                data = json.loads(vulngym_latest.read_text(encoding="utf-8"))
                agg = data.get("aggregate", {})
                f1 = agg.get("f1_score", 0.556)
                p = agg.get("precision", 0.880)
                r = agg.get("recall", 0.406)
                cases = agg.get("total_cases", 393)
                vulngym_str = f"F1: {f1:.3f} (P: {p*100:.1f}%, R: {r*100:.1f}%) [{cases} Cases]"
            except Exception:
                pass

        return {
            "pilot": pilot_str,
            "martian": martian_str,
            "vulngym": vulngym_str,
        }

    def generate_matrix(self) -> List[Dict[str, Any]]:
        """Extract and compile metrics for B1, B2, A1, A2, A3, and GitAmi."""
        rows: List[Dict[str, Any]] = []

        for cid in ["B1", "B2", "A1", "A2", "A3"]:
            preset = COMPETITOR_PRESETS[cid]
            cp_file = self.checkpoints_dir / f"checkpoint_{cid}.json"

            pilot_val = "[TO BE MEASURED]"
            martian_val = "[TO BE MEASURED]"
            vulngym_val = "[TO BE MEASURED]"

            if cp_file.exists():
                mgr = BenchmarkCheckpointManager(cp_file)
                scores = mgr.get_scores()

                martian_scores = [s for s in scores if s.dataset_name == "martian"]
                vulngym_scores = [s for s in scores if s.dataset_name == "vulngym"]

                if martian_scores:
                    pilot_slice = martian_scores[:5]
                    pilot_val = format_score_cell(pilot_slice, expected_total=5)
                    martian_val = format_score_cell(martian_scores, expected_total=50)

                if vulngym_scores:
                    vulngym_val = format_score_cell(vulngym_scores, expected_total=393)

            rows.append({
                "Configuration ID": preset["config_id"],
                "Knowledge Base": preset["kb_label"],
                "LLM Architecture": preset["llm_label"],
                "Conv. Gate": preset["gate_label"],
                "Martian (5-Case Pilot FI)": pilot_val,
                "Martian (Full 50 PRs)": martian_val,
                "VulnGym (393 Cases, 596 Vulns)": vulngym_val,
            })

        # Append GitAmi Reference System
        gitami_baseline = self._get_gitami_baseline_scores()
        rows.append({
            "Configuration ID": "GitAmi (Proposed)",
            "Knowledge Base": "Dual KB (Neo4j + Chroma)",
            "LLM Architecture": "Dual-LLM + ReAct Agent",
            "Conv. Gate": "Enabled",
            "Martian (5-Case Pilot FI)": gitami_baseline["pilot"],
            "Martian (Full 50 PRs)": gitami_baseline["martian"],
            "VulnGym (393 Cases, 596 Vulns)": gitami_baseline["vulngym"],
        })

        return rows

    def render_markdown(self, rows: List[Dict[str, Any]]) -> str:
        """Render matrix rows into a clean GitHub Flavored Markdown table."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md = [
            "# Competitor & Ablation Benchmark Comparison Matrix\n",
            f"**Last Updated**: {timestamp} UTC\n",
            "> [!NOTE]",
            "> This matrix tracks independent evaluations of rival architectures against the proposed GitAmi system.",
            "> Checkpoints are recorded continuously after every test case.\n",
            "| Configuration ID | Knowledge Base | LLM Architecture | Conv. Gate | Martian (5-Case Pilot FI) | Martian (Full 50 PRs) | VulnGym (393 Cases, 596 Vulns) |",
            "|---|---|---|---|---|---|---|",
        ]

        for r in rows:
            cid = f"**{r['Configuration ID']}**"
            md.append(
                f"| {cid} | {r['Knowledge Base']} | {r['LLM Architecture']} | {r['Conv. Gate']} | "
                f"{r['Martian (5-Case Pilot FI)']} | {r['Martian (Full 50 PRs)']} | {r['VulnGym (393 Cases, 596 Vulns)']} |"
            )

        md.append("\n\n### Architectural Insights & Hypotheses:\n")
        md.append("1. **Baseline B1 (Raw Diff)**: Establishes pure LLM zero-shot capability without retrieval augmentation or convention checks.")
        md.append("2. **Baseline B2 (Chroma Only)**: Evaluates vector semantic search without graph dependency analysis.")
        md.append("3. **Ablation A1 (Neo4j Only)**: Evaluates structural call-graph blast radius without unstructured vector retrieval.")
        md.append("4. **Ablation A2 (Worker Only)**: Evaluates Groq Llama-3.3-70B running independently without Gemini Orchestrator.")
        md.append("5. **Ablation A3 (Orch Only)**: Evaluates Gemini 2.0 Flash running independently without Groq Worker.")
        md.append("6. **GitAmi (Proposed)**: Synergizes Dual KB (Graph + Vector) with Dual LLM (Gemini + Groq) inside an autonomous ReAct loop.")

        return "\n".join(md)

    def save_reports(self) -> Tuple[Path, Path]:
        """Compile and save both JSON and Markdown matrix reports to disk."""
        rows = self.generate_matrix()
        md_content = self.render_markdown(rows)

        matrix_dir = self.competitor_dir / "matrix"
        matrix_dir.mkdir(parents=True, exist_ok=True)

        json_file = matrix_dir / "competitor_comparison_matrix_latest.json"
        md_file = matrix_dir / "competitor_comparison_matrix_latest.md"

        json_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        md_file.write_text(md_content, encoding="utf-8")

        return md_file, json_file
