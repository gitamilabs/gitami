import tempfile
from pathlib import Path
from git import Repo
import pytest

from src.indexer.contracts import (
    ChangedFileType,
    IncrementalIndexingStats,
    RepositoryIndexState,
    IndexStateStatus,
)
from src.indexer.differ import GitDiffer
from src.indexer.graph_indexer import make_entity_uid, compute_symbol_uids
from src.parsing.models import SymbolNode


def test_git_differ_lifecycle():
    """Test GitDiffer detects added, modified, deleted, renamed, and ignored files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repo = Repo.init(tmp_path)

        # Commit A
        f_main = tmp_path / "main.py"
        f_main.write_text("def app(): pass\n")
        f_old = tmp_path / "old_service.py"
        f_old.write_text("class OldService: pass\n")
        f_delete = tmp_path / "to_delete.py"
        f_delete.write_text("def del_me(): pass\n")
        f_docs = tmp_path / "logo.png"
        f_docs.write_bytes(b"\x89PNG\r\n\x1a\n")

        repo.index.add(["main.py", "old_service.py", "to_delete.py", "logo.png"])
        commit_a = repo.index.commit("Commit A")

        # Commit B:
        # - modify main.py
        # - rename old_service.py -> new_service.py
        # - delete to_delete.py
        # - add new_feature.py
        # - modify ignored logo.png
        f_main.write_text("def app(): return 42\n")
        
        # Git rename
        repo.index.remove(["old_service.py"])
        f_old.unlink()
        f_new = tmp_path / "new_service.py"
        f_new.write_text("class OldService: pass\n")

        repo.index.remove(["to_delete.py"])
        f_delete.unlink()

        f_added = tmp_path / "new_feature.py"
        f_added.write_text("def feature(): pass\n")

        f_docs.write_bytes(b"\x89PNG\r\n\x1a\nupdated")

        repo.index.add(["main.py", "new_service.py", "new_feature.py", "logo.png"])
        commit_b = repo.index.commit("Commit B")

        differ = GitDiffer()
        diff_res = differ.compute_diff(tmp_path, commit_a.hexsha, commit_b.hexsha)

        assert diff_res.is_ancestor is True
        # logo.png has ignored extension, so it must be filtered out
        assert not any(f.path == "logo.png" for f in diff_res.changed_files)

        types_by_path = {f.path: f.change_type for f in diff_res.changed_files}
        assert types_by_path["main.py"] == ChangedFileType.MODIFIED
        assert types_by_path["new_service.py"] == ChangedFileType.RENAMED
        assert types_by_path["to_delete.py"] == ChangedFileType.DELETED
        assert types_by_path["new_feature.py"] == ChangedFileType.ADDED

        # Verify rename tracking
        renamed_file = next(f for f in diff_res.changed_files if f.path == "new_service.py")
        assert renamed_file.old_path == "old_service.py"

        repo.close()


def test_git_differ_non_ancestor():
    """Test GitDiffer detects non-ancestor commits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repo = Repo.init(tmp_path)

        # Commit A on branch 1
        f1 = tmp_path / "f1.py"
        f1.write_text("x = 1\n")
        repo.index.add(["f1.py"])
        commit_a = repo.index.commit("Commit A")

        # Branch 1 commit
        repo.create_head("branch1")
        f2 = tmp_path / "f2.py"
        f2.write_text("x = 2\n")
        repo.index.add(["f2.py"])
        commit_b1 = repo.index.commit("Commit B1")

        # Branch 2 from Commit A
        repo.head.reference = repo.create_head("branch2", commit_a)
        repo.head.reset(index=True, working_tree=True)
        f3 = tmp_path / "f3.py"
        f3.write_text("x = 3\n")
        repo.index.add(["f3.py"])
        commit_b2 = repo.index.commit("Commit B2")

        differ = GitDiffer()
        # commit_b1 and commit_b2 are parallel divergence
        diff_res = differ.compute_diff(tmp_path, commit_b1.hexsha, commit_b2.hexsha)
        assert diff_res.is_ancestor is False
        assert diff_res.is_safe_incremental is False
        assert "not an ancestor" in diff_res.fallback_reason

        repo.close()


