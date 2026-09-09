from dataclasses import dataclass, field
from typing import Literal, Optional, List

SymbolKind = Literal[
    "function",
    "class",
    "component",
    "method",
    "module",
    "interface",
    "type",
    "test",
]
LanguageType = Literal["python", "javascript", "typescript", "tsx", "jsx", "unknown"]


@dataclass
class SymbolNode:
    """Represents a code symbol (function, class, method, interface, type, test, etc.)."""
    name: str
    kind: SymbolKind
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    code_body: str = ""
    qualified_name: str = ""
    class_name: Optional[str] = None
    superclasses: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.qualified_name:
            if self.class_name:
                self.qualified_name = f"{self.file_path}::{self.class_name}.{self.name}"
            else:
                self.qualified_name = f"{self.file_path}::{self.name}"


@dataclass
class CallEdge:
    """Represents an invocation edge: caller -> callee."""
    caller_symbol: str  # qualified name of caller
    callee_name: str    # target function/method name being invoked
    file_path: str
    line: int


@dataclass
class ImportEdge:
    """Represents an import relationship."""
    importer_file: str
    imported_symbol: str
    module_path: str
    line: int


@dataclass
class HeritageEdge:
    """Represents inheritance or implementation (EXTENDS / IMPLEMENTS)."""
    subclass_name: str
    target_name: str
    kind: Literal["extends", "implements"]
    file_path: str
    line: int


@dataclass
class ParseResult:
    """Combined output of parsing a single file."""
    file_path: str
    language: str
    symbols: list[SymbolNode] = field(default_factory=list)
    calls: list[CallEdge] = field(default_factory=list)
    imports: list[ImportEdge] = field(default_factory=list)
    heritage: list[HeritageEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
