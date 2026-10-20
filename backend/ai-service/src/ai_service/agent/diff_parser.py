import re
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
from unidiff import PatchSet


@dataclass
class DiffHunk:
    file_path: str
    status: str
    added_lines: List[Tuple[int, str]] = field(default_factory=list)
    removed_lines: List[Tuple[int, str]] = field(default_factory=list)
    patch_text: str = ""


def parse_git_diff(raw_diff_text: str) -> List[DiffHunk]:
    """Parse raw git diff patch text into structured file hunks with line numbers."""
    if not raw_diff_text.strip():
        return []

    try:
        patch = PatchSet(raw_diff_text)
        hunks: List[DiffHunk] = []

        for patched_file in patch:
            path = patched_file.target_file or patched_file.source_file
            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]

            status = "modified"
            if patched_file.is_added_file:
                status = "added"
            elif patched_file.is_removed_file:
                status = "deleted"

            added_lines = []
            removed_lines = []

            for hunk in patched_file:
                for line in hunk:
                    if line.is_added and line.target_line_no is not None:
                        added_lines.append((line.target_line_no, line.value.rstrip("\r\n")))
                    elif line.is_removed and line.source_line_no is not None:
                        removed_lines.append((line.source_line_no, line.value.rstrip("\r\n")))

            hunks.append(
                DiffHunk(
                    file_path=path,
                    status=status,
                    added_lines=added_lines,
                    removed_lines=removed_lines,
                    patch_text=str(patched_file),
                )
            )
        return hunks
    except Exception:
        # Fallback simple parser if unidiff strict parsing fails on raw commit string
        return [
            DiffHunk(
                file_path="modified_files",
                status="modified",
                patch_text=raw_diff_text,
            )
        ]


def group_hunks_by_file(hunks: List[DiffHunk]) -> Dict[str, List[DiffHunk]]:
    """Group parsed diff hunks by target file path."""
    grouped: Dict[str, List[DiffHunk]] = {}
    for hunk in hunks:
        path = hunk.file_path or "codebase"
        grouped.setdefault(path, []).append(hunk)
    return grouped


def chunk_diff_by_files(
    hunks: List[DiffHunk], max_chars_per_chunk: int = 5000
) -> List[Tuple[List[str], str]]:
    """
    Partition diff hunks across files into bounded chunks.
    Returns list of (file_paths, chunk_diff_text) pairs so long diffs
    can be inspected without dropping any changed file.
    """
    chunks: List[Tuple[List[str], str]] = []
    curr_files: List[str] = []
    curr_patches: List[str] = []
    curr_len = 0

    grouped = group_hunks_by_file(hunks)
    for file_path, file_hunks in grouped.items():
        file_patch = "\n".join(h.patch_text for h in file_hunks if h.patch_text)
        if not file_patch:
            continue
        patch_len = len(file_patch)

        if curr_len + patch_len > max_chars_per_chunk and curr_patches:
            chunks.append((list(curr_files), "\n".join(curr_patches)))
            curr_files = []
            curr_patches = []
            curr_len = 0

        curr_files.append(file_path)
        if patch_len > max_chars_per_chunk:
            curr_patches.append(file_patch[:max_chars_per_chunk])
            curr_len += max_chars_per_chunk
        else:
            curr_patches.append(file_patch)
            curr_len += patch_len

    if curr_patches:
        chunks.append((list(curr_files), "\n".join(curr_patches)))

    return chunks


def extract_changed_symbols(hunks: List[DiffHunk], raw_diff_text: str) -> List[str]:
    """Extract modified function, class, and method names from diff hunks."""
    symbols = set()

    # Regex patterns for Python, JS/TS, Java, C++, Go, Rust definitions
    patterns = [
        r"(?:def|function|class|async\s+function)\s+([a-zA-Z0-9_]+)",
        r"(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(",
        r"(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*function",
        r"@@\s+.*\s+@@\s*(?:def|function|class)?\s*([a-zA-Z0-9_]+)",
        r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+([a-zA-Z0-9_]+)",
    ]

    reserved_words = {
        "if", "for", "while", "switch", "catch", "return", "try", "finally",
        "else", "import", "from", "export", "default", "type", "interface",
        "void", "null", "undefined", "true", "false", "new", "this", "super",
    }

    # Prioritize added lines first to find new/modified definitions
    lines_to_check = []
    for hunk in hunks:
        for _, line_str in hunk.added_lines:
            lines_to_check.append(line_str)

    # Fallback to general lines if no added lines found
    if not lines_to_check:
        for hunk in hunks:
            for _, line_str in hunk.removed_lines:
                lines_to_check.append(line_str)
        if not lines_to_check:
            lines_to_check = raw_diff_text.splitlines()

    for line in lines_to_check:
        for pat in patterns:
            matches = re.findall(pat, line)
            for m in matches:
                if m and len(m) > 1 and m not in reserved_words:
                    symbols.add(m)

    return list(symbols)
