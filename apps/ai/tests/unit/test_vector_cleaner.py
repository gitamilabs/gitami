"""Tests for smart chunk cleaning, script detection, and boilerplate deduplication."""

from src.parsing.models import SymbolNode
from src.vector.cleaner import (
    detect_script,
    get_script_aware_min_length,
    clean_code_symbol,
    filter_repetitive_boilerplate,
)


def test_detect_script():
    assert detect_script("def calculate_total(x: int, y: int) -> int:") == "latin"
    assert detect_script("function नमस्ते() { return 1; }") == "indic"
    assert detect_script("function 計算(x, y) { return x + y; }") == "cjk"
    assert detect_script("def مرحبا(): return True") == "arabic"
    assert detect_script("") == "generic"


def test_get_script_aware_min_length():
    assert get_script_aware_min_length("latin") == 60
    assert get_script_aware_min_length("cjk") == 20
    assert get_script_aware_min_length("indic") == 30
    assert get_script_aware_min_length("arabic") == 35


def test_clean_code_symbol_drops_trivial_stubs():
    trivial_stub = SymbolNode(
        name="stub_func",
        kind="function",
        file_path="service.py",
        language="python",
        start_line=1,
        end_line=2,
        signature="def stub_func(): pass",
        docstring="",
        code_body="pass",
    )
    assert clean_code_symbol(trivial_stub) is None

    meaningful_func = SymbolNode(
        name="authenticate_user",
        kind="function",
        file_path="auth.py",
        language="python",
        start_line=10,
        end_line=25,
        signature="def authenticate_user(token: str) -> UserSession:",
        docstring="Verify JWT signature and retrieve active user session from cache or database.",
        code_body="session = cache.get(token)\nif session:\n    return session\nreturn db.lookup(token)",
    )
    cleaned = clean_code_symbol(meaningful_func)
    assert cleaned is not None
    assert cleaned.name == "authenticate_user"


def test_filter_repetitive_boilerplate():
    symbols = []
    # Add 6 identical getter boilerplate symbols
    for i in range(6):
        symbols.append(
            SymbolNode(
                name=f"get_item_{i}",
                kind="method",
                file_path=f"models/item_{i}.py",
                language="python",
                start_line=1,
                end_line=2,
                signature=f"def get_item_{i}(self):",
                docstring="",
                code_body="return self._item",
            )
        )
    # Add 1 unique function
    symbols.append(
        SymbolNode(
            name="unique_processor",
            kind="function",
            file_path="processor.py",
            language="python",
            start_line=1,
            end_line=10,
            signature="def unique_processor(data: list) -> dict:",
            docstring="Process stream of events into summary report.",
            code_body="return {k: v for k, v in data}",
        )
    )

    filtered = filter_repetitive_boilerplate(symbols, threshold_count=5)
    # The 6 repetitive getters should be deduplicated down to 1, plus the unique processor = 2 symbols total
    assert len(filtered) == 2
    assert any(s.name == "unique_processor" for s in filtered)
