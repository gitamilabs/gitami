"""Scoring and evaluation metrics engine for benchmark test runs."""

import re
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.benchmark.datasets.base import GroundTruthIssue


@dataclass
class IssueMatch:
    """Represents a matched predicted issue and ground truth issue."""

    predicted: Dict[str, Any]
    ground_truth: GroundTruthIssue
    match_score: float
    file_matched: bool
    line_distance: Optional[int]


@dataclass
class TestCaseScore:
    """Scoring result for an individual benchmark test case."""

    case_id: str
    dataset_name: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    matched_pairs: List[IssueMatch] = field(default_factory=list)
    unmatched_predictions: List[Dict[str, Any]] = field(default_factory=list)
    unmatched_ground_truth: List[GroundTruthIssue] = field(default_factory=list)
    duration_seconds: float = 0.0
    category_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class AggregateScore:
    """Aggregated evaluation metrics across an entire benchmark suite run."""

    total_cases: int = 0
    total_ground_truth: int = 0
    total_predicted: int = 0
    total_tp: int = 0
    total_fp: int = 0
    total_fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    mean_duration_seconds: float = 0.0
    category_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    severity_detection_rates: Dict[str, float] = field(default_factory=dict)


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric keywords."""
    tokens = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    # Exclude trivial stop words
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "should", "have", "not"}
    return {t for t in tokens if t not in stopwords}


def jaccard_similarity(text1: str, text2: str) -> float:
    """Compute Jaccard token similarity between two text strings."""
    t1 = _tokenize(text1)
    t2 = _tokenize(text2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union > 0 else 0.0


def files_match(file1: str, file2: str) -> bool:
    """Check if two file paths refer to the same file (exact or normalized basename/suffix)."""
    if not file1 or not file2:
        return False
    f1 = file1.replace("\\", "/").strip().lstrip("./")
    f2 = file2.replace("\\", "/").strip().lstrip("./")
    if f1 == f2 or f1.endswith(f2) or f2.endswith(f1):
        return True
    return os.path.basename(f1) == os.path.basename(f2)


class BenchmarkScorer:
    """Evaluates agent review predictions against benchmark ground truth."""

    def __init__(
        self,
        line_tolerance: int = 15,
        text_threshold: float = 0.25,
    ):
        self.line_tolerance = line_tolerance
        self.text_threshold = text_threshold

    def score_test_case(
        self,
        case_id: str,
        dataset_name: str,
        predicted_issues: List[Dict[str, Any]],
        ground_truth: List[GroundTruthIssue],
        duration_seconds: float = 0.0,
    ) -> TestCaseScore:
        """Match predicted issues with ground truth and compute precision, recall, and F1."""
        matched_gt_indices: Set[int] = set()
        matched_pred_indices: Set[int] = set()
        matches: List[IssueMatch] = []

        # Find best bipartite matches between predicted issues and ground truth
        candidates: List[Tuple[float, int, int, bool, Optional[int]]] = []

        for p_idx, pred in enumerate(predicted_issues):
            p_file = str(pred.get("file_path", ""))
            p_line = pred.get("line")
            p_text = f"{pred.get('title', '')} {pred.get('description', '')}"

            for gt_idx, gt in enumerate(ground_truth):
                f_match = files_match(p_file, gt.file_path)

                line_dist: Optional[int] = None
                line_ok = False
                if gt.line_start is not None and p_line is not None:
                    try:
                        p_line_int = int(p_line)
                        line_dist = abs(p_line_int - gt.line_start)
                        line_ok = gt.line_in_range(p_line_int, tolerance=self.line_tolerance)
                    except (ValueError, TypeError):
                        pass
                elif gt.line_start is None:
                    line_ok = True  # File-level defect

                gt_text = f"{gt.title} {gt.description}"
                text_sim = jaccard_similarity(p_text, gt_text)

                # Category compatibility bonus
                cat_bonus = 0.0
                p_cat = str(pred.get("category", "")).lower()
                if p_cat == gt.category:
                    cat_bonus = 0.2

                # Calculate composite match score
                score = 0.0
                if f_match:
                    score += 0.4
                    if line_ok:
                        score += 0.3
                    score += (text_sim * 0.3) + cat_bonus
                else:
                    # Weak cross-file textual match
                    score += text_sim * 0.5 + cat_bonus

                candidates.append((score, p_idx, gt_idx, f_match, line_dist))

        # Sort candidates greedily by match score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        for score, p_idx, gt_idx, f_match, line_dist in candidates:
            if p_idx in matched_pred_indices or gt_idx in matched_gt_indices:
                continue

            # Accept match if score threshold met and file matches (or very strong textual match)
            if (f_match and score >= 0.40) or score >= 0.70:
                matched_pred_indices.add(p_idx)
                matched_gt_indices.add(gt_idx)
                matches.append(
                    IssueMatch(
                        predicted=predicted_issues[p_idx],
                        ground_truth=ground_truth[gt_idx],
                        match_score=round(score, 3),
                        file_matched=f_match,
                        line_distance=line_dist,
                    )
                )

        tp = len(matches)
        fp = len(predicted_issues) - len(matched_pred_indices)
        fn = len(ground_truth) - len(matched_gt_indices)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        unmatched_preds = [
            p for i, p in enumerate(predicted_issues) if i not in matched_pred_indices
        ]
        unmatched_gts = [
            gt for i, gt in enumerate(ground_truth) if i not in matched_gt_indices
        ]

        return TestCaseScore(
            case_id=case_id,
            dataset_name=dataset_name,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            matched_pairs=matches,
            unmatched_predictions=unmatched_preds,
            unmatched_ground_truth=unmatched_gts,
            duration_seconds=duration_seconds,
        )

    def aggregate_scores(self, test_scores: List[TestCaseScore]) -> AggregateScore:
        """Aggregate per-testcase results into overall benchmark metrics."""
        if not test_scores:
            return AggregateScore()

        total_tp = sum(s.true_positives for s in test_scores)
        total_fp = sum(s.false_positives for s in test_scores)
        total_fn = sum(s.false_negatives for s in test_scores)
        total_dur = sum(s.duration_seconds for s in test_scores)

        total_gt = total_tp + total_fn
        total_pred = total_tp + total_fp

        precision = total_tp / total_pred if total_pred > 0 else 0.0
        recall = total_tp / total_gt if total_gt > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        mean_dur = total_dur / len(test_scores) if test_scores else 0.0

        # Category breakdowns
        cat_tp: Dict[str, int] = {}
        cat_total: Dict[str, int] = {}
        for s in test_scores:
            for m in s.matched_pairs:
                cat = m.ground_truth.category
                cat_tp[cat] = cat_tp.get(cat, 0) + 1
            for gt in s.unmatched_ground_truth:
                cat = gt.category
                cat_total[cat] = cat_total.get(cat, 0) + 1
            for m in s.matched_pairs:
                cat = m.ground_truth.category
                cat_total[cat] = cat_total.get(cat, 0) + 1

        cat_breakdown: Dict[str, Dict[str, Any]] = {}
        for cat, total in cat_total.items():
            tp = cat_tp.get(cat, 0)
            cat_recall = tp / total if total > 0 else 0.0
            cat_breakdown[cat] = {
                "detected": tp,
                "total": total,
                "recall": round(cat_recall, 4),
            }

        # Severity detection rates
        sev_tp: Dict[str, int] = {}
        sev_total: Dict[str, int] = {}
        for s in test_scores:
            for m in s.matched_pairs:
                sev = m.ground_truth.severity
                sev_tp[sev] = sev_tp.get(sev, 0) + 1
            for gt in s.unmatched_ground_truth:
                sev = gt.severity
                sev_total[sev] = sev_total.get(sev, 0) + 1
            for m in s.matched_pairs:
                sev = m.ground_truth.severity
                sev_total[sev] = sev_total.get(sev, 0) + 1

        sev_rates: Dict[str, float] = {}
        for sev, total in sev_total.items():
            tp = sev_tp.get(sev, 0)
            sev_rates[sev] = round(tp / total, 4) if total > 0 else 0.0

        return AggregateScore(
            total_cases=len(test_scores),
            total_ground_truth=total_gt,
            total_predicted=total_pred,
            total_tp=total_tp,
            total_fp=total_fp,
            total_fn=total_fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            mean_duration_seconds=round(mean_dur, 2),
            category_breakdown=cat_breakdown,
            severity_detection_rates=sev_rates,
        )
