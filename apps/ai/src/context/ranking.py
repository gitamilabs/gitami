from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from src.context.contracts import ContextItem, ContextItemType


# ── Named Scoring Constants (Configurable, not hardcoded truth) ─────────────

DEFAULT_EXACT_MATCH_SCORE: float = 1.0
DEFAULT_DIRECT_DEFINITION_SCORE: float = 0.9
DEFAULT_DIRECT_RELATIONSHIP_SCORE: float = 0.8
DEFAULT_SEMANTIC_WEIGHT: float = 0.75
DEFAULT_MULTI_HOP_SCORE: float = 0.5
DEFAULT_BACKGROUND_SCORE: float = 0.3


@dataclass
class ScoringConfig:
    """Configurable scoring weights for deterministic ranking."""
    exact_match_score: float = DEFAULT_EXACT_MATCH_SCORE
    direct_definition_score: float = DEFAULT_DIRECT_DEFINITION_SCORE
    direct_relationship_score: float = DEFAULT_DIRECT_RELATIONSHIP_SCORE
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT
    multi_hop_score: float = DEFAULT_MULTI_HOP_SCORE
    background_score: float = DEFAULT_BACKGROUND_SCORE


class DeterministicRanker:
    """
    Ranks context candidates deterministically based on match signals,
    graph distance, semantic relevance, and stable tie-breaking.
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()

    def score_item(self, item: ContextItem, query: str) -> float:
        """Calculate a deterministic relevance score for a context item."""
        q_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        title_lower = item.title.lower()
        content_lower = item.content.lower()

        # Check for exact token/symbol matches in title
        exact_title_match = any(t == title_lower or f".{t}" in title_lower or f"::{t}" in title_lower for t in q_tokens)
        token_title_overlap = sum(1 for t in q_tokens if t in title_lower) / max(len(q_tokens), 1)

        hop_count = item.metadata.get("hop_distance", 1)

        if exact_title_match:
            base_score = self.config.exact_match_score
        elif item.type in (ContextItemType.SYMBOL, ContextItemType.FILE) and hop_count == 1:
            base_score = self.config.direct_definition_score
        elif item.type in (ContextItemType.CALL_GRAPH, ContextItemType.DEPENDENCY, ContextItemType.TEST, ContextItemType.HERITAGE):
            base_score = self.config.direct_relationship_score if hop_count == 1 else self.config.multi_hop_score
        elif item.type == ContextItemType.SEMANTIC_CODE:
            # Semantic items carry a raw similarity score in metadata (0.0 to 1.0)
            raw_sim = float(item.metadata.get("similarity", 0.7))
            base_score = min(raw_sim * self.config.semantic_weight + (0.2 * token_title_overlap), 1.0)
        else:
            base_score = self.config.background_score

        # Combine with title overlap signal
        final_score = round(base_score + (0.05 * token_title_overlap), 4)
        return min(final_score, 1.0)

    def rank(self, items: List[ContextItem], query: str) -> List[ContextItem]:
        """
        Assigns scores and returns items sorted deterministically:
        Primary: relevance_score (descending)
        Secondary tie-breaker: type.value (ascending)
        Tertiary tie-breaker: id (ascending)
        """
        scored_items: List[ContextItem] = []
        for item in items:
            # If relevance_score not pre-set or 0.0, compute it
            score = self.score_item(item, query)
            item.relevance_score = score
            scored_items.append(item)

        # Deterministic sort with zero nondeterminism
        scored_items.sort(
            key=lambda x: (
                -x.relevance_score,
                x.type.value,
                x.id,
            )
        )
        return scored_items
