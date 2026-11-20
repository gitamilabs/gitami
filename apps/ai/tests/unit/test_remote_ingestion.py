import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.indexer.contracts import ChangedFileType, DiffResult
from src.indexer.remote import GitHubApiDiffer, RemoteGitHubSnapshot


@pytest.fixture
def sample_compare_payload():
    return {
        "status": "ahead",
        "ahead_by": 2,
        "behind_by": 0,
        "total_commits": 2,
        "files": [
            {
                "filename": "src/utils.ts",
                "status": "added",
                "additions": 15,
                "deletions": 0,
                "changes": 15,
                "patch": "@@ -0,0 +1,15 @@\n+export function helper() {}",
            },
            {
                "filename": "src/auth.ts",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "changes": 7,
                "patch": "@@ -10,2 +10,5 @@",
            },
            {
                "filename": "src/old_helpers.ts",
                "status": "removed",
                "additions": 0,
                "deletions": 20,
                "changes": 20,
            },
            {
                "filename": "src/services/user_service.ts",
                "previous_filename": "src/user_service.ts",
                "status": "renamed",
                "additions": 1,
                "deletions": 1,
                "changes": 2,
            },
        ],
    }


def test_github_differ_computes_delta_successfully(sample_compare_payload):
    differ = GitHubApiDiffer()

    with patch.object(differ, "_fetch_compare_api", return_value=sample_compare_payload):
        res = differ.compute_diff(
            full_name="owner/repo",
            base_commit_sha="base_111",
            target_commit_sha="head_222",
            access_token="test_token",
        )

        assert isinstance(res, DiffResult)
        assert res.base_commit_sha == "base_111"
        assert res.target_commit_sha == "head_222"
        assert res.is_ancestor is True
        assert res.is_safe_incremental is True
        assert res.fallback_reason is None

        # Verify categorization
        assert len(res.added) == 1
        assert res.added[0].path == "src/utils.ts"
        assert res.added[0].change_type == ChangedFileType.ADDED

        assert len(res.modified) == 1
        assert res.modified[0].path == "src/auth.ts"
        assert res.modified[0].change_type == ChangedFileType.MODIFIED

        assert len(res.deleted) == 1
        assert res.deleted[0].path == "src/old_helpers.ts"
        assert res.deleted[0].change_type == ChangedFileType.DELETED

        assert len(res.renamed) == 1
        assert res.renamed[0].path == "src/services/user_service.ts"
        assert res.renamed[0].old_path == "src/user_service.ts"
        assert res.renamed[0].change_type == ChangedFileType.RENAMED


def test_github_differ_detects_force_push_divergence():
    differ = GitHubApiDiffer()
    diverged_payload = {
        "status": "diverged",
        "ahead_by": 3,
        "behind_by": 5,
        "files": [{"filename": "src/auth.ts", "status": "modified"}],
    }

    with patch.object(differ, "_fetch_compare_api", return_value=diverged_payload):
        res = differ.compute_diff(
            full_name="owner/repo",
            base_commit_sha="base_111",
            target_commit_sha="head_222",
        )

        assert res.is_ancestor is False
        assert res.is_safe_incremental is False
        assert "diverged" in (res.fallback_reason or "").lower()


def test_github_differ_detects_oversized_diff_threshold():
    differ = GitHubApiDiffer(max_changed_files_threshold=50)
    oversized_files = [
        {"filename": f"src/file_{i}.ts", "status": "modified"}
        for i in range(55)
    ]
    oversized_payload = {
        "status": "ahead",
        "ahead_by": 1,
        "behind_by": 0,
        "files": oversized_files,
    }

    with patch.object(differ, "_fetch_compare_api", return_value=oversized_payload):
        res = differ.compute_diff(
            full_name="owner/repo",
            base_commit_sha="base_111",
            target_commit_sha="head_222",
        )

        assert res.is_safe_incremental is False
        assert "exceeds" in (res.fallback_reason or "").lower()


def test_github_differ_detects_root_config_alteration():
    differ = GitHubApiDiffer()
    config_payload = {
        "status": "ahead",
        "ahead_by": 1,
        "behind_by": 0,
        "files": [
            {"filename": "src/auth.ts", "status": "modified"},
            {"filename": "tsconfig.json", "status": "modified"},
        ],
    }

    with patch.object(differ, "_fetch_compare_api", return_value=config_payload):
        res = differ.compute_diff(
            full_name="owner/repo",
            base_commit_sha="base_111",
            target_commit_sha="head_222",
        )

        assert res.is_safe_incremental is False
        assert "configuration file" in (res.fallback_reason or "").lower()


def test_remote_github_snapshot_reads_in_memory_bytes_without_disk(tmp_path):
    # Remote snapshot holds files in memory
    preloaded = {
        "src/auth.ts": b"export function login() { return true; }",
        "src/utils.ts": b"export const PI = 3.14;",
    }

    snapshot = RemoteGitHubSnapshot(
        full_name="owner/repo",
        commit_sha="target_commit_sha_123",
        access_token="mock_token",
        preloaded_files=preloaded,
    )

    with snapshot:
        assert snapshot.resolved_commit_sha == "target_commit_sha_123"
        assert snapshot.read_bytes("src/auth.ts") == b"export function login() { return true; }"
        assert snapshot.read_bytes("src/utils.ts") == b"export const PI = 3.14;"
        assert sorted(snapshot.list_files()) == ["src/auth.ts", "src/utils.ts"]

    # Trying to read a non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        snapshot.read_bytes("src/missing.ts")
