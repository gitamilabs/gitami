"""Martian Code Review Benchmark adapter (offline suite)."""

import hashlib
import json
import logging
import os
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from git import Repo

from ai_service.benchmark.config import BenchmarkConfig
from ai_service.benchmark.datasets.base import BenchmarkDataset, BenchmarkTestCase, GroundTruthIssue
from ai_service.agent.diff_parser import parse_git_diff

logger = logging.getLogger(__name__)

# Repository URLs mapping for Martian benchmarks
REPO_UPSTREAM_MAP = {
    "sentry": "https://github.com/getsentry/sentry.git",
    "cal_dot_com": "https://github.com/calcom/cal.com.git",
    "grafana": "https://github.com/grafana/grafana.git",
    "discourse": "https://github.com/discourse/discourse.git",
    "keycloak": "https://github.com/keycloak/keycloak.git",
}

LANGUAGE_MAP = {
    "sentry": "python",
    "cal_dot_com": "typescript",
    "grafana": "go",
    "discourse": "ruby",
    "keycloak": "java",
}

SEVERITY_MAP = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "info",
}

CATEGORY_MAP = {
    "bug": "bug",
    "security": "security",
    "concurrency": "bug",
    "perf": "performance",
    "data": "bug",
    "api": "bug",
    "style": "convention",
    "doc_defect": "convention",
    "test_gap": "convention",
    "speculative": "convention",
}


class MartianAdapter(BenchmarkDataset):
    """Adapter for Martian Code Review Benchmark dataset."""

    GIT_URL = "https://github.com/withmartian/code-review-benchmark.git"

    @property
    def name(self) -> str:
        return "martian"

    def prepare(self, config: BenchmarkConfig) -> None:
        """Clone the Martian benchmark repository if not already present."""
        config.ensure_directories()
        target_dir = config.repos_dir / "code-review-benchmark"
        if not target_dir.exists():
            logger.info(f"Cloning Martian benchmark repository to {target_dir}...")
            Repo.clone_from(self.GIT_URL, str(target_dir), depth=1)
            logger.info("Martian benchmark repository cloned successfully.")
        else:
            logger.info(f"Martian benchmark repository already present at {target_dir}.")

    def _fetch_or_cache_diff(self, pr_url: str, config: BenchmarkConfig) -> str:
        """Fetch PR diff via GitHub URL or local cache."""
        cache_key = hashlib.sha256(pr_url.encode("utf-8")).hexdigest()[:16]
        cache_file = config.repos_dir / "diff_cache" / f"martian_{cache_key}.diff"

        if cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read cached diff {cache_file}: {e}")

        # Fetch directly from GitHub .diff endpoint
        diff_url = f"{pr_url}.diff"
        try:
            req = urllib.request.Request(
                diff_url,
                headers={"User-Agent": "GitAmi-Benchmark-Runner/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                cache_file.write_text(content, encoding="utf-8")
                return content
        except Exception as e:
            logger.warning(f"Could not fetch diff for {pr_url} ({diff_url}): {e}")
            return ""

    def load_cases(self, config: BenchmarkConfig) -> List[BenchmarkTestCase]:
        """Load Martian benchmark PRs and map golden comments to GroundTruthIssues."""
        self.prepare(config)
        dataset_dir = config.repos_dir / "code-review-benchmark" / "offline" / "golden_comments"
        cases: List[BenchmarkTestCase] = []

        if not dataset_dir.exists():
            logger.error(f"Golden comments directory not found at {dataset_dir}")
            return cases

        # Determine target json files based on language filters
        target_files = list(dataset_dir.glob("*.json"))

        for file_path in target_files:
            repo_key = file_path.stem  # e.g., "sentry", "cal_dot_com"
            language = LANGUAGE_MAP.get(repo_key, "unknown")

            # Check language filter
            if config.languages and language not in config.languages:
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_items = json.load(f)
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                continue

            for idx, item in enumerate(raw_items):
                pr_url = item.get("url") or item.get("original_url")
                if not pr_url:
                    continue

                pr_title = item.get("pr_title", f"PR #{idx+1}")
                case_id = f"martian_{repo_key}_{idx+1}"

                # Fetch diff text
                diff_text = self._fetch_or_cache_diff(pr_url, config)
                hunks = parse_git_diff(diff_text) if diff_text else []
                changed_files = [h.file_path for h in hunks if h.file_path]

                # Map comments to GroundTruthIssue
                gt_issues: List[GroundTruthIssue] = []
                for c in item.get("comments", []):
                    comment_text = c.get("comment", "")
                    raw_sev = str(c.get("severity", "medium")).lower()
                    raw_cat = str(c.get("category", "bug")).lower()

                    sev = SEVERITY_MAP.get(raw_sev, "warning")
                    cat = CATEGORY_MAP.get(raw_cat, "bug")

                    # Extract line number if explicitly mentioned in comment
                    line_match = re.search(r"\b(?:line|lines)\s+(\d+)", comment_text, re.IGNORECASE)
                    line_start = int(line_match.group(1)) if line_match else None

                    # Associate with file: look for exact filename in comment, else default to primary changed file
                    target_file = ""
                    for cf in changed_files:
                        fname = os.path.basename(cf)
                        if fname in comment_text or cf in comment_text:
                            target_file = cf
                            break
                    if not target_file and changed_files:
                        target_file = changed_files[0]

                    # Fallback line number to first hunk line if not found
                    if line_start is None and hunks:
                        for h in hunks:
                            if not target_file or h.file_path == target_file:
                                if h.added_lines:
                                    line_start = h.added_lines[0][0]
                                    break

                    gt_issues.append(
                        GroundTruthIssue(
                            file_path=target_file,
                            line_start=line_start,
                            severity=sev,
                            category=cat,
                            title=comment_text[:80] + ("..." if len(comment_text) > 80 else ""),
                            description=comment_text,
                        )
                    )

                cases.append(
                    BenchmarkTestCase(
                        case_id=case_id,
                        dataset_name="martian",
                        repo_name=repo_key,
                        repo_url=REPO_UPSTREAM_MAP.get(repo_key, pr_url),
                        commit_or_ref=pr_url,
                        diff_text=diff_text,
                        language=language,
                        ground_truth_issues=gt_issues,
                        metadata={
                            "pr_title": pr_title,
                            "pr_url": pr_url,
                            "source_file": file_path.name,
                        },
                    )
                )

                if config.sample_size and len(cases) >= config.sample_size:
                    return cases

        return cases
