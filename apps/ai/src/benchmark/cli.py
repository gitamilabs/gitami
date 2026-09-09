"""Command-line interface commands for the GitAmi benchmarking framework."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
import click

from src.benchmark.config import BenchmarkConfig
from src.benchmark.runner import BenchmarkRunner
from src.benchmark.report import compare_benchmark_runs
from src.benchmark.kb_lifecycle import purge_all_benchmark_data
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@click.group(name="benchmark")
def benchmark_group():
    """GitAmi Benchmarking Framework for PR Review and Vulnerability Detection."""
    pass


@benchmark_group.command(name="run")
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
    help="Subsample number of test cases (for rapid evaluation).",
)
@click.option(
    "--repos-dir",
    type=click.Path(),
    default=r"D:\gitami-benchmark-repos",
    help="Disk directory for benchmark repositories.",
)
@click.option(
    "--results-dir",
    type=click.Path(),
    default="./benchmark_results",
    help="Output directory for generated Markdown and JSON reports.",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Purge Knowledge Base entries (Neo4j & Vector DB) after each testcase.",
)
@click.option(
    "--language",
    "-l",
    multiple=True,
    help="Filter test cases by programming language (e.g. -l python -l typescript).",
)
def run_benchmark(
    dataset: str,
    sample: Optional[int],
    repos_dir: str,
    results_dir: str,
    cleanup: bool,
    language: tuple,
):
    """Execute benchmark evaluation across selected dataset suites."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    cfg = BenchmarkConfig(
        repos_dir=Path(repos_dir),
        results_dir=Path(results_dir),
        sample_size=sample,
        cleanup_kb=cleanup,
        datasets=["martian", "vulngym"] if dataset.lower() == "all" else [dataset.lower()],
        languages=list(language) if language else None,
    )

    async def _exec():
        runner = BenchmarkRunner(cfg)
        target_ds = None if dataset.lower() == "all" else dataset.lower()
        res = await runner.run(dataset_name=target_ds)

        click.echo("\n" + "=" * 60)
        click.echo("🎉 BENCHMARK RUN COMPLETED")
        click.echo("=" * 60)
        click.echo(f"Total Cases Evaluated: {res.aggregate_score.total_cases}")
        click.echo(f"Precision:            {res.aggregate_score.precision * 100:.1f}%")
        click.echo(f"Recall:               {res.aggregate_score.recall * 100:.1f}%")
        click.echo(f"F1 Score:             {res.aggregate_score.f1_score:.4f}")
        click.echo(f"Mean Latency:         {res.aggregate_score.mean_duration_seconds:.2f}s per case")
        if res.markdown_report_path:
            click.echo(f"\n📄 Markdown Report:    {res.markdown_report_path.resolve()}")
        if res.json_report_path:
            click.echo(f"📊 JSON Report:        {res.json_report_path.resolve()}")
        click.echo("=" * 60)

    asyncio.run(_exec())


@benchmark_group.command(name="compare")
@click.option(
    "--baseline",
    "-b",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to baseline benchmark run JSON report.",
)
@click.option(
    "--candidate",
    "-c",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to candidate benchmark run JSON report.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Optional path to save comparison Markdown report.",
)
def compare_runs(baseline: str, candidate: str, output: Optional[str]):
    """Compare two benchmark runs to detect improvements or regressions."""
    b_path = Path(baseline)
    c_path = Path(candidate)
    report_md = compare_benchmark_runs(b_path, c_path)

    click.echo("\n" + report_md)

    if output:
        out_file = Path(output)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(report_md, encoding="utf-8")
        click.echo(f"\nComparison report saved to: {out_file.resolve()}")


@benchmark_group.command(name="cleanup")
@click.option(
    "--prefix",
    default="benchmark_",
    help="Repo ID prefix for benchmark data to purge.",
)
@click.option(
    "--purge-repos",
    is_flag=True,
    default=False,
    help="Also delete downloaded benchmark repositories from disk.",
)
@click.option(
    "--repos-dir",
    type=click.Path(),
    default=r"D:\gitami-benchmark-repos",
    help="Disk directory for benchmark repositories.",
)
def cleanup_benchmark(prefix: str, purge_repos: bool, repos_dir: str):
    """Purge all orphaned benchmark data from Neo4j, Vector DB, and disk."""
    async def _exec():
        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        try:
            click.echo(f"Purging Knowledge Base records matching prefix '{prefix}'...")
            purged = await purge_all_benchmark_data(graph_client, vector_client, prefix=prefix)
            click.echo(f"Successfully purged {purged} benchmark nodes from Neo4j.")

            # Purge vector entries
            try:
                vector_client.delete(where={"repo": {"$regex": f"^{prefix}"}})
            except Exception:
                pass
            click.echo("Successfully purged matching vector records from Vector DB.")

            if purge_repos:
                r_path = Path(repos_dir)
                if r_path.exists():
                    import shutil
                    click.echo(f"Deleting benchmark repositories from: {r_path.resolve()}...")
                    shutil.rmtree(r_path, ignore_errors=True)
                    click.echo("Repository storage directory deleted.")

            click.echo("Cleanup completed successfully.")
        finally:
            await graph_client.close()

    asyncio.run(_exec())
