"""Tencent VulnGym benchmark adapter for vulnerability detection evaluation."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from git import Repo

from src.benchmark.config import BenchmarkConfig
from src.benchmark.datasets.base import BenchmarkDataset, BenchmarkTestCase, GroundTruthIssue

logger = logging.getLogger(__name__)

# Primary language heuristics for VulnGym projects
PROJECT_LANGUAGE_MAP = {
    "fastmcp": "python",
    "litellm": "python",
    "mlflow": "python",
    "langflow": "python",
    "autogpt": "python",
    "apache/airflow": "python",
    "airflow": "python",
    "nltk": "python",
    "google/adk-python": "python",
    "langchain": "python",
    "nemo": "python",
    "open-webui": "python",
    "flowise": "typescript",
    "openclaw": "typescript",
    "typescript-sdk": "typescript",
    "n8n": "typescript",
    "paperclip": "typescript",
    "milvus": "go",
    "trivy": "go",
    "ollama": "go",
}


def parse_line_span(line_val: Any) -> Tuple[Optional[int], Optional[int]]:
    """Normalize line representation (int, '348-352', or '97') into (start, end)."""
    if line_val is None:
        return None, None
    if isinstance(line_val, int):
        return line_val, line_val
    line_str = str(line_val).strip()
    if "-" in line_str:
        parts = line_str.split("-")
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return None, None
    try:
        val = int(line_str)
        return val, val
    except ValueError:
        return None, None


class VulnGymAdapter(BenchmarkDataset):
    """Adapter for Tencent VulnGym benchmark dataset."""

    GIT_URL = "https://github.com/Tencent/VulnGym.git"

    @property
    def name(self) -> str:
        return "vulngym"

    def prepare(self, config: BenchmarkConfig) -> None:
        """Clone the VulnGym repository if not present."""
        config.ensure_directories()
        target_dir = config.repos_dir / "VulnGym"
        if not target_dir.exists():
            logger.info(f"Cloning VulnGym benchmark repository to {target_dir}...")
            Repo.clone_from(self.GIT_URL, str(target_dir), depth=1)
            logger.info("VulnGym repository cloned successfully.")
        else:
            logger.info(f"VulnGym repository already present at {target_dir}.")

    def _clone_or_checkout_project(
        self, project_name: str, repo_url: str, commit_sha: str, config: BenchmarkConfig
    ) -> Optional[Path]:
        """Clone project repo to repos_dir/vulngym_projects/{project_name} and checkout commit."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", project_name.lower())
        project_dir = config.repos_dir / "vulngym_projects" / safe_name
        project_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not project_dir.exists():
                logger.info(f"Cloning {repo_url} to {project_dir}...")
                repo = Repo.clone_from(repo_url, str(project_dir), no_checkout=True)
            else:
                repo = Repo(str(project_dir))

            # Fetch and checkout commit
            try:
                repo.git.fetch("origin", commit_sha, depth=1)
            except Exception:
                pass

            repo.git.checkout(commit_sha, force=True)
            repo.close()
            return project_dir
        except Exception as e:
            logger.warning(f"Failed to clone/checkout {repo_url} at {commit_sha}: {e}")
            return None

    def _extract_diff_from_repo(self, repo_dir: Path, commit_sha: str) -> str:
        """Extract diff for vulnerable commit using git show or parent diff."""
        try:
            repo = Repo(str(repo_dir))
            try:
                diff_text = repo.git.diff(f"{commit_sha}~1", commit_sha)
            except Exception:
                diff_text = repo.git.show(commit_sha, format="", stat=False)
            repo.close()
            return diff_text
        except Exception as e:
            logger.warning(f"Could not extract git diff for {commit_sha}: {e}")
            return ""

    def _create_synthetic_diff(self, file_path: str, line_start: Optional[int], code_snippet: str) -> str:
        """Create a unified diff representation when target commit cannot be directly diffed."""
        line = line_start or 1
        lines = code_snippet.strip().splitlines()
        added_lines = "\n".join(f"+{l}" for l in lines) if lines else "+<vulnerable code>"
        count = len(lines) or 1
        return (
            f"diff --git a/{file_path} b/{file_path}\n"
            f"--- a/{file_path}\n"
            f"+++ b/{file_path}\n"
            f"@@ -{line},{count} +{line},{count} @@\n"
            f"{added_lines}\n"
        )

    def load_cases(self, config: BenchmarkConfig) -> List[BenchmarkTestCase]:
        """Load verified VulnGym entries and format as BenchmarkTestCase."""
        self.prepare(config)
        entries_file = config.repos_dir / "VulnGym" / "data" / "entries.jsonl"
        cases: List[BenchmarkTestCase] = []

        if not entries_file.exists():
            logger.error(f"Entries file not found at {entries_file}")
            return cases

        with open(entries_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                # Filter for human-verified entries (verify == 1) for highest quality ground truth
                verify_val = entry.get("verify")
                if str(verify_val) not in ("1", "True", "true"):
                    continue

                project = entry.get("project", "unknown")
                project_slug = project.lower().split("/")[-1]
                language = PROJECT_LANGUAGE_MAP.get(project_slug, "unknown")

                # Filter by language if specified
                if config.languages and language not in config.languages:
                    continue

                entry_id = entry.get("entry_id", "entry_unknown")
                repo_url = entry.get("repo_url", "")
                commit_sha = entry.get("commit", "")
                vuln_title = entry.get("vuln_title", "")
                cat_l1 = entry.get("vuln_category_l1", "Security Vulnerability")
                cat_l2 = entry.get("vuln_category_l2", "")
                vuln_ids = entry.get("vuln_ids", [])
                primary_vuln_id = vuln_ids[0] if vuln_ids else entry.get("report_id")

                crit_op = entry.get("critical_operation") or {}
                crit_file = crit_op.get("file", "")
                crit_code = crit_op.get("code", "")
                crit_desc = crit_op.get("desc", "")
                crit_line_raw = crit_op.get("line")
                line_start, line_end = parse_line_span(crit_line_raw)

                entry_point = entry.get("entry_point") or {}
                ep_file = entry_point.get("file", crit_file)
                ep_code = entry_point.get("code", "")
                ep_desc = entry_point.get("desc", "")
                ep_line_raw = entry_point.get("line")
                ep_line_start, ep_line_end = parse_line_span(ep_line_raw)

                # Build GroundTruthIssues
                gt_issues: List[GroundTruthIssue] = []
                # Critical operation defect
                if crit_file:
                    desc = f"[{cat_l1}] {vuln_title}. {crit_desc}".strip()
                    gt_issues.append(
                        GroundTruthIssue(
                            file_path=crit_file,
                            line_start=line_start,
                            line_end=line_end,
                            severity="error",
                            category="security",
                            title=f"{cat_l1}: {vuln_title}"[:90],
                            description=desc,
                            vuln_id=primary_vuln_id,
                            suggested_fix=f"Sanitize input or enforce access control in {crit_file}",
                        )
                    )

                # Entry point defect if distinct
                if ep_file and ep_file != crit_file:
                    gt_issues.append(
                        GroundTruthIssue(
                            file_path=ep_file,
                            line_start=ep_line_start,
                            line_end=ep_line_end,
                            severity="warning",
                            category="security",
                            title=f"Vulnerability Entry Point: {cat_l1}"[:90],
                            description=f"Entry point for {vuln_title}. {ep_desc}".strip(),
                            vuln_id=primary_vuln_id,
                        )
                    )

                # Generate diff text (synthetic fallback or local clone)
                diff_text = self._create_synthetic_diff(crit_file, line_start, crit_code)

                cases.append(
                    BenchmarkTestCase(
                        case_id=f"vulngym_{entry_id}",
                        dataset_name="vulngym",
                        repo_name=project,
                        repo_url=repo_url,
                        commit_or_ref=commit_sha,
                        diff_text=diff_text,
                        language=language,
                        ground_truth_issues=gt_issues,
                        metadata={
                            "entry_id": entry_id,
                            "report_id": entry.get("report_id"),
                            "vuln_ids": vuln_ids,
                            "category_l1": cat_l1,
                            "category_l2": cat_l2,
                            "critical_operation": crit_op,
                            "entry_point": entry_point,
                            "source_link": entry.get("source_link"),
                        },
                    )
                )

                if config.sample_size and len(cases) >= config.sample_size:
                    return cases

        return cases
