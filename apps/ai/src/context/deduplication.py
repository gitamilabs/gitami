from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple

from src.context.contracts import ContextItem, ContextItemType


def compute_item_identity(item: ContextItem) -> str:
    """
    Computes a stable, provider-aware identity key for a context item.
    Does NOT lump distinct evidence together merely because it references the same file.
    """
    src = item.source
    repo = src.repository_id or "global"

    # 1. Structural and behavioral relationships have distinct edge identities
    if item.type in (
        ContextItemType.CALL_GRAPH,
        ContextItemType.HERITAGE,
        ContextItemType.DEPENDENCY,
        ContextItemType.TEST,
    ):
        return f"rel:{repo}:{item.type.value}:{item.id}"

    # 2. Code entities with an explicit entity UID
    if src.entity_uid:
        return f"entity:{repo}:{src.entity_uid}"


    # 2. GitHub entities with external numbers (issue, PR)
    if item.type == ContextItemType.PULL_REQUEST and src.pr_number is not None:
        return f"github:{repo}:pr:{src.pr_number}"
    if item.type == ContextItemType.ISSUE and src.issue_number is not None:
        return f"github:{repo}:issue:{src.issue_number}"

    # 3. Git commits
    if item.type == ContextItemType.COMMIT:
        commit_id = src.commit_sha or item.id
        return f"git:{repo}:commit:{commit_id}"

    # 4. Source code snippets bounded by line ranges
    if src.file_path and src.start_line is not None and src.end_line is not None:
        return f"source:{repo}:{src.file_path}:{src.start_line}-{src.end_line}"

    # 5. Whole files
    if item.type == ContextItemType.FILE and src.file_path:
        return f"file:{repo}:{src.file_path}"

    # 6. Documentation and semantic search content: content-derived hash
    norm_content = " ".join(item.content.split())
    content_hash = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()[:16]
    if src.file_path:
        return f"semantic:{repo}:{src.file_path}:{content_hash}"
    return f"doc:{repo}:{item.type.value}:{content_hash}"


class ProviderAwareDeduplicator:
    """
    Deduplicates candidates using item-appropriate stable identities,
    safely merging complementary information (e.g. graph relationships + source snippet)
    without dropping distinct evidence.
    """

    def deduplicate(self, items: List[ContextItem]) -> Tuple[List[ContextItem], int]:
        """
        Deduplicates items and returns (deduplicated_items, deduplicated_count).
        """
        seen: Dict[str, ContextItem] = {}
        dedup_count = 0

        for item in items:
            key = compute_item_identity(item)
            if key not in seen:
                seen[key] = item
            else:
                dedup_count += 1
                existing = seen[key]
                # Merge complementary metadata and keep highest relevance score
                if item.relevance_score > existing.relevance_score:
                    existing.relevance_score = item.relevance_score

                # Merge metadata dictionaries
                for k, v in item.metadata.items():
                    if k not in existing.metadata:
                        existing.metadata[k] = v
                    elif isinstance(existing.metadata[k], list) and isinstance(v, list):
                        # Union lists without duplicates
                        for val in v:
                            if val not in existing.metadata[k]:
                                existing.metadata[k].append(val)

                # If existing has shorter content or missing snippet and new has it, enrich
                if len(item.content) > len(existing.content) and item.type == existing.type:
                    existing.content = item.content

        return list(seen.values()), dedup_count
