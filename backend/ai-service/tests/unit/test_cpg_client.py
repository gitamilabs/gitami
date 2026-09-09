import pytest
from ai_service.cpg.client import JoernClient


def test_joern_client_init():
    client = JoernClient(url="http://localhost:8088", timeout=10)
    assert client.url == "http://localhost:8088"
    assert client.timeout == 10


def test_joern_client_heuristic_fallback(tmp_path):
    # Create sample files in a temporary test repository directory
    sample_file = tmp_path / "routes.py"
    sample_file.write_text(
        "def query_user(req):\n"
        "    if is_admin(req):\n"
        "        db.execute(req.params.id)\n",
        encoding="utf-8"
    )

    client = JoernClient(url="http://localhost:9999", timeout=1)

    # Test reachable guards heuristic
    guards_res = client.get_reachable_guards("db.execute", repo_path=str(tmp_path))
    assert guards_res["engine"] == "static_heuristic"
    assert guards_res["symbol"] == "db.execute"
    assert guards_res["guarded"] is True
    assert any("if is_admin" in g for g in guards_res["guards"])

    # Test callers with args heuristic
    callers_res = client.get_callers_with_args("db.execute", repo_path=str(tmp_path))
    assert callers_res["engine"] == "static_heuristic"
    assert len(callers_res["callers_with_args"]) > 0


def test_joern_client_dataflow_heuristic(tmp_path):
    vuln_file = tmp_path / "vuln.py"
    vuln_file.write_text(
        "def search(req):\n"
        "    user_input = req.query\n"
        "    db.raw_query(user_input)\n",
        encoding="utf-8"
    )

    client = JoernClient(url="http://localhost:9999", timeout=1)
    res = client.check_dataflow(source_pattern="req.query", sink_pattern="raw_query", repo_path=str(tmp_path))
    assert res["engine"] == "static_heuristic"
    assert res["reachable"] is True
    assert len(res["flow_traces"]) > 0
