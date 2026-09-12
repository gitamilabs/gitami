import pytest
from ai_service.benchmark.datasets.martian_adapter import locate_comment_target
from ai_service.agent.diff_parser import DiffHunk
from ai_service.agent.reviewer import deduplicate_issues


def test_locate_comment_target_token_matching():
    hunk1 = DiffHunk(
        file_path="apps/web/components/auth/BackupCode.tsx",
        status="modified",
        added_lines=[(1, "export function BackupCode() {"), (2, "  return <div>Backup Code</div>;")],
        removed_lines=[],
    )
    hunk2 = DiffHunk(
        file_path="apps/web/components/settings/EnableTwoFactorModal.tsx",
        status="modified",
        added_lines=[
            (90, "  const textBlob = new Blob([codes.join('\\n')]);"),
            (95, "  setBackupCodesUrl(URL.createObjectURL(textBlob));"),
        ],
        removed_lines=[],
    )

    changed_files = [
        "apps/web/components/auth/BackupCode.tsx",
        "apps/web/components/settings/EnableTwoFactorModal.tsx",
    ]

    comment = "Object URL for backup codes is not revoked on component unmount, leading to a potential memory leak."

    file_path, line_no = locate_comment_target(comment, [hunk1, hunk2], changed_files)
    assert file_path == "apps/web/components/settings/EnableTwoFactorModal.tsx"
    assert line_no == 95


def test_locate_comment_target_explicit_filename():
    hunk1 = DiffHunk(
        file_path="apps/web/components/auth/BackupCode.tsx",
        status="modified",
        added_lines=[(1, "export function TwoFactor() {")],
        removed_lines=[],
    )
    hunk2 = DiffHunk(
        file_path="apps/web/components/settings/EnableTwoFactorModal.tsx",
        status="modified",
        added_lines=[(85, "export function EnableModal() {")],
        removed_lines=[],
    )
    changed_files = [
        "apps/web/components/settings/EnableTwoFactorModal.tsx",
        "apps/web/components/auth/BackupCode.tsx",
    ]

    comment = "The exported function TwoFactor handles backup codes and is in BackupCode.tsx. Inconsistent naming."

    file_path, line_no = locate_comment_target(comment, [hunk1, hunk2], changed_files)
    assert file_path == "apps/web/components/auth/BackupCode.tsx"


def test_locate_comment_target_fallback():
    changed_files = ["default/first/file.ts", "second/file.ts"]
    comment = "Generic observation that has zero overlap with diff content."
    file_path, line_no = locate_comment_target(comment, [], changed_files)
    assert file_path == "default/first/file.ts"


def test_deduplicate_issues():
    issues = [
        {
            "id": "1",
            "title": "Dynamic imports in videoClient lack error handling",
            "description": "In videoClient.ts function getVideoAdapters awaits dynamic import without try/catch.",
            "file_path": "packages/core/videoClient.ts",
            "line": 20,
            "severity": "warning",
        },
        {
            "id": "2",
            "title": "Potential unhandled rejection in getBusyVideoTimes due to missing await on getVideoAdapters errors",
            "description": "getVideoAdapters dynamic import can throw and reject without surrounding try/catch.",
            "file_path": "packages/core/videoClient.ts",
            "line": 30,
            "severity": "error",
        },
        {
            "id": "3",
            "title": "Potential unhandled rejection in getBusyVideoTimes",
            "description": "Missing error handling for getVideoAdapters inside getBusyVideoTimes.",
            "file_path": "packages/core/videoClient.ts",
            "line": 30,
            "severity": "warning",
        },
        {
            "id": "4",
            "title": "SQL Injection in searchUsers",
            "description": "Raw string formatting in SQL query.",
            "file_path": "packages/db/search.ts",
            "line": 100,
            "severity": "critical",
        },
    ]

    deduped = deduplicate_issues(issues, line_window=15)
    # The 3 overlapping issues in videoClient.ts should be consolidated
    video_issues = [i for i in deduped if i["file_path"] == "packages/core/videoClient.ts"]
    assert len(video_issues) < 3
    # The distinct issue in search.ts should remain intact
    db_issues = [i for i in deduped if i["file_path"] == "packages/db/search.ts"]
    assert len(db_issues) == 1
