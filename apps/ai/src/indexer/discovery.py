import hashlib
from pathlib import Path
from typing import List, Set, Tuple
from src.indexer.contracts import DiscoveredFile
from src.indexer.snapshot import RepositorySnapshot
from src.parsing.parser import LanguageRegistry

IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".next",
    "out",
    "coverage",
    ".idea",
    ".vscode",
    ".gemini",
    "benchmark_results",
}

IGNORED_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".zip", ".tar", ".gz", ".tgz", ".7z",
    ".pdf", ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyd", ".pyo",
    ".lock", ".lockb",
}


class FileDiscovery:
    """Discovers and filters indexable source files from a RepositorySnapshot."""

    def __init__(
        self,
        ignored_dirs: Set[str] = None,
        ignored_extensions: Set[str] = None,
        max_file_size_bytes: int = 2 * 1024 * 1024,  # 2MB max for single source file
    ):
        self.ignored_dirs = ignored_dirs or IGNORED_DIRECTORIES
        self.ignored_extensions = ignored_extensions or IGNORED_EXTENSIONS
        self.max_file_size_bytes = max_file_size_bytes

    def is_indexable_path(self, rel_path: str) -> bool:
        """Check if a relative file path matches indexing criteria (not in ignored dirs or extensions)."""
        norm = rel_path.replace("\\", "/").lstrip("/")
        parts = norm.split("/")
        if any(part in self.ignored_dirs for part in parts[:-1]):
            return False
        suffix = Path(norm).suffix.lower()
        if not suffix or suffix in self.ignored_extensions:
            return False
        return True

    def get_language_for_path(self, rel_path: str) -> str:
        """Infer canonical language string from file path suffix."""
        suffix = Path(rel_path).suffix.lower()
        lang_tuple = LanguageRegistry.get_language_and_extractor(suffix)
        return lang_tuple[2] if lang_tuple else (suffix[1:] if suffix else "text")

    def discover_files(self, snapshot: RepositorySnapshot) -> Tuple[List[DiscoveredFile], int]:

        """
        Scan snapshot files, filter noise, compute sha256 hashes.
        
        Returns:
            (discovered_files, skipped_count)
        """
        all_files = snapshot.list_files()
        discovered: List[DiscoveredFile] = []
        skipped = 0

        for rel_path in all_files:
            parts = rel_path.split("/")
            # Check directory ignore rules
            if any(part in self.ignored_dirs for part in parts[:-1]):
                skipped += 1
                continue

            # Check extension ignore rules
            suffix = Path(rel_path).suffix.lower()
            if suffix in self.ignored_extensions:
                skipped += 1
                continue

            try:
                code_bytes = snapshot.read_bytes(rel_path)
            except Exception:
                skipped += 1
                continue

            # Check file size boundary
            if len(code_bytes) > self.max_file_size_bytes:
                skipped += 1
                continue

            # Detect language
            lang_tuple = LanguageRegistry.get_language_and_extractor(suffix)
            language = lang_tuple[2] if lang_tuple else (suffix[1:] if suffix else "text")

            sha256 = hashlib.sha256(code_bytes).hexdigest()

            discovered.append(
                DiscoveredFile(
                    file_path=rel_path,
                    language=language,
                    size_bytes=len(code_bytes),
                    sha256=sha256,
                )
            )

        return discovered, skipped
