"""GitAmi Benchmarking Framework for PR Review and Vulnerability Detection.

Provides standardized evaluation against industry benchmarks (Martian Code Review Bench
and Tencent VulnGym), testing actual Knowledge Base ingestion (Neo4j + Vector DB)
and agentic review accuracy with automated cleanup and comprehensive metrics.
"""

from ai_service.benchmark.config import BenchmarkConfig
from ai_service.benchmark.runner import BenchmarkRunner, BenchmarkRunResult
from ai_service.benchmark.kb_lifecycle import BenchmarkKBContext
from ai_service.benchmark.datasets.base import BenchmarkTestCase, GroundTruthIssue, BenchmarkDataset

__all__ = [
    "BenchmarkConfig",
    "BenchmarkRunner",
    "BenchmarkRunResult",
    "BenchmarkKBContext",
    "BenchmarkTestCase",
    "GroundTruthIssue",
    "BenchmarkDataset",
]
