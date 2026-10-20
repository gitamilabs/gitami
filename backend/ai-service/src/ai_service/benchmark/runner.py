"""Main benchmark execution runner orchestrating dataset loading, KB injection, agent review, and scoring."""

import asyncio
import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_service.benchmark.config import BenchmarkConfig
from ai_service.benchmark.datasets import get_dataset
from ai_service.benchmark.datasets.base import BenchmarkTestCase
from ai_service.benchmark.kb_lifecycle import BenchmarkKBContext
from ai_service.benchmark.report import BenchmarkReportGenerator
from ai_service.benchmark.scorer import AggregateScore, BenchmarkScorer, TestCaseScore
from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.agent.llm_client import DualLLMClient, is_rate_limit_error
from ai_service.agent.reviewer import run_agentic_pr_review
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols
from ai_service.benchmark.checkpoint import BenchmarkCheckpointManager


logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRunResult:
    """Complete summary of a benchmark suite execution."""

    config: BenchmarkConfig
    aggregate_score: AggregateScore
    case_scores: List[TestCaseScore] = field(default_factory=list)
    markdown_report_path: Optional[Path] = None
    json_report_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


class BenchmarkRunner:
    """Executes PR review and vulnerability detection benchmarks against the active AI system."""

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self.config.ensure_directories()
        self.scorer = BenchmarkScorer(
            line_tolerance=self.config.match_line_tolerance,
            text_threshold=self.config.match_text_threshold,
        )

    def _sanitize_id(self, raw_id: str) -> str:
        """Sanitize an identifier for use in Neo4j and file paths."""
        return re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id.lower())

    def _setup_stage_directory(self, case: BenchmarkTestCase) -> Path:
        """Create a staging directory containing the files affected by the testcase for KB ingestion."""
        stage_dir = Path(tempfile.mkdtemp(prefix=f"gitami_stage_{self._sanitize_id(case.case_id)}_"))

        # Write files from ground truth or diff hunks if real repo not provided
        hunks = parse_git_diff(case.diff_text) if case.diff_text else []
        written_files = set()

        for hunk in hunks:
            if hunk.file_path and hunk.file_path not in written_files:
                target_file = stage_dir / hunk.file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                # Populate with added lines or stub code
                body_lines = [content for _, content in hunk.added_lines]
                file_content = "\n".join(body_lines) if body_lines else "# Stub content for analysis"
                target_file.write_text(file_content, encoding="utf-8")
                written_files.add(hunk.file_path)

        for gt in case.ground_truth_issues:
            if gt.file_path and gt.file_path not in written_files:
                target_file = stage_dir / gt.file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(
                    f"# Vulnerability test case target: {gt.title}\n"
                    f"# Category: {gt.category}\n"
                    f"# Severity: {gt.severity}\n",
                    encoding="utf-8",
                )
                written_files.add(gt.file_path)

        return stage_dir

    async def run(self, dataset_name: Optional[str] = None, resume: Optional[bool] = None) -> BenchmarkRunResult:
        """Execute the benchmark run over selected datasets with checkpointing and resume support."""
        start_time = time.time()
        logger.info("Initializing GitAmi Benchmark Runner with ReAct Agent Reviewer...")

        do_resume = self.config.resume if resume is None else resume
        checkpoint_file = self.config.results_dir / "benchmark_checkpoint.json"
        checkpoint_mgr = BenchmarkCheckpointManager(checkpoint_file)

        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        llm_client = DualLLMClient()

        # Enforce execution order: smaller benchmark (martian) first, then vulngym
        target_datasets = [dataset_name] if dataset_name else list(self.config.datasets)
        dataset_order = {"martian": 0, "vulngym": 1}
        target_datasets.sort(key=lambda d: dataset_order.get(d.lower(), 99))

        all_cases: List[BenchmarkTestCase] = []
        errors: List[str] = []

        # 1. Load test cases from dataset adapters
        for ds_name in target_datasets:
            try:
                adapter = get_dataset(ds_name)
                logger.info(f"Loading cases from benchmark dataset '{ds_name}'...")
                cases = adapter.load_cases(self.config)
                logger.info(f"Loaded {len(cases)} case(s) from '{ds_name}'.")
                all_cases.extend(cases)
            except Exception as e:
                err = f"Failed loading dataset '{ds_name}': {e}"
                logger.error(err)
                errors.append(err)

        if self.config.sample_size and len(all_cases) > self.config.sample_size:
            all_cases = all_cases[: self.config.sample_size]

        case_scores: List[TestCaseScore] = []
        if do_resume and checkpoint_mgr.completed_count > 0:
            case_scores = checkpoint_mgr.get_scores()
            logger.info(
                f"[CHECKPOINT] Loaded {len(case_scores)} previously completed case(s) from {checkpoint_file.name}."
            )

        logger.info(
            f"Beginning evaluation: {len(all_cases)} total test cases planned "
            f"({len(case_scores)} already completed, {max(0, len(all_cases) - len(case_scores))} remaining)..."
        )

        completed_ids = checkpoint_mgr.completed_case_ids if do_resume else set()
        rate_limit_paused = False

        # 2. Evaluate each test case
        for idx, case in enumerate(all_cases, start=1):
            if do_resume and case.case_id in completed_ids:
                logger.info(f"[{idx}/{len(all_cases)}] [RESUMED] Case '{case.case_id}' already evaluated. Skipping.")
                continue

            logger.info(
                f"\n[{idx}/{len(all_cases)}] Evaluating case '{case.case_id}' ({case.dataset_name} | {case.repo_name})..."
            )
            case_start = time.time()
            safe_id = self._sanitize_id(case.case_id)
            repo_id = f"{self.config.repo_id_prefix}{safe_id}"

            stage_dir: Optional[Path] = None
            if case.local_repo_dir and case.local_repo_dir.exists():
                repo_dir = case.local_repo_dir
            else:
                stage_dir = self._setup_stage_directory(case)
                repo_dir = stage_dir

            predicted_issues: List[Dict[str, Any]] = []
            case_success = False

            # Retry loop for API rate limits
            for attempt in range(1, 4):
                try:
                    async with BenchmarkKBContext(
                        repo_id=repo_id,
                        branch=self.config.branch,
                        repo_dir=repo_dir,
                        graph_client=graph_client,
                        vector_client=vector_client,
                        cleanup=self.config.cleanup_kb,
                    ) as kb_ctx:
                        hunks = parse_git_diff(case.diff_text)
                        changed_files = list({h.file_path for h in hunks if h.file_path})
                        changed_symbols = extract_changed_symbols(hunks, case.diff_text)

                        # Extract AST symbols from changed files in staged repository
                        symbols = []
                        if repo_dir and Path(repo_dir).exists():
                            try:
                                from ai_service.parsing.parser import CodeParser
                                code_parser = CodeParser()
                                for f_rel in changed_files:
                                    f_full = Path(repo_dir) / f_rel
                                    if f_full.exists() and f_full.is_file():
                                        p_res = code_parser.parse_file(f_full, repo_root=Path(repo_dir))
                                        symbols.extend(p_res.symbols)
                            except Exception as pe:
                                logger.debug(f"AST symbol extraction notice for '{case.case_id}': {pe}")

                        review_result = await run_agentic_pr_review(
                            client=kb_ctx.graph_client,
                            repo_id=repo_id,
                            branch=self.config.branch,
                            changed_symbols=changed_symbols,
                            raw_diff_text=case.diff_text,
                            symbols=symbols,
                            vector_client=kb_ctx.vector_client,
                            llm_client=llm_client,
                        )

                        predicted_issues = review_result.issues
                        logger.info(
                            f"Review complete for '{case.case_id}': verdict={review_result.decision.verdict}, "
                            f"predicted_issues={len(predicted_issues)}"
                        )
                        case_success = True
                        break

                except Exception as e:
                    if is_rate_limit_error(e):
                        backoff = 15 * attempt
                        logger.warning(
                            f"[API RATE LIMIT] Rate limit or quota warning on '{case.case_id}' (attempt {attempt}/3): {e}"
                        )
                        if attempt < 3:
                            logger.info(f"Pausing for {backoff}s before retrying...")
                            await asyncio.sleep(backoff)
                        else:
                            rate_limit_paused = True
                            errors.append(f"{case.case_id}: Rate limit exceeded - {e}")
                            break
                    else:
                        logger.error(f"Error during evaluation of '{case.case_id}': {e}")
                        errors.append(f"{case.case_id}: {e}")
                        break
                finally:
                    if stage_dir and stage_dir.exists():
                        import shutil
                        shutil.rmtree(stage_dir, ignore_errors=True)

            if rate_limit_paused:
                logger.warning(
                    "\n" + "=" * 65 + "\n"
                    "*** API RATE LIMIT / QUOTA EXHAUSTION DETECTED ***\n"
                    f"Execution paused safely. Progress checkpointed ({len(case_scores)} cases completed).\n"
                    "To resume later once limits reset, simply run:\n"
                    f"  python -m ai_service.cli benchmark run --dataset {dataset_name or 'all'} --resume\n"
                    + "=" * 65 + "\n"
                )
                break

            case_duration = round(time.time() - case_start, 3)

            # Score predictions against ground truth
            score = self.scorer.score_test_case(
                case_id=case.case_id,
                dataset_name=case.dataset_name,
                predicted_issues=predicted_issues,
                ground_truth=case.ground_truth_issues,
                duration_seconds=case_duration,
            )
            case_scores.append(score)
            completed_ids.add(case.case_id)

            # Save immediately to disk checkpoint
            checkpoint_mgr.record_case_score(score)

            logger.info(
                f"Result '{case.case_id}': TP={score.true_positives}, FP={score.false_positives}, "
                f"FN={score.false_negatives} | Precision={score.precision*100:.1f}%, "
                f"Recall={score.recall*100:.1f}%, F1={score.f1_score:.3f}"
            )

            # Live checkpoint: continuously update latest running report files on disk after each test case
            try:
                running_agg = self.scorer.aggregate_scores(case_scores)
                running_meta = {
                    "datasets": target_datasets,
                    "sample_size": self.config.sample_size,
                    "completed_cases": len(case_scores),
                    "total_cases": len(all_cases),
                    "status": "in_progress",
                    "cleanup_kb": self.config.cleanup_kb,
                    "repos_dir": str(self.config.repos_dir),
                    "elapsed_seconds": round(time.time() - start_time, 2),
                }
                BenchmarkReportGenerator.generate_json(
                    running_agg,
                    case_scores,
                    running_meta,
                    self.config.results_dir / "benchmark_report_latest.json",
                )
                BenchmarkReportGenerator.generate_markdown(
                    running_agg,
                    case_scores,
                    running_meta,
                    self.config.results_dir / "benchmark_report_latest.md",
                )
            except Exception as ce:
                logger.debug(f"Failed to update running checkpoint: {ce}")

            # Check if current dataset just completed its cases
            current_ds_name = case.dataset_name
            is_last_case_of_dataset = (
                idx == len(all_cases) or all_cases[idx].dataset_name != current_ds_name
            )
            if is_last_case_of_dataset:
                ds_scores = [s for s in case_scores if s.dataset_name == current_ds_name]
                if ds_scores:
                    ds_agg = self.scorer.aggregate_scores(ds_scores)
                    ds_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ds_md = self.config.results_dir / f"benchmark_report_{current_ds_name}_{ds_ts}.md"
                    ds_json = self.config.results_dir / f"benchmark_report_{current_ds_name}_{ds_ts}.json"
                    ds_md_latest = self.config.results_dir / f"benchmark_report_{current_ds_name}_latest.md"
                    ds_json_latest = self.config.results_dir / f"benchmark_report_{current_ds_name}_latest.json"
                    ds_meta = {
                        "dataset": current_ds_name,
                        "completed_cases": len(ds_scores),
                        "status": "completed",
                        "cleanup_kb": self.config.cleanup_kb,
                    }
                    BenchmarkReportGenerator.generate_markdown(ds_agg, ds_scores, ds_meta, ds_md)
                    BenchmarkReportGenerator.generate_json(ds_agg, ds_scores, ds_meta, ds_json)
                    BenchmarkReportGenerator.generate_markdown(ds_agg, ds_scores, ds_meta, ds_md_latest)
                    BenchmarkReportGenerator.generate_json(ds_agg, ds_scores, ds_meta, ds_json_latest)
                    logger.info(
                        f"\n[DEDICATED REPORT] Saved dedicated benchmark report for '{current_ds_name}': "
                        f"{ds_md.name} (Cases: {len(ds_scores)}, F1: {ds_agg.f1_score:.4f})"
                    )

            # Inter-case delay to protect free tier rate limits
            if self.config.inter_case_delay > 0:
                await asyncio.sleep(self.config.inter_case_delay)

        # 3. Aggregate metrics across all test cases
        aggregate = self.scorer.aggregate_scores(case_scores)
        total_duration = round(time.time() - start_time, 2)
        status_label = "paused_due_to_rate_limit" if rate_limit_paused else "completed"

        logger.info(
            f"\n=== Benchmark Run Status: {status_label.upper()} in {total_duration}s ==="
            f"\nTotal Cases Evaluated: {aggregate.total_cases}"
            f"\nPrecision: {aggregate.precision*100:.1f}%"
            f"\nRecall: {aggregate.recall*100:.1f}%"
            f"\nF1 Score: {aggregate.f1_score:.4f}"
        )

        # 4. Generate timestamped and latest final reports (both individual and unified)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "benchmark_report_combined_" if len(target_datasets) > 1 else f"benchmark_report_{target_datasets[0]}_"
        md_file = self.config.results_dir / f"{prefix}{timestamp_str}.md"
        json_file = self.config.results_dir / f"{prefix}{timestamp_str}.json"

        meta = {
            "datasets": target_datasets,
            "sample_size": self.config.sample_size,
            "cleanup_kb": self.config.cleanup_kb,
            "repos_dir": str(self.config.repos_dir),
            "total_duration_seconds": total_duration,
            "status": status_label,
        }

        BenchmarkReportGenerator.generate_markdown(aggregate, case_scores, meta, md_file)
        BenchmarkReportGenerator.generate_json(aggregate, case_scores, meta, json_file)

        # Update latest reports
        BenchmarkReportGenerator.generate_markdown(
            aggregate, case_scores, meta, self.config.results_dir / "benchmark_report_latest.md"
        )
        BenchmarkReportGenerator.generate_json(
            aggregate, case_scores, meta, self.config.results_dir / "benchmark_report_latest.json"
        )

        await graph_client.close()

        return BenchmarkRunResult(
            config=self.config,
            aggregate_score=aggregate,
            case_scores=case_scores,
            markdown_report_path=md_file,
            json_report_path=json_file,
            errors=errors,
        )

