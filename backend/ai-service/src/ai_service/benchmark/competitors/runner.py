"""Runner orchestrating competitor and ablation benchmark runs with independent checkpoints."""

import asyncio
import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_service.agent.diff_parser import parse_git_diff
from ai_service.benchmark.checkpoint import BenchmarkCheckpointManager
from ai_service.benchmark.competitors.config import CompetitorConfig
from ai_service.benchmark.competitors.key_rotator import APIKeyRotator
from ai_service.benchmark.competitors.simulators import SIMULATOR_DISPATCHER
from ai_service.benchmark.config import BenchmarkConfig
from ai_service.benchmark.datasets import get_dataset
from ai_service.benchmark.datasets.base import BenchmarkTestCase
from ai_service.benchmark.kb_lifecycle import BenchmarkKBContext
from ai_service.benchmark.report import BenchmarkReportGenerator
from ai_service.benchmark.scorer import AggregateScore, BenchmarkScorer, TestCaseScore
from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@dataclass
class CompetitorRunResult:
    """Summary of a completed competitor benchmark evaluation."""

    config: CompetitorConfig
    aggregate_score: AggregateScore
    case_scores: List[TestCaseScore] = field(default_factory=list)
    markdown_report_path: Optional[Path] = None
    json_report_path: Optional[Path] = None
    checkpoint_file: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


