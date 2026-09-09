from abc import ABC, abstractmethod
from tree_sitter import Tree
from src.parsing.models import ParseResult, LanguageType


class BaseExtractor(ABC):
    """Abstract base class for language-specific AST extractors."""

    def __init__(self, language: LanguageType):
        self.language = language

    @abstractmethod
    def extract(self, tree: Tree, code_bytes: bytes, file_path: str) -> ParseResult:
        """Extract symbols, calls, and imports from a tree-sitter parse tree."""
        pass
