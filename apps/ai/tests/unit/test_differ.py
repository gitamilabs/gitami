import tempfile
from pathlib import Path
from git import Repo
from src.repo.differ import get_changed_files, get_changed_symbols


def test_differ_git_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repo = Repo.init(tmp_path)

        # Create initial commit
        file1 = tmp_path / "main.py"
        file1.write_text("def init_app():\n    pass\n")
        repo.index.add(["main.py"])
        commit1 = repo.index.commit("Initial commit")

        # Create second commit modifying main.py and adding helper.py
        file1.write_text("def init_app():\n    print('started')\n")
        file2 = tmp_path / "helper.py"
        file2.write_text("def help_func():\n    return 42\n")
        repo.index.add(["main.py", "helper.py"])
        commit2 = repo.index.commit("Second commit")

        changed_files = get_changed_files(tmp_path, commit1.hexsha, commit2.hexsha)
        assert len(changed_files) == 2

        file_statuses = {cf.file_path: cf.status for cf in changed_files}
        assert file_statuses["main.py"] == "modified"
        assert file_statuses["helper.py"] == "added"

        symbols = get_changed_symbols(tmp_path, commit1.hexsha, commit2.hexsha)
        assert any("init_app" in s for s in symbols)
        assert any("help_func" in s for s in symbols)
        repo.close()
