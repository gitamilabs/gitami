"""Persistent checkpoint manager for fault-tolerant benchmark runs and resumption."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ai_service.benchmark.scorer import TestCaseScore, IssueMatch
from ai_service.benchmark.datasets.base import GroundTruthIssue

logger = logging.getLogger(__name__)


class BenchmarkCheckpointManager:
    """Manages disk-backed checkpointing for benchmark runs to enable pausing and resuming."""

    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        self._completed_case_ids: Set[str] = set()
        self._scores: List[TestCaseScore] = []
        self._load()

    @property
    def completed_count(self) -> int:
        return len(self._completed_case_ids)

    @property
    def completed_case_ids(self) -> Set[str]:
        return set(self._completed_case_ids)

    def is_completed(self, case_id: str) -> bool:
        return case_id in self._completed_case_ids

    def get_scores(self) -> List[TestCaseScore]:
        return list(self._scores)

    def record_case_score(self, score: TestCaseScore) -> None:
        """Atomically record a newly scored test case to disk."""
        if score.case_id in self._completed_case_ids:
            # Replace existing score if present
            self._scores = [s for s in self._scores if s.case_id != score.case_id]

        self._completed_case_ids.add(score.case_id)
        self._scores.append(score)
        self._save()

    def clear(self) -> None:
        """Clear all checkpoint data from disk."""
        self._completed_case_ids.clear()
        self._scores.clear()
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info(f"Cleared benchmark checkpoint at {self.checkpoint_file}")
            except Exception as e:
                logger.warning(f"Could not remove checkpoint file {self.checkpoint_file}: {e}")

    def _save(self) -> None:
        """Atomically write checkpoint to disk via temporary file."""
        data = {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "completed_case_ids": list(self._completed_case_ids),
            "scores": [self._serialize_score(s) for s in self._scores],
        }

        tmp_path = self.checkpoint_file.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_path.replace(self.checkpoint_file)
        except Exception as e:
            logger.error(f"Failed writing benchmark checkpoint to {self.checkpoint_file}: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _load(self) -> None:
        """Load existing checkpoint state from disk if available."""
        if not self.checkpoint_file.exists():
            return

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_ids = data.get("completed_case_ids", [])
            self._completed_case_ids = set(raw_ids)

            raw_scores = data.get("scores", [])
            self._scores = [self._deserialize_score(rs) for rs in raw_scores]
            logger.info(
                f"[CHECKPOINT] Loaded existing checkpoint from {self.checkpoint_file.name} "
                f"({len(self._completed_case_ids)} completed case(s))."
            )
        except Exception as e:
            logger.warning(f"Could not parse checkpoint file {self.checkpoint_file}: {e}")
            self._completed_case_ids = set()
            self._scores = []

    def _serialize_score(self, s: TestCaseScore) -> Dict[str, Any]:
        """Convert TestCaseScore into JSON-serializable dictionary."""
        matched = []
        for m in s.matched_pairs:
            matched.append({
                "predicted": m.predicted,
                "gt_title": m.ground_truth.title,
                "gt_file": m.ground_truth.file_path,
                "gt_line_start": m.ground_truth.line_start,
                "gt_line_end": m.ground_truth.line_end,
                "gt_severity": m.ground_truth.severity,
                "gt_category": m.ground_truth.category,
                "gt_desc": m.ground_truth.description,
                "match_score": m.match_score,
                "file_matched": m.file_matched,
                "line_distance": m.line_distance,
            })

        unmatched_gt = []
        for gt in s.unmatched_ground_truth:
            unmatched_gt.append({
                "title": gt.title,
                "file_path": gt.file_path,
                "line_start": gt.line_start,
                "line_end": gt.line_end,
                "severity": gt.severity,
                "category": gt.category,
                "description": gt.description,
            })

        return {
            "case_id": s.case_id,
            "dataset_name": s.dataset_name,
            "true_positives": s.true_positives,
            "false_positives": s.false_positives,
            "false_negatives": s.false_negatives,
            "precision": s.precision,
            "recall": s.recall,
            "f1_score": s.f1_score,
            "duration_seconds": s.duration_seconds,
            "matched_pairs": matched,
            "unmatched_predictions": s.unmatched_predictions,
            "unmatched_ground_truth": unmatched_gt,
            "category_scores": s.category_scores,
        }

    def _deserialize_score(self, d: Dict[str, Any]) -> TestCaseScore:
        """Reconstruct TestCaseScore from dictionary."""
        matched_pairs = []
        for m in d.get("matched_pairs", []):
            gt = GroundTruthIssue(
                file_path=m.get("gt_file", ""),
                line_start=m.get("gt_line_start"),
                line_end=m.get("gt_line_end"),
                severity=m.get("gt_severity", "warning"),
                category=m.get("gt_category", "bug"),
                title=m.get("gt_title", ""),
                description=m.get("gt_desc", ""),
            )
            matched_pairs.append(
                IssueMatch(
                    predicted=m.get("predicted", {}),
                    ground_truth=gt,
                    match_score=float(m.get("match_score", 0.0)),
                    file_matched=bool(m.get("file_matched", False)),
                    line_distance=m.get("line_distance"),
                )
            )

        unmatched_gt = []
        for gt_dict in d.get("unmatched_ground_truth", []):
            unmatched_gt.append(
                GroundTruthIssue(
                    file_path=gt_dict.get("file_path", ""),
                    line_start=gt_dict.get("line_start"),
                    line_end=gt_dict.get("line_end"),
                    severity=gt_dict.get("severity", "warning"),
                    category=gt_dict.get("category", "bug"),
                    title=gt_dict.get("title", ""),
                    description=gt_dict.get("description", ""),
                )
            )

        return TestCaseScore(
            case_id=d.get("case_id", ""),
            dataset_name=d.get("dataset_name", ""),
            true_positives=int(d.get("true_positives", 0)),
            false_positives=int(d.get("false_positives", 0)),
            false_negatives=int(d.get("false_negatives", 0)),
            precision=float(d.get("precision", 0.0)),
            recall=float(d.get("recall", 0.0)),
            f1_score=float(d.get("f1_score", 0.0)),
            matched_pairs=matched_pairs,
            unmatched_predictions=d.get("unmatched_predictions", []),
            unmatched_ground_truth=unmatched_gt,
            duration_seconds=float(d.get("duration_seconds", 0.0)),
            category_scores=d.get("category_scores", {}),
        )
