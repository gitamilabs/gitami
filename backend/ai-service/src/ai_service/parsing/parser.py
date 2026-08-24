from pathlib import Path
from typing import Dict, Optional
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from ai_service.parsing.models import ParseResult, LanguageType
from ai_service.parsing.extractors.base import BaseExtractor
from ai_service.parsing.extractors.python import PythonExtractor
from ai_service.parsing.extractors.mern import MernExtractor


class LanguageRegistry:
    """Manages tree-sitter language grammars and parsers."""

    _languages: Dict[str, Language] = {}
    _extractors: Dict[str, BaseExtractor] = {}

    @classmethod
    def get_language_and_extractor(cls, extension: str) -> Optional[tuple[Optional[Language], Optional[BaseExtractor], str]]:
        ext = extension.lower()
        if ext in (".py",):
            if "python" not in cls._languages:
                cls._languages["python"] = Language(tspython.language())
                cls._extractors["python"] = PythonExtractor()
            return cls._languages["python"], cls._extractors["python"], "python"

        elif ext in (".js", ".mjs", ".cjs"):
            if "javascript" not in cls._languages:
                cls._languages["javascript"] = Language(tsjs.language())
                cls._extractors["javascript"] = MernExtractor(language="javascript")
            return cls._languages["javascript"], cls._extractors["javascript"], "javascript"

        elif ext in (".jsx",):
            if "jsx" not in cls._languages:
                cls._languages["jsx"] = Language(tsjs.language())
                cls._extractors["jsx"] = MernExtractor(language="jsx")
            return cls._languages["jsx"], cls._extractors["jsx"], "jsx"

        elif ext in (".ts", ".mts", ".cts"):
            if "typescript" not in cls._languages:
                cls._languages["typescript"] = Language(tsts.language_typescript())
                cls._extractors["typescript"] = MernExtractor(language="typescript")
            return cls._languages["typescript"], cls._extractors["typescript"], "typescript"

        elif ext in (".tsx",):
            if "tsx" not in cls._languages:
                cls._languages["tsx"] = Language(tsts.language_tsx())
                cls._extractors["tsx"] = MernExtractor(language="tsx")
            return cls._languages["tsx"], cls._extractors["tsx"], "tsx"

        elif ext in (
            ".json", ".yaml", ".yml", ".md", ".txt", ".html", ".css", ".sh",
            ".toml", ".env", ".sql", ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp"
        ):
            return None, None, ext[1:]

        return None


class CodeParser:
    """High-level code parser interface for parsing files and directories."""

    def __init__(self):
        self._parsers: Dict[str, Parser] = {}

    def _get_parser(self, lang_name: str, language: Language) -> Parser:
        if lang_name not in self._parsers:
            self._parsers[lang_name] = Parser(language)
        return self._parsers[lang_name]

    def parse_code_bytes(self, code_bytes: bytes, file_path: str) -> Optional[ParseResult]:
        """Parse code directly from byte content in-memory without reading from disk."""
        norm_path = file_path.replace("\\", "/")
        ext = Path(norm_path).suffix

        lang_tuple = LanguageRegistry.get_language_and_extractor(ext)
        if not lang_tuple:
            return None  # Unsupported file extension

        language, extractor, lang_type = lang_tuple
        if language is None or extractor is None:
            return ParseResult(file_path=norm_path, language=lang_type)

        parser = self._get_parser(lang_type, language)

        try:
            tree = parser.parse(code_bytes)
            res = extractor.extract(tree, code_bytes, norm_path)
            res.file_path = norm_path
            return res
        except Exception as e:
            return ParseResult(
                file_path=norm_path,
                language=lang_type,
                errors=[f"Failed to parse file bytes: {str(e)}"],
            )

    def parse_file(self, file_path: str | Path, relative_to_dir: Optional[str | Path] = None) -> Optional[ParseResult]:
        path = Path(file_path).resolve()
        if not path.is_file():
            return None

        if relative_to_dir:
            try:
                rel_file_path = path.relative_to(Path(relative_to_dir).resolve()).as_posix()
            except ValueError:
                rel_file_path = str(path).replace("\\", "/")
        else:
            rel_file_path = str(path).replace("\\", "/")

        try:
            code_bytes = path.read_bytes()
            return self.parse_code_bytes(code_bytes, rel_file_path)
        except Exception as e:
            return ParseResult(
                file_path=rel_file_path,
                language="unknown",
                errors=[f"Failed to read file: {str(e)}"],
            )

    def parse_directory(self, dir_path: str | Path, ignore_dirs: Optional[set[str]] = None) -> list[ParseResult]:
        root = Path(dir_path).resolve()
        if not root.is_dir():
            return []

        ignore = ignore_dirs or {".git", "node_modules", ".venv", "__pycache__", "build", "dist", ".next", "out", "coverage"}
        results = []

        for p in root.rglob("*"):
            if p.is_file() and not any(part in ignore for part in p.parts):
                res = self.parse_file(p, relative_to_dir=root)
                if res:
                    results.append(res)

        return results

