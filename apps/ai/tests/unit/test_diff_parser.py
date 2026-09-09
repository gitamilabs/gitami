from src.agents.diff_parser import parse_git_diff


def test_parse_git_diff():
    sample_diff = """--- a/src/api.js
+++ b/src/api.js
@@ -2,3 +2,3 @@
 function fetchUsers() {
-    return fetch('/api/v1/users');
+    return fetch('/api/v2/users');
 }
"""
    hunks = parse_git_diff(sample_diff)
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.file_path == "src/api.js"
    assert len(hunk.added_lines) > 0
    assert hunk.added_lines[0][1] == "    return fetch('/api/v2/users');"
