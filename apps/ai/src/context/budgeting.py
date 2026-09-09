from __future__ import annotations

from typing import List, Tuple

from src.context.contracts import ContextBudget, ContextItem


def estimate_tokens(text: str) -> int:
    """
    Deterministic token estimation heuristic (~4 characters per token).
    Isolated so a real tokenizer (e.g. tiktoken) can be plugged in later.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def estimate_item_tokens(item: ContextItem) -> int:
    """Estimates total tokens consumed by a single ContextItem."""
    meta_str = str(item.metadata) if item.metadata else ""
    total_chars = len(item.title) + len(item.content) + len(meta_str)
    return max(1, (total_chars + 3) // 4)



class ContextBudgeter:
    """
    Enforces item-count and token-budget limits on ranked candidate items.
    Drops lower-ranked items first, preserving highest-value context.
    """

    def apply_budget(
        self, items: List[ContextItem], budget: ContextBudget
    ) -> Tuple[List[ContextItem], bool]:
        """
        Takes already ranked items and selects top items fitting within budget.
        Returns:
            (budgeted_items, truncated_boolean)
        """
        if not items:
            return [], False

        selected: List[ContextItem] = []
        accumulated_tokens = 0
        truncated = False

        for item in items:
            if len(selected) >= budget.max_items:
                truncated = True
                break

            item_tokens = estimate_item_tokens(item)
            if accumulated_tokens + item_tokens > budget.max_tokens:
                # If even the very first item exceeds budget, include it to avoid empty context
                if not selected:
                    selected.append(item)
                truncated = True
                break

            selected.append(item)
            accumulated_tokens += item_tokens

        return selected, truncated
