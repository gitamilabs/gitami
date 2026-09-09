from src.parsing.models import SymbolNode
from src.analysis.conventions import check_conventions


def test_convention_violations():
    symbols = [
        SymbolNode(
            name="very_long_function",
            kind="function",
            file_path="app.py",
            language="python",
            start_line=1,
            end_line=100,  # 100 lines > 50
            docstring="",  # missing docstring
        ),
        SymbolNode(
            name="bad_class_name",
            kind="class",
            file_path="model.py",
            language="python",
            start_line=1,
            end_line=10,
        ),
    ]

    violations = check_conventions(symbols, max_function_length=50)
    assert len(violations) >= 2

    rules = {v.rule_id for v in violations}
    assert "RULE-001" in rules  # Function length
    assert "RULE-002" in rules  # Missing docstring
    assert "RULE-003" in rules  # PascalCase class name
