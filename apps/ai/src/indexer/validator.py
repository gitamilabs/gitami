from typing import List, Optional
from src.indexer.contracts import IndexingStats, ValidationReport


class IndexValidator:
    """Validates repository index completeness before state is marked as READY."""

    def validate(
        self,
        repo_id: str,
        commit_sha: str,
        stats: IndexingStats,
        fatal_errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> ValidationReport:
        fatal = list(fatal_errors or [])
        warns = list(warnings or [])

        # 1. Repository identity checks
        repo_exists = bool(repo_id and repo_id.strip())
        if not repo_exists:
            fatal.append("Repository ID is empty or invalid.")

        # 2. Commit SHA check
        commit_exists = bool(commit_sha and len(commit_sha.strip()) >= 7)
        if not commit_exists:
            fatal.append(f"Target commit SHA '{commit_sha}' is invalid.")

        # 3. File discovery check
        if stats.files_discovered == 0:
            warns.append("Zero indexable source files were discovered in this commit.")

        # 4. Parsing check
        if stats.files_discovered > 0 and stats.files_parsed == 0:
            fatal.append("Source files were discovered but zero files were parsed successfully.")

        # 5. Entity check
        if stats.files_parsed > 0 and stats.entities_created == 0:
            warns.append("No code entities (functions, classes, interfaces) were extracted.")

        # 6. Parse error threshold
        if stats.files_parsed > 0:
            error_ratio = stats.parse_errors / (stats.files_parsed + stats.parse_errors)
            if error_ratio > 0.8:
                fatal.append(f"Excessive parse failures: {stats.parse_errors} files failed out of {stats.files_parsed + stats.parse_errors} ({error_ratio:.1%}).")
            elif stats.parse_errors > 0:
                warns.append(f"{stats.parse_errors} files encountered non-fatal parse errors.")

        is_valid = len(fatal) == 0

        return ValidationReport(
            is_valid=is_valid,
            repository_exists=repo_exists,
            commit_exists=commit_exists,
            files_discovered=stats.files_discovered,
            files_parsed=stats.files_parsed,
            entities_created=stats.entities_created,
            relationships_created=stats.relationships_created,
            fatal_errors=fatal,
            warnings=warns,
        )
