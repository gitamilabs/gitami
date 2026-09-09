from __future__ import annotations

import logging
from typing import Optional

from src.context.contracts import ContextItem, ContextSource

logger = logging.getLogger(__name__)


def validate_provenance(item: ContextItem) -> bool:
    """
    Validates that a ContextItem has authentic, non-empty provenance.
    Ensures repository_id and kind are always present, and no fabricated
    placeholders are used.
    """
    source = item.source
    if not source:
        logger.warning(f"Item '{item.id}' has no source provenance")
        return False

    if not source.repository_id or not source.kind:
        logger.warning(f"Item '{item.id}' has invalid source: kind={source.kind}, repo={source.repository_id}")
        return False

    # Check for placeholder strings
    for val in (source.repository_id, source.file_path, source.entity_uid, source.commit_sha):
        if val and any(ph in str(val).lower() for ph in ("placeholder", "todo", "unknown_repo", "fabricated")):
            logger.warning(f"Item '{item.id}' contains suspicious provenance placeholder: {val}")
            return False

    return True


def create_source(
    kind: str,
    repository_id: str,
    file_path: Optional[str] = None,
    entity_uid: Optional[str] = None,
    commit_sha: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    issue_number: Optional[int] = None,
    pr_number: Optional[int] = None,
    confidence: float = 1.0,
) -> ContextSource:
    """Factory helper to construct an authentic ContextSource."""
    return ContextSource(
        kind=kind,
        repository_id=repository_id,
        file_path=file_path,
        entity_uid=entity_uid,
        commit_sha=commit_sha,
        start_line=start_line,
        end_line=end_line,
        issue_number=issue_number,
        pr_number=pr_number,
        confidence=confidence,
    )
