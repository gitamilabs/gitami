from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional
from git import Repo

from src.parsing.parser import CodeParser

FileStatus = Literal["added", "modified", "deleted", "renamed"]


@dataclass
class ChangedFile:
    file_path: str
    status: FileStatus
    old_path: Optional[str] = None


def get_changed_files(repo_path: str | Path, base_ref: str, head_ref: str) -> List[ChangedFile]:
    """Compute changed files between base_ref and head_ref in git repo."""
    try:
        repo = Repo(repo_path, search_parent_directories=True)
    except Exception:
        return []

    try:
        diffs = repo.commit(base_ref).diff(repo.commit(head_ref))

        results = []
        for d in diffs:
            if d.new_file:
                results.append(ChangedFile(file_path=d.b_path, status="added"))
            elif d.deleted_file:
                results.append(ChangedFile(file_path=d.a_path, status="deleted"))
            elif d.renamed_file:
                results.append(ChangedFile(file_path=d.b_path, status="renamed", old_path=d.a_path))
            else:
                results.append(ChangedFile(file_path=d.b_path, status="modified"))

        return results
    finally:
        repo.close()


def get_changed_symbols(repo_path: str | Path, base_ref: str, head_ref: str) -> List[str]:
    """Identify exact symbol qualified names affected by code changes between base_ref and head_ref."""
    root = Path(repo_path)
    changed_files = get_changed_files(root, base_ref, head_ref)
    parser = CodeParser()

    changed_symbols = []

    for cf in changed_files:
        if cf.status in ("added", "modified"):
            file_abs_path = root / cf.file_path
            parse_res = parser.parse_file(file_abs_path)
            if parse_res and parse_res.symbols:
                # If file is added or modified, map symbols in this file
                for sym in parse_res.symbols:
                    changed_symbols.append(sym.qualified_name)
        elif cf.status in ("deleted", "renamed"):
            # Mark file level symbol
            changed_symbols.append(f"{cf.file_path}::<deleted>")

    return changed_symbols
