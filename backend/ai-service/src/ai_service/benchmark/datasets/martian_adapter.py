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


def _find_best_hunk_line(comment_text: str, file_hunks: list) -> Optional[int]:
    """Find the most relevant line in a file's hunks for a given comment."""
    line_match = re.search(r"\b(?:line|lines)\s+(\d+)", comment_text, re.IGNORECASE)
    if line_match:
        return int(line_match.group(1))

    for h in file_hunks:
        if h.added_lines:
            return h.added_lines[0][0]
        if h.removed_lines:
            return h.removed_lines[0][0]
    return None


def locate_comment_target(
    comment_text: str,
    hunks: list,
    changed_files: List[str],
) -> tuple[str, Optional[int]]:
    """
    Intelligently associates a Martian benchmark golden comment with the correct file
    and line number within the PR diff hunks.
    """
    if not changed_files:
        return "", None

    # 1. Direct filename check in comment text
    for cf in changed_files:
        fname = os.path.basename(cf)
        base_no_ext = os.path.splitext(fname)[0]
        if fname.lower() in comment_text.lower() or (len(base_no_ext) > 3 and base_no_ext.lower() in comment_text.lower()):
            matching_hunks = [h for h in hunks if h.file_path == cf]
            return cf, _find_best_hunk_line(comment_text, matching_hunks)

    # 2. Extract significant identifier tokens and joined phrases from comment
    backtick_tokens = set(re.findall(r"`([^`]+)`", comment_text))
    code_identifiers = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}(?:\.[a-zA-Z0-9_]+)*\b", comment_text))

    phrases = re.findall(r"\b([A-Za-z]+)\s+([A-Za-z]+)\b", comment_text)
    joined_phrases = {f"{w1}{w2}".lower() for w1, w2 in phrases if len(w1) > 2 and len(w2) > 2}

    STOPWORDS = {
        "the", "this", "that", "with", "from", "should", "have", "would", "could",
        "does", "because", "when", "where", "which", "then", "also", "into", "been",
        "being", "between", "before", "after", "while", "above", "below", "true", "false",
        "error", "warning", "issue", "problem", "function", "method", "class", "file",
        "code", "line", "lines", "return", "returns", "using", "call", "calls", "used",
        "instead", "since", "here", "there", "some", "other", "about", "import", "imports",
        "export", "exports", "async", "await", "catch", "try", "const", "let", "var",
        "calendar", "event", "events", "type", "types", "interface", "name", "names",
        "null", "undefined", "value", "values", "string", "number", "boolean", "array",
        "object", "test", "tests", "adding", "consider", "handle", "handling", "causes",
        "gracefully", "failures", "operations", "callbacks", "uses", "package", "packages",
        "for", "not", "are", "can", "due", "lead", "leads", "only", "all", "any",
        "such", "more", "than", "within", "without", "each", "every", "potential",
        "increase", "unmount", "memory", "leak", "component", "records", "default",
        "during", "now", "occur", "occurs", "path", "paths", "case", "cases", "cause",
        "sensitive", "validation", "fail", "fails", "enters", "user", "users", "two",
        "concurrent", "login", "requests", "written", "back", "mutated", "decrypted",
        "inconsistent", "naming", "handles", "endpoint", "disable", "mentions", "message"
    }
    meaningful_tokens = set()
    for t in code_identifiers | backtick_tokens:
        clean = re.sub(r"[\(\)]", "", t).strip()
        if clean.lower() not in STOPWORDS and len(clean) > 2:
            meaningful_tokens.add(clean)

    # 3. Score each changed file based on distinct token matches in hunk diff lines
    file_distinct_matches: Dict[str, set] = {cf: set() for cf in changed_files}
    file_weighted_score: Dict[str, float] = {cf: 0.0 for cf in changed_files}
    file_best_line: Dict[str, Optional[int]] = {cf: None for cf in changed_files}
    file_best_line_score: Dict[str, float] = {cf: -1.0 for cf in changed_files}

    for hunk in hunks:
        cf = hunk.file_path
        if cf not in file_distinct_matches:
            continue

        all_lines = hunk.added_lines + hunk.removed_lines
        for line_no, content in all_lines:
            content_lower = content.lower()
            curr_line_score = 0.0

            for jp in joined_phrases:
                if jp in content_lower and len(jp) > 6:
                    file_distinct_matches[cf].add(jp)
                    file_weighted_score[cf] += 10.0
                    curr_line_score += 10.0

            for token in meaningful_tokens:
                pattern = r"\b" + re.escape(token) + r"\b"
                if re.search(pattern, content, re.IGNORECASE):
                    file_distinct_matches[cf].add(token.lower())
                    w = 5.0 if (token in backtick_tokens or re.search(r"[A-Z]", token)) else 2.0
                    file_weighted_score[cf] += w
                    curr_line_score += w

            if curr_line_score > file_best_line_score[cf]:
                file_best_line_score[cf] = curr_line_score
                file_best_line[cf] = line_no

    scored_files = sorted(
        changed_files,
        key=lambda cf: (len(file_distinct_matches[cf]), file_weighted_score[cf]),
        reverse=True,
    )
    best_file = scored_files[0]
    if len(file_distinct_matches[best_file]) > 0:
        best_line = file_best_line.get(best_file)
        if best_line is None:
            best_line = _find_best_hunk_line(comment_text, [h for h in hunks if h.file_path == best_file])
        return best_file, best_line

    # 4. Fallback to explicit line if present in comment, else changed_files[0]
    line_match = re.search(r"\b(?:line|lines)\s+(\d+)", comment_text, re.IGNORECASE)
    fallback_line = int(line_match.group(1)) if line_match else None
    if fallback_line is None and hunks:
        for h in hunks:
            if h.file_path == changed_files[0] and h.added_lines:
                fallback_line = h.added_lines[0][0]
                break

    return changed_files[0], fallback_line


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

                # Map comments to GroundTruthIssue using intelligent locator
                gt_issues: List[GroundTruthIssue] = []
                for c in item.get("comments", []):
                    comment_text = c.get("comment", "")
                    raw_sev = str(c.get("severity", "medium")).lower()
                    raw_cat = str(c.get("category", "bug")).lower()

                    sev = SEVERITY_MAP.get(raw_sev, "warning")
                    cat = CATEGORY_MAP.get(raw_cat, "bug")

                    target_file, line_start = locate_comment_target(comment_text, hunks, changed_files)

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
