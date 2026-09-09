"""Benchmark datasets package and registry."""

from typing import Dict, List, Type

from ai_service.benchmark.datasets.base import BenchmarkDataset, BenchmarkTestCase, GroundTruthIssue

_DATASET_REGISTRY: Dict[str, Type[BenchmarkDataset]] = {}


def register_dataset(name: str):
    """Decorator to register a benchmark dataset adapter."""
    def decorator(cls: Type[BenchmarkDataset]):
        _DATASET_REGISTRY[name.lower()] = cls
        return cls
    return decorator


def get_dataset(name: str) -> BenchmarkDataset:
    """Retrieve an initialized dataset adapter instance by name."""
    name_lower = name.lower()
    # Ensure standard adapters are loaded
    if "martian" not in _DATASET_REGISTRY or "vulngym" not in _DATASET_REGISTRY:
        from ai_service.benchmark.datasets.martian_adapter import MartianAdapter
        from ai_service.benchmark.datasets.vulngym_adapter import VulnGymAdapter
        _DATASET_REGISTRY["martian"] = MartianAdapter
        _DATASET_REGISTRY["vulngym"] = VulnGymAdapter

    if name_lower not in _DATASET_REGISTRY:
        available = list(_DATASET_REGISTRY.keys())
        raise ValueError(f"Unknown benchmark dataset: '{name}'. Available datasets: {available}")
    return _DATASET_REGISTRY[name_lower]()


def list_datasets() -> List[str]:
    """List all registered benchmark dataset names."""
    # Ensure standard adapters are loaded
    if "martian" not in _DATASET_REGISTRY or "vulngym" not in _DATASET_REGISTRY:
        from ai_service.benchmark.datasets.martian_adapter import MartianAdapter
        from ai_service.benchmark.datasets.vulngym_adapter import VulnGymAdapter
        _DATASET_REGISTRY["martian"] = MartianAdapter
        _DATASET_REGISTRY["vulngym"] = VulnGymAdapter
    return sorted(list(_DATASET_REGISTRY.keys()))


__all__ = [
    "BenchmarkDataset",
    "BenchmarkTestCase",
    "GroundTruthIssue",
    "register_dataset",
    "get_dataset",
    "list_datasets",
]
