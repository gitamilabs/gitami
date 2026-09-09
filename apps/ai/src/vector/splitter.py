"""Markdown-Aware and Semantic Text Splitter for non-AST documents (PRs, Issues, Commits, Markdown files)."""

import re
from typing import List


def split_text_by_separators(
    text: str,
    separators: List[str],
    chunk_size: int = 800,
    chunk_overlap: int = 80,
) -> List[str]:
    """Recursively split text using a hierarchical list of separators."""
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    # Find the first separator present in the text
    chosen_sep = ""
    for sep in separators:
        if sep in text:
            chosen_sep = sep
            break

    if not chosen_sep:
        # Fallback: slice by chunk_size directly
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end].strip())
            start += max(1, chunk_size - chunk_overlap)
        return [c for c in chunks if c]

    # Split into raw parts by the chosen separator
    splits = text.split(chosen_sep)
    
    # Merge splits back together up to chunk_size
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for split in splits:
        split_len = len(split) + (len(chosen_sep) if current_chunk else 0)

        if current_length + split_len > chunk_size and current_chunk:
            combined = chosen_sep.join(current_chunk).strip()
            if combined:
                chunks.append(combined)
            
            # Compute overlap: retain last few items if possible
            overlap_parts: List[str] = []
            overlap_len = 0
            for part in reversed(current_chunk):
                if overlap_len + len(part) + len(chosen_sep) <= chunk_overlap:
                    overlap_parts.insert(0, part)
                    overlap_len += len(part) + len(chosen_sep)
                else:
                    break
            current_chunk = overlap_parts
            current_length = overlap_len

        # If a single split itself exceeds chunk_size, recurse on remaining separators
        if len(split) > chunk_size:
            remaining_seps = separators[separators.index(chosen_sep) + 1:]
            if remaining_seps:
                sub_chunks = split_text_by_separators(split, remaining_seps, chunk_size, chunk_overlap)
                for sc in sub_chunks:
                    if current_chunk:
                        chunks.append(chosen_sep.join(current_chunk).strip())
                        current_chunk = []
                        current_length = 0
                    chunks.append(sc)
                continue

        current_chunk.append(split)
        current_length += len(split) + (len(chosen_sep) if len(current_chunk) > 1 else 0)

    if current_chunk:
        combined = chosen_sep.join(current_chunk).strip()
        if combined:
            chunks.append(combined)

    return chunks


def split_markdown_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 80,
) -> List[str]:
    """Split markdown text respecting markdown structural hierarchy.
    
    Hierarchy: Headings (#, ##, ###, ####), Code blocks, Double newlines, Single newlines, Sentences, Words.
    """
    markdown_separators = [
        "\n# ",
        "\n## ",
        "\n### ",
        "\n#### ",
        "```",
        "\n\n",
        "\n",
        ". ",
        "? ",
        "! ",
        " ",
        "",
    ]
    return split_text_by_separators(text, markdown_separators, chunk_size, chunk_overlap)


def split_generic_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 80,
) -> List[str]:
    """Split generic plain text using paragraphs, sentences, and words."""
    plain_separators = [
        "\n\n",
        "\n",
        ". ",
        "? ",
        "! ",
        "; ",
        " ",
        "",
    ]
    return split_text_by_separators(text, plain_separators, chunk_size, chunk_overlap)
