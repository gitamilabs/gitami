import io
import tarfile
from ai_service.parsing.parser import CodeParser
from ai_service.repo.streamer import stream_and_parse_github_repo
from unittest.mock import patch, MagicMock


def test_parse_code_bytes_python():
    parser = CodeParser()
    py_code = b"""
def greet(name: str) -> str:
    \"\"\"Return a greeting message.\"\"\"
    return f"Hello, {name}"

class Greeter:
    def execute(self):
        return greet("World")
"""
    res = parser.parse_code_bytes(py_code, "services/greeter.py")
    assert res is not None
    assert res.language == "python"
    assert res.file_path == "services/greeter.py"
    names = {s.name for s in res.symbols}
    assert "greet" in names
    assert "Greeter" in names
    assert "execute" in names


def test_parse_code_bytes_typescript():
    parser = CodeParser()
    ts_code = b"""
export interface User {
    id: string;
    name: string;
}

export function getUser(id: string): User {
    return { id, name: "Alice" };
}
"""
    res = parser.parse_code_bytes(ts_code, "src/user.ts")
    assert res is not None
    assert res.language == "typescript"
    names = {s.name for s in res.symbols}
    assert "getUser" in names


def test_in_memory_tarball_streaming():
    # Build a simulated in-memory GitHub tarball
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # File 1: Python file
        py_content = b"def calculate_tax(amount):\n    return amount * 0.2\n"
        ti = tarfile.TarInfo(name="myorg-myrepo-12345/src/tax.py")
        ti.size = len(py_content)
        tar.addfile(ti, io.BytesIO(py_content))

        # File 2: Ignored file in node_modules
        ignored_content = b"console.log('ignored')"
        ti_ign = tarfile.TarInfo(name="myorg-myrepo-12345/node_modules/pkg/index.js")
        ti_ign.size = len(ignored_content)
        tar.addfile(ti_ign, io.BytesIO(ignored_content))

    tar_bytes = buf.getvalue()

    # Mock urllib.request.urlopen
    mock_resp = MagicMock()
    mock_resp.read.return_value = tar_bytes
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        results = stream_and_parse_github_repo(
            full_name="myorg/myrepo",
            token="ghp_test_token",
            branch="main",
        )

        assert len(results) == 1
        assert results[0].file_path == "src/tax.py"
        assert len(results[0].symbols) == 1
        assert results[0].symbols[0].name == "calculate_tax"