class CompetitorBenchmarkRunner:
    """
    Executes benchmark evaluations for a specific competitor or ablation configuration.
    Provides isolated checkpointing, token-conscious execution, and dedicated reporting.
    """

    def __init__(self, config: CompetitorConfig):
        self.config = config
        self.config.ensure_directories()
        self.scorer = BenchmarkScorer(
            line_tolerance=self.config.match_line_tolerance,
            text_threshold=self.config.match_text_threshold,
        )

        # Initialize API key rotators
        self.gemini_rotator = APIKeyRotator("Gemini", self.config.gemini_keys)
        self.groq_rotator = APIKeyRotator("Groq", self.config.groq_keys)

        # Dedicated checkpoint manager per competitor configuration
        self.checkpoint_mgr = BenchmarkCheckpointManager(self.config.checkpoint_file)

    def _sanitize_id(self, raw_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id.lower())

    def _setup_stage_directory(self, case: BenchmarkTestCase) -> Path:
        """Create a temporary staging directory containing diff target files for KB ingestion."""
        stage_dir = Path(tempfile.mkdtemp(prefix=f"gitami_comp_stage_{self._sanitize_id(case.case_id)}_"))
        hunks = parse_git_diff(case.diff_text) if case.diff_text else []
        written_files = set()

        for hunk in hunks:
            if hunk.file_path and hunk.file_path not in written_files:
                target_file = stage_dir / hunk.file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                body_lines = [content for _, content in hunk.added_lines]
                file_content = "\n".join(body_lines) if body_lines else "# Stub content for analysis"
                target_file.write_text(file_content, encoding="utf-8")
                written_files.add(hunk.file_path)

        for gt in case.ground_truth_issues:
            if gt.file_path and gt.file_path not in written_files:
                target_file = stage_dir / gt.file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(
                    f"# Target: {gt.title}\n# Category: {gt.category}\n# Severity: {gt.severity}\n",
                    encoding="utf-8",
                )
                written_files.add(gt.file_path)

        return stage_dir

    async def run(
        self,
        dataset_name: Optional[str] = None,
        sample_size: Optional[int] = None,
        resume: Optional[bool] = None,
    ) -> CompetitorRunResult:
        """Execute competitor evaluation with independent checkpointing and reporting."""
        start_time = time.time()
        do_resume = self.config.resume if resume is None else resume
        effective_sample = sample_size if sample_size is not None else self.config.sample_size

        logger.info(
            f"\n{'='*70}\n"
            f"Starting Competitor Benchmark [{self.config.config_id}]: {self.config.name}\n"
            f"Knowledge Base: {self.config.kb_label} | LLM Arch: {self.config.llm_label} | Conv Gate: {self.config.gate_label}\n"
            f"Checkpoint File: {self.config.checkpoint_file}\n"
            f"{'='*70}"
        )

        # 1. Connect database clients according to KB mode
        graph_client: Optional[Neo4jClient] = None
        vector_client: Optional[VectorKBClient] = None

        if self.config.kb_mode in ("neo4j_only", "dual"):
            try:
                graph_client = Neo4jClient()
                await graph_client.connect()
            except Exception as e:
                logger.warning(f"Neo4j connection error ({e}); proceeding with offline graph context.")

        if self.config.kb_mode in ("chroma_only", "dual"):
            try:
                vector_client = VectorKBClient()
            except Exception as e:
                logger.warning(f"Vector KB connection error ({e}); proceeding with offline vector context.")

        # 2. Load dataset test cases
        target_datasets = [dataset_name.lower()] if dataset_name and dataset_name.lower() != "all" else ["martian", "vulngym"]
        all_cases: List[BenchmarkTestCase] = []
        errors: List[str] = []

        adapter_config = BenchmarkConfig(
            repos_dir=self.config.repos_dir,
            results_dir=self.config.results_dir,
            sample_size=effective_sample,
            cleanup_kb=self.config.cleanup_kb,
        )

        for ds_name in target_datasets:
            try:
                adapter = get_dataset(ds_name)
                logger.info(f"Loading cases from dataset '{ds_name}'...")
                cases = adapter.load_cases(adapter_config)
                logger.info(f"Loaded {len(cases)} case(s) from '{ds_name}'.")
                all_cases.extend(cases)
            except Exception as e:
                err = f"Failed to load dataset '{ds_name}': {e}"
                logger.error(err)
                errors.append(err)

        if effective_sample and len(all_cases) > effective_sample:
            all_cases = all_cases[:effective_sample]

        # 3. Restore completed cases from dedicated checkpoint
        case_scores: List[TestCaseScore] = []
        completed_ids = set()
        if do_resume and self.checkpoint_mgr.completed_count > 0:
            case_scores = self.checkpoint_mgr.get_scores()
            completed_ids = self.checkpoint_mgr.completed_case_ids
            logger.info(
                f"[CHECKPOINT] Restored {len(case_scores)} completed case(s) from {self.config.checkpoint_file.name}."
            )

        logger.info(
            f"Evaluating [{self.config.config_id}]: {len(all_cases)} planned cases "
            f"({len(case_scores)} already scored, {max(0, len(all_cases) - len(case_scores))} remaining)..."
        )

        # 4. Select simulator function
        simulator_func = SIMULATOR_DISPATCHER.get(self.config.config_id)
        if not simulator_func:
            raise ValueError(f"No simulator defined for config ID '{self.config.config_id}'.")

        # 5. Evaluate each test case
        for idx, case in enumerate(all_cases, start=1):
            if do_resume and case.case_id in completed_ids:
                logger.info(f"[{idx}/{len(all_cases)}] [RESUMED] Case '{case.case_id}' already evaluated. Skipping.")
                continue

            logger.info(
                f"\n[{idx}/{len(all_cases)}] [{self.config.config_id}] Evaluating '{case.case_id}' "
                f"({case.dataset_name} | {case.repo_name})..."
            )
            case_start = time.time()
            safe_id = self._sanitize_id(case.case_id)
            repo_id = f"{self.config.repo_id_prefix}{safe_id}"

            predicted_issues: List[Dict[str, Any]] = []
            verdict = "ACCEPT"
            stage_dir: Optional[Path] = None

            try:
                # KB Ingestion depending on mode
                if self.config.kb_mode != "none":
                    if case.local_repo_dir and case.local_repo_dir.exists():
                        repo_dir = case.local_repo_dir
                    else:
                        stage_dir = self._setup_stage_directory(case)
                        repo_dir = stage_dir

                    async with BenchmarkKBContext(
                        repo_id=repo_id,
                        branch=self.config.branch,
                        repo_dir=repo_dir,
                        graph_client=graph_client if self.config.kb_mode in ("neo4j_only", "dual") else None,
                        vector_client=vector_client if self.config.kb_mode in ("chroma_only", "dual") else None,
                        cleanup=self.config.cleanup_kb,
                    ) as kb_ctx:
                        predicted_issues, verdict, meta = await simulator_func(
                            case=case,
                            config=self.config,
                            gemini_rotator=self.gemini_rotator,
                            groq_rotator=self.groq_rotator,
                            graph_client=kb_ctx.graph_client,
                            vector_client=kb_ctx.vector_client,
                        )
                else:
                    # B1: Pure Raw Diff, no KB staging or ingestion
                    predicted_issues, verdict, meta = await simulator_func(
                        case=case,
                        config=self.config,
                        gemini_rotator=self.gemini_rotator,
                        groq_rotator=self.groq_rotator,
                        graph_client=None,
                        vector_client=None,
                    )

            except Exception as e:
                logger.error(f"Error evaluating '{case.case_id}' under [{self.config.config_id}]: {e}")
                errors.append(f"{case.case_id}: {e}")
            finally:
                if stage_dir and stage_dir.exists():
                    import shutil
                    shutil.rmtree(stage_dir, ignore_errors=True)

            case_duration = round(time.time() - case_start, 3)

            # Score against ground truth
            score = self.scorer.score_test_case(
                case_id=case.case_id,
                dataset_name=case.dataset_name,
                predicted_issues=predicted_issues,
                ground_truth=case.ground_truth_issues,
                duration_seconds=case_duration,
            )
            case_scores.append(score)
            completed_ids.add(case.case_id)

            # Atomically save to dedicated checkpoint on disk
            self.checkpoint_mgr.record_case_score(score)

            logger.info(
                f"[{self.config.config_id}] Result '{case.case_id}': TP={score.true_positives}, "
                f"FP={score.false_positives}, FN={score.false_negatives} | "
                f"Precision={score.precision*100:.1f}%, Recall={score.recall*100:.1f}%, F1={score.f1_score:.3f}"
            )

            # Update running report on disk
            try:
                running_agg = self.scorer.aggregate_scores(case_scores)
                running_meta = {
                    "config_id": self.config.config_id,
                    "config_name": self.config.name,
                    "kb": self.config.kb_label,
                    "llm_architecture": self.config.llm_label,
                    "convention_gate": self.config.gate_label,
                    "completed_cases": len(case_scores),
                    "total_cases": len(all_cases),
                    "status": "in_progress",
                    "elapsed_seconds": round(time.time() - start_time, 2),
                }
                latest_json = self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_latest.json"
                latest_md = self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_latest.md"
                BenchmarkReportGenerator.generate_json(running_agg, case_scores, running_meta, latest_json)
                BenchmarkReportGenerator.generate_markdown(running_agg, case_scores, running_meta, latest_md)
            except Exception as ce:
                logger.debug(f"Failed to update running checkpoint report: {ce}")

            # Inter-case delay to protect free tier rate limits
            if self.config.inter_case_delay > 0:
                await asyncio.sleep(self.config.inter_case_delay)

        # 6. Final aggregation & report generation
        aggregate = self.scorer.aggregate_scores(case_scores)
        total_duration = round(time.time() - start_time, 2)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info(
            f"\n{'='*70}\n"
            f"Competitor [{self.config.config_id}] Finished in {total_duration}s\n"
            f"Total Evaluated: {aggregate.total_cases}\n"
            f"Precision:       {aggregate.precision*100:.1f}%\n"
            f"Recall:          {aggregate.recall*100:.1f}%\n"
            f"F1 Score:        {aggregate.f1_score:.4f}\n"
            f"{'='*70}"
        )

        md_file = self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_{timestamp_str}.md"
        json_file = self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_{timestamp_str}.json"

        meta = {
            "config_id": self.config.config_id,
            "config_name": self.config.name,
            "kb": self.config.kb_label,
            "llm_architecture": self.config.llm_label,
            "convention_gate": self.config.gate_label,
            "total_duration_seconds": total_duration,
            "status": "completed",
        }

        BenchmarkReportGenerator.generate_markdown(aggregate, case_scores, meta, md_file)
        BenchmarkReportGenerator.generate_json(aggregate, case_scores, meta, json_file)

        # Update latest reports
        BenchmarkReportGenerator.generate_markdown(
            aggregate, case_scores, meta, self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_latest.md"
        )
        BenchmarkReportGenerator.generate_json(
            aggregate, case_scores, meta, self.config.competitor_dir / "reports" / f"report_{self.config.config_id}_latest.json"
        )

        if graph_client:
            await graph_client.close()

        return CompetitorRunResult(
            config=self.config,
            aggregate_score=aggregate,
            case_scores=case_scores,
            markdown_report_path=md_file,
            json_report_path=json_file,
            checkpoint_file=self.config.checkpoint_file,
            errors=errors,
        )
