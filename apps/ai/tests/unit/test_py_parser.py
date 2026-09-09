from pathlib import Path
from src.parsing.parser import CodeParser

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "python_sample"


def test_python_file_parsing():
    parser = CodeParser()
    calc_file = FIXTURE_DIR / "calculator.py"
    result = parser.parse_file(calc_file)

    assert result is not None
    assert result.language == "python"
    assert len(result.symbols) == 3  # add, MathService, compute

    symbol_names = {s.name for s in result.symbols}
    assert "add" in symbol_names
    assert "MathService" in symbol_names
    assert "compute" in symbol_names

    # Check symbol details
    add_sym = next(s for s in result.symbols if s.name == "add")
    assert add_sym.kind == "function"
    assert add_sym.docstring == "Add two numbers together."

    math_sym = next(s for s in result.symbols if s.name == "MathService")
    assert math_sym.kind == "class"

    compute_sym = next(s for s in result.symbols if s.name == "compute")
    assert compute_sym.kind == "method"

    # Check calls
    assert len(result.calls) >= 1
    callee_names = [c.callee_name for c in result.calls]
    assert "add" in callee_names
