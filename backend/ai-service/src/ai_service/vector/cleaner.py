"""Smart Chunk Cleaning, Script-Aware Thresholds, and Boilerplate Deduplication."""

import hashlib
import re
import unicodedata
from typing import List, Optional, Set
from ai_service.parsing.models import SymbolNode


def detect_script(text: str) -> str:
    """Detect the dominant script category of a text sample.
    
    Returns one of: 'cjk', 'indic', 'arabic', 'latin', or 'generic'.
    """
    if not text:
        return "generic"

    # Sample the first 150 non-whitespace characters
    sample = [ch for ch in text if not ch.isspace()][:150]
    if not sample:
        return "generic"

    cjk_count = 0
    indic_count = 0
    arabic_count = 0
    latin_count = 0

    for ch in sample:
        name = unicodedata.name(ch, "")
        if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name or "HANGUL" in name:
            cjk_count += 1
        elif any(script in name for script in ("DEVANAGARI", "BENGALI", "TAMIL", "TELUGU", "GUJARATI", "KANNADA", "MALAYALAM")):
            indic_count += 1
        elif "ARABIC" in name:
            arabic_count += 1
        elif "LATIN" in name:
            latin_count += 1

    total = len(sample)
    if total == 0:
        return "generic"

    if cjk_count >= 2 or (cjk_count / total) >= 0.05:
        return "cjk"
    if indic_count >= 2 or (indic_count / total) >= 0.05:
        return "indic"
    if arabic_count >= 2 or (arabic_count / total) >= 0.05:
        return "arabic"
    if (latin_count / total) >= 0.3:
        return "latin"

    return "generic"



# Script-aware minimum character thresholds for meaningful semantic content
SCRIPT_MIN_LENGTHS = {
    "latin": 60,
    "indic": 30,
    "cjk": 20,
    "arabic": 35,
    "generic": 40,
}


def get_script_aware_min_length(script: str) -> int:
    """Return the minimum character threshold for a detected script."""
    return SCRIPT_MIN_LENGTHS.get(script, SCRIPT_MIN_LENGTHS["generic"])


# Common trivial code body patterns that provide zero semantic value
TRIVIAL_BODY_PATTERNS: Set[str] = {
    "pass",
    "...",
    "return",
    "return None",
    "return True",
    "return False",
    "return self",
    "raise NotImplementedError",
    "raise NotImplementedError()",
    "{ }",
    "{}",
    ";",
}


def clean_code_symbol(sym: SymbolNode) -> Optional[SymbolNode]:
    """Tiered smart cleaning for a parsed code symbol.
    
    Returns the cleaned SymbolNode, or None if the symbol is trivial noise.
    """
    docstring = (sym.docstring or "").strip()
    code_body = (sym.code_body or "").strip()

    # If both docstring and code body are empty, drop the symbol
    if not docstring and not code_body:
        return None

    # Check for trivial 1-line stubs without meaningful docstrings
    normalized_body = re.sub(r"\s+", " ", code_body).strip()
    if normalized_body in TRIVIAL_BODY_PATTERNS and len(docstring) < 30:
        return None

    # Script-aware length threshold check
    combined_text = f"{sym.signature}\n{docstring}\n{code_body}".strip()
    script = detect_script(combined_text)
    min_len = get_script_aware_min_length(script)

    if len(combined_text) < min_len and not docstring:
        return None

    return sym


def filter_repetitive_boilerplate(
    symbols: List[SymbolNode],
    threshold_count: int = 5,
    max_body_len: int = 150,
) -> List[SymbolNode]:
    """Pre-ingestion repetitive pattern detection and boilerplate deduplication.
    
    Filters out short, identical method bodies appearing repeatedly across the repository
    (e.g., auto-generated getters, standard pass-through stubs).
    """
    if not symbols:
        return []

    # Count frequencies of normalized short bodies
    body_counts: dict[str, int] = {}
    for sym in symbols:
        body = (sym.code_body or "").strip()
        if body and len(body) <= max_body_len and not (sym.docstring and len(sym.docstring) > 40):
            norm = re.sub(r"\s+", " ", body)
            body_counts[norm] = body_counts.get(norm, 0) + 1

    # Keep unique symbols and first instance of repetitive boilerplate
    seen_boilerplate: Set[str] = set()
    cleaned_symbols: List[SymbolNode] = []

    for sym in symbols:
        body = (sym.code_body or "").strip()
        norm = re.sub(r"\s+", " ", body) if body else ""

        # If this body appears frequently and has no unique docstring, index it only once
        if norm and body_counts.get(norm, 0) >= threshold_count and not (sym.docstring and len(sym.docstring) > 40):
            if norm in seen_boilerplate:
                continue
            seen_boilerplate.add(norm)

        cleaned_symbols.append(sym)

    return cleaned_symbols
