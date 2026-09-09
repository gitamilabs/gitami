"""Base interfaces and data structures for benchmark datasets."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.benchmark.config import BenchmarkConfig


@dataclass
class GroundTruthIssue:
    """A verified issue or vulnerability known to exist in the test case."""

    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    severity: str = "warning"  # "error", "warning", "info"
    category: str = "bug"  # "security", "bug", "performance", "convention", "blast_radius"
    title: str = ""
    description: str = ""
    vuln_id: Optional[str] = None
    cwe_id: Optional[str] = None
    suggested_fix: Optional[str] = None

    def line_in_range(self, line: int, tolerance: int = 15) -> bool:
        """Check if a target line number falls within or near this issue's location."""
        if self.line_start is None:
            return True
        start = max(1, self.line_start - tolerance)
        end = (self.line_end if self.line_end is not None else self.line_start) + tolerance
        return start <= line <= end


@dataclass
class BenchmarkTestCase:
    """A standardized unit of benchmarking evaluation."""

    case_id: str
    dataset_name: str
    repo_name: str
    repo_url: str
    commit_or_ref: str
    base_ref: Optional[str] = None
    diff_text: str = ""
    language: str = "unknown"
    ground_truth_issues: List[GroundTruthIssue] = field(default_factory=list)
    local_repo_dir: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BenchmarkDataset(ABC):
    """Abstract base class for benchmark dataset adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifier of the benchmark dataset."""
        ...

    @abstractmethod
    def prepare(self, config: BenchmarkConfig) -> None:
        """Acquire, clone, or update the dataset repository and underlying data files."""
        ...

    @abstractmethod
    def load_cases(self, config: BenchmarkConfig) -> List[BenchmarkTestCase]:
        """Load and yield standardized benchmark test cases ready for evaluation."""
        ...
