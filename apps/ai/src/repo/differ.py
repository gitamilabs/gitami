"""
Deprecated: src.repo.differ has been consolidated into canonical src.indexer.differ.
This module forwards symbols for backwards compatibility.
"""
from src.indexer.differ import (
    FileStatus,
    LegacyChangedFile as ChangedFile,
    get_changed_files,
    get_changed_symbols,
)

__all__ = ["FileStatus", "ChangedFile", "get_changed_files", "get_changed_symbols"]
