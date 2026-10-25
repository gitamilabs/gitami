from pathlib import Path
from src.parsing.parser import CodeParser

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "mern_sample"


def test_mern_js_parsing():
    parser = CodeParser()
    service_file = FIXTURE_DIR / "UserService.js"
    result = parser.parse_file(service_file)

    assert result is not None
    assert result.language == "javascript"

    symbol_names = {s.name for s in result.symbols}
    assert "getUserList" in symbol_names
    assert "getUserProfile" in symbol_names
    assert "formatUser" in symbol_names

    # Check ES6 import symbol
    import_syms = [imp.imported_symbol for imp in result.imports]
    assert "fetchUsers" in import_syms or "fetchUserById" in import_syms

    # Check function call inside getUserList
    callees = [c.callee_name for c in result.calls]
    assert "fetchUsers" in callees or "fetchUserById" in callees


def test_mern_jsx_component_parsing():
    parser = CodeParser()
    header_file = FIXTURE_DIR / "Header.jsx"
    result = parser.parse_file(header_file)

    assert result is not None
    assert result.language == "jsx"

    symbols = {s.name: s.kind for s in result.symbols}
    assert "Header" in symbols
    assert symbols["Header"] == "component"


def test_destructuring_not_extracted_as_symbol(tmp_path):
    parser = CodeParser()
    code = """
    export const loginUser = async (req, res) => {
        const { email, password } = req.body;
        const [token, user] = await authenticate(email, password);
        return res.json({ token, user });
    };
    """
    test_file = tmp_path / "authController.ts"
    test_file.write_text(code, encoding="utf-8")

    result = parser.parse_file(test_file)
    assert result is not None
    symbol_names = [s.name for s in result.symbols]
    assert "loginUser" in symbol_names
    assert "{ email, password }" not in symbol_names
    assert "[token, user]" not in symbol_names
    assert not any("{" in name or "[" in name for name in symbol_names)
