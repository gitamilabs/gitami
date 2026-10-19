"""CLI commands for running and analyzing competitor and ablation benchmarks."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import click

from ai_service.benchmark.checkpoint import BenchmarkCheckpointManager
from ai_service.benchmark.competitors.config import (
    COMPETITOR_PRESETS,
    get_competitor_config,
)
from ai_service.benchmark.competitors.matrix import CompetitorMatrixGenerator
from ai_service.benchmark.competitors.runner import CompetitorBenchmarkRunner
from ai_service.benchmark.competitors.key_rotator import parse_keys

logger = logging.getLogger(__name__)


@click.group(name="benchmark-competitors")
def competitor_benchmark_group():
    """GitAmi Competitor & Ablation Benchmark Suite (B1, B2, A1, A2, A3)."""
    pass


@competitor_benchmark_group.command(name="run")
@click.option(
    "--config",
    "-c",
    "config_id",
    type=click.Choice(["B1", "B2", "A1", "A2", "A3", "all"], case_sensitive=False),
    default="B1",
    help="Target competitor/ablation configuration to run (or 'all' for sequential execution).",
)
@click.option(
    "--dataset",
    "-d",
    type=click.Choice(["all", "martian", "vulngym"], case_sensitive=False),
    default="all",
    help="Target benchmark dataset to execute.",
)
@click.option(
    "--sample",
    "-s",
    type=int,
    default=None,
    help="Subsample number of test cases.",
)
@click.option(
    "--pilot",
    is_flag=True,
    default=False,
    help="Shortcut for Martian 5-case pilot run (--dataset martian --sample 5).",
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="Resume from disk checkpoint, skipping already-scored cases.",
)
@click.option(
    "--delay",
    type=float,
    default=1.5,
    help="Inter-case delay in seconds to stay within free-tier API rate limits.",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Purge Knowledge Base entries after each testcase.",
)
@click.option(
    "--results-dir",
    type=click.Path(),
    default="./benchmark_results",
    help="Output directory for reports and checkpoints.",
)
@click.option(
    "--repos-dir",
    type=click.Path(),
    default=r"D:\gitami-benchmark-repos",
    help="Storage directory for benchmark repositories.",
)
@click.option(
    "--gemini-keys",
    type=str,
    default=None,
    help="Optional comma-separated Gemini API keys for round-robin rotation.",
)
@click.option(
    "--groq-keys",
    type=str,
    default=None,
    help="Optional comma-separated Groq API keys for round-robin rotation.",
)
def run_competitors(
    config_id: str,
    dataset: str,
    sample: Optional[int],
    pilot: bool,
    resume: bool,
    delay: float,
    cleanup: bool,
    results_dir: str,
    repos_dir: str,
    gemini_keys: Optional[str],
    groq_keys: Optional[str],
):
    """Execute benchmark evaluation for competitor and ablation configurations."""
    import sys
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    target_dataset = "martian" if pilot else dataset
    effective_sample = 5 if pilot else sample

    target_configs = ["B1", "B2", "A1", "A2", "A3"] if config_id.lower() == "all" else [config_id.upper()]

    parsed_gemini = parse_keys(gemini_keys) if gemini_keys else None
    parsed_groq = parse_keys(groq_keys) if groq_keys else None

    async def _exec():
        for cid in target_configs:
            cfg = get_competitor_config(
                config_id=cid,
                repos_dir=Path(repos_dir),
                results_dir=Path(results_dir),
                sample_size=effective_sample,
                resume=resume,
                inter_case_delay=delay,
                cleanup_kb=cleanup,
                gemini_keys=parsed_gemini,
                groq_keys=parsed_groq,
            )

            runner = CompetitorBenchmarkRunner(cfg)
            res = await runner.run(
                dataset_name=target_dataset,
                sample_size=effective_sample,
                resume=resume,
            )

            click.echo("\n" + "=" * 65)
            click.echo(f"[{cid}] BENCHMARK COMPLETE: {cfg.name}")
            click.echo("=" * 65)
            click.echo(f"Cases Evaluated:  {res.aggregate_score.total_cases}")
            click.echo(f"Precision:        {res.aggregate_score.precision * 100:.1f}%")
            click.echo(f"Recall:           {res.aggregate_score.recall * 100:.1f}%")
            click.echo(f"F1 Score:         {res.aggregate_score.f1_score:.4f}")
            if res.markdown_report_path:
                click.echo(f"Report:           {res.markdown_report_path.resolve()}")
            click.echo(f"Checkpoint:       {res.checkpoint_file.resolve()}")
            click.echo("=" * 65 + "\n")

        # Auto-update comparison matrix
        matrix_gen = CompetitorMatrixGenerator(Path(results_dir))
        md_file, json_file = matrix_gen.save_reports()
        click.echo(f"[MATRIX] Updated comparison matrix: {md_file.resolve()}")

    asyncio.run(_exec())


@competitor_benchmark_group.command(name="matrix")
@click.option(
    "--results-dir",
    type=click.Path(),
    default="./benchmark_results",
    help="Directory containing benchmark checkpoints and reports.",
)
def show_matrix(results_dir: str):
    """Generate and display the competitor comparison matrix."""
    import sys
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    matrix_gen = CompetitorMatrixGenerator(Path(results_dir))
    md_file, json_file = matrix_gen.save_reports()

    content = md_file.read_text(encoding="utf-8")
    click.echo("\n" + content)
    click.echo(f"\nSaved matrix JSON: {json_file.resolve()}")
    click.echo(f"Saved matrix Markdown: {md_file.resolve()}\n")


@competitor_benchmark_group.command(name="status")
@click.option(
    "--results-dir",
    type=click.Path(),
    default="./benchmark_results",
    help="Directory containing benchmark checkpoints and reports.",
)
def show_status(results_dir: str):
    """Show live checkpoint progress across all 5 competitor configurations."""
    import sys
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    r_path = Path(results_dir)
    cp_dir = r_path / "competitors" / "checkpoints"

    click.echo("\n" + "=" * 70)
    click.echo("COMPETITOR BENCHMARK CHECKPOINT STATUS")
    click.echo("=" * 70)

    for cid, preset in COMPETITOR_PRESETS.items():
        cp_file = cp_dir / f"checkpoint_{cid}.json"
        if cp_file.exists():
            mgr = BenchmarkCheckpointManager(cp_file)
            scores = mgr.get_scores()
            martian_count = len([s for s in scores if s.dataset_name == "martian"])
            vulngym_count = len([s for s in scores if s.dataset_name == "vulngym"])
            click.echo(
                f"[{cid}] {preset['name']}\n"
                f"     Checkpoint File: {cp_file.name}\n"
                f"     Completed:       {len(scores)} cases total "
                f"(Martian: {martian_count}/50, VulnGym: {vulngym_count}/393)\n"
            )
        else:
            click.echo(
                f"[{cid}] {preset['name']}\n"
                f"     Checkpoint File: {cp_file.name} (Not started)\n"
            )

    click.echo("=" * 70)
    click.echo("To run a configuration, use:")
    click.echo("  python -m ai_service.cli benchmark-competitors run --config B1 --dataset martian --sample 5")
    click.echo("=" * 70 + "\n")


@competitor_benchmark_group.command(name="clear")
@click.option(
    "--config",
    "-c",
    "config_id",
    type=click.Choice(["B1", "B2", "A1", "A2", "A3", "all"], case_sensitive=False),
    required=True,
    help="Which competitor checkpoint to clear.",
)
@click.option(
    "--results-dir",
    type=click.Path(),
    default="./benchmark_results",
    help="Results directory.",
)
def clear_checkpoint(config_id: str, results_dir: str):
    """Clear checkpoint file for a competitor configuration to start fresh."""
    r_path = Path(results_dir)
    cp_dir = r_path / "competitors" / "checkpoints"

    targets = ["B1", "B2", "A1", "A2", "A3"] if config_id.lower() == "all" else [config_id.upper()]

    for cid in targets:
        cp_file = cp_dir / f"checkpoint_{cid}.json"
        if cp_file.exists():
            cp_file.unlink()
            click.echo(f"Cleared checkpoint for [{cid}]: {cp_file}")
        else:
            click.echo(f"No checkpoint found for [{cid}].")
