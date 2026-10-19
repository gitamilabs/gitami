"""Competitor and ablation benchmark subsystem for GitAmi research evaluation."""

from ai_service.benchmark.competitors.config import (
    CompetitorConfig,
    COMPETITOR_PRESETS,
    get_competitor_config,
)
from ai_service.benchmark.competitors.runner import CompetitorBenchmarkRunner
from ai_service.benchmark.competitors.matrix import CompetitorMatrixGenerator
from ai_service.benchmark.competitors.key_rotator import APIKeyRotator

__all__ = [
    "CompetitorConfig",
    "COMPETITOR_PRESETS",
    "get_competitor_config",
    "CompetitorBenchmarkRunner",
    "CompetitorMatrixGenerator",
    "APIKeyRotator",
]
