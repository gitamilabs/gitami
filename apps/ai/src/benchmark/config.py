"""Configuration for GitAmi Benchmarking Framework."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class BenchmarkConfig:
    """Benchmark execution configuration."""

    # Storage for cloned benchmark repositories (can be deleted independently)
    repos_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BENCHMARK_REPOS_DIR", r"D:\gitami-benchmark-repos")
        )
    )

    # Output directory for Markdown and JSON evaluation reports
    results_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("BENCHMARK_RESULTS_DIR", "./benchmark_results")
        )
    )

    # Subsample test cases (e.g. 3 or 5 for quick testing, None for full suite)
    sample_size: Optional[int] = None

    # Automatically purge Knowledge Base entries (Neo4j & Vector DB) after each testcase/run
    cleanup_kb: bool = True

    # Which benchmark datasets to evaluate ("martian", "vulngym", or both)
    datasets: List[str] = field(default_factory=lambda: ["martian", "vulngym"])

    # Filter by target programming languages (e.g. ["python", "typescript"])
    languages: Optional[List[str]] = None

    # Use shallow git cloning (--depth 1) for speed and disk conservation
    shallow_clone: bool = True

    # Namespace prefix for Knowledge Base isolation to avoid colliding with user repos
    repo_id_prefix: str = "benchmark_"

    # Virtual branch name for evaluation runs
    branch: str = "benchmark_main"

    # Line distance tolerance for matching predicted issues to ground truth
    match_line_tolerance: int = 15

    # Minimum text overlap/similarity threshold for issue matching
    match_text_threshold: float = 0.35

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist on disk."""
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.repos_dir / "diff_cache").mkdir(parents=True, exist_ok=True)