def test_git_differ_large_diff_fallback():
    """Test GitDiffer flags > 50% change percentage as unsafe incremental."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repo = Repo.init(tmp_path)

        # Commit A: 2 files
        f1 = tmp_path / "a.py"
        f1.write_text("x = 1\n")
        f2 = tmp_path / "b.py"
        f2.write_text("y = 2\n")
        repo.index.add(["a.py", "b.py"])
        commit_a = repo.index.commit("Commit A")

        # Commit B: modify both files (100% changed)
        f1.write_text("x = 10\n")
        f2.write_text("y = 20\n")
        repo.index.add(["a.py", "b.py"])
        commit_b = repo.index.commit("Commit B")

        differ = GitDiffer(max_change_percentage=0.50)
        diff_res = differ.compute_diff(tmp_path, commit_a.hexsha, commit_b.hexsha)

        assert diff_res.change_percentage == 1.0
        assert diff_res.is_safe_incremental is False
        assert "exceeds safety threshold" in diff_res.fallback_reason

        repo.close()


def test_deterministic_uid_lexical_scoping():
    """Test UID format: kind:repo_id:normalized_file_path::scope.name."""
    # Class
    uid_class = make_entity_uid("repo1", "class", "src/auth.ts", "AuthManager")
    assert uid_class == "class:repo1:src/auth.ts::AuthManager"

    # Nested method/symbol
    uid_method = make_entity_uid("repo1", "method", "src/auth.ts", "login", parent="AuthManager")
    assert uid_method == "method:repo1:src/auth.ts::AuthManager.login"

    # Function
    uid_func = make_entity_uid("repo1", "function", "src/utils/math.py", "calc")
    assert uid_func == "func:repo1:src/utils/math.py::calc"

    # Test
    uid_test = make_entity_uid("repo1", "test", "tests/test_auth.py", "test_login", parent="AuthSuite")
    assert uid_test == "test:repo1:tests/test_auth.py::AuthSuite.test_login"

    # Verify no commit sha, branch, or line numbers in UID
    assert "main" not in uid_class
    assert "HEAD" not in uid_class
    assert "line" not in uid_class


def test_uid_occurrence_disambiguation():
    """Test deterministic occurrence disambiguation for overloads/duplicates in same scope."""
    symbols = [
        SymbolNode(
            name="execute",
            qualified_name="execute",
            kind="function",
            language="typescript",
            file_path="src/executor.ts",
            start_line=10,
            end_line=12,
            signature="execute(cmd: string): void",
        ),
        SymbolNode(
            name="execute",
            qualified_name="execute",
            kind="function",
            language="typescript",
            file_path="src/executor.ts",
            start_line=15,
            end_line=18,
            signature="execute(cmd: string, timeout: number): void",
        ),
        SymbolNode(
            name="single_func",
            qualified_name="single_func",
            kind="function",
            language="typescript",
            file_path="src/executor.ts",
            start_line=20,
            end_line=22,
        ),
    ]

    computed = compute_symbol_uids("myrepo", "src/executor.ts", symbols)
    assert len(computed) == 3

    # First duplicate -> #0
    assert computed[0][2] == "func:myrepo:src/executor.ts::execute#0"
    # Second duplicate -> #1
    assert computed[1][2] == "func:myrepo:src/executor.ts::execute#1"
    # Single declaration -> no suffix
    assert computed[2][2] == "func:myrepo:src/executor.ts::single_func"


def test_repository_index_state_advance():
    """Test RepositoryIndexState atomic transitions and error tracking."""
    state = RepositoryIndexState(
        repository_id="repo-1",
        branch="main",
        indexed_commit_sha="commit-aaa",
        status=IndexStateStatus.READY,
        generation=1,
    )

    stats = IncrementalIndexingStats(
        base_commit_sha="commit-aaa",
        target_commit_sha="commit-bbb",
        files_added=1,
        files_modified=2,
        files_deleted=1,
    )

    state.advance_to("commit-bbb", stats=stats.model_dump())

    assert state.indexed_commit_sha == "commit-bbb"
    assert state.previous_commit_sha == "commit-aaa"
    assert state.generation == 2
    assert state.status == IndexStateStatus.READY
    assert state.last_successful_index_at is not None
    assert state.indexing_error is None
    assert state.stats["files_modified"] == 2


def test_rename_changes_symbol_uids():
    """Verify that file rename changes entity UIDs because canonical residence changes."""
    old_symbols = [
        SymbolNode(name="Service", qualified_name="Service", kind="class", language="python", file_path="v1/service.py", start_line=1, end_line=10),
        SymbolNode(name="run", qualified_name="Service.run", class_name="Service", kind="method", language="python", file_path="v1/service.py", start_line=3, end_line=5),
    ]
    new_symbols = [
        SymbolNode(name="Service", qualified_name="Service", kind="class", language="python", file_path="v2/service.py", start_line=1, end_line=10),
        SymbolNode(name="run", qualified_name="Service.run", class_name="Service", kind="method", language="python", file_path="v2/service.py", start_line=3, end_line=5),
    ]

    old_computed = compute_symbol_uids("repoX", "v1/service.py", old_symbols)
    new_computed = compute_symbol_uids("repoX", "v2/service.py", new_symbols)

    old_uids = {uid for _, _, uid in old_computed}
    new_uids = {uid for _, _, uid in new_computed}

    # Must be completely disjoint - path-derived UIDs do not carry over across renames
    assert len(old_uids.intersection(new_uids)) == 0
    assert "class:repoX:v1/service.py::Service" in old_uids
    assert "class:repoX:v2/service.py::Service" in new_uids


def test_symbol_reconciliation_set_math():
    """Verify the S_old, S_new mathematical reconciliation."""
    old_uids = {
        "func:repo:src/calc.py::add",
        "func:repo:src/calc.py::subtract",
        "func:repo:src/calc.py::multiply",
    }
    
    # New symbols: subtract removed, divide added, add kept, multiply kept
    new_symbols = [
        SymbolNode(name="add", qualified_name="add", kind="function", language="python", file_path="src/calc.py", start_line=1, end_line=2),
        SymbolNode(name="multiply", qualified_name="multiply", kind="function", language="python", file_path="src/calc.py", start_line=4, end_line=5),
        SymbolNode(name="divide", qualified_name="divide", kind="function", language="python", file_path="src/calc.py", start_line=7, end_line=8),
    ]

    new_computed = compute_symbol_uids("repo", "src/calc.py", new_symbols)
    new_uids = {uid for _, _, uid in new_computed}

    to_delete = old_uids - new_uids
    to_create = new_uids - old_uids
    to_update = new_uids & old_uids

    assert to_delete == {"func:repo:src/calc.py::subtract"}
    assert to_create == {"func:repo:src/calc.py::divide"}
    assert to_update == {"func:repo:src/calc.py::add", "func:repo:src/calc.py::multiply"}

