"""
Curated Benchmark Dataset for Vulnerability Detection & False Positive Evaluation.
Covers real-world CVE/CWE patterns across Python and JavaScript/TypeScript (MERN).
Designed to benchmark Pair-wise Correct Rate (P-C) and False Positive Reduction
as demonstrated in the VulAgentRL paper.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class BenchmarkCase:
    case_id: str
    language: str  # "python" or "javascript"
    cwe: str  # e.g. "CWE-89", "CWE-79", "CWE-22", "CWE-78", "CWE-287"
    title: str
    target_file: str
    description: str
    vulnerable_diff: str
    patched_diff: str
    caller_callee_context: str  # Code of callers or callees showing guards or sanitizers
    vulnerable_evidence_nodes: List[str]  # Graph nodes that must be cited for the vuln
    patched_falsification_nodes: List[str]  # Graph nodes proving the bug is falsified/guarded


BENCHMARK_CASES: List[BenchmarkCase] = [
    # ── CASE 1: Python SQL Injection (CWE-89) ──────────────────────────────────
    BenchmarkCase(
        case_id="PY-CVE-2023-8901",
        language="python",
        cwe="CWE-89",
        title="SQL Injection in User Search Query",
        target_file="app/db/repositories.py",
        description="Unsanitized search term interpolated directly into SQL query vs. parameterized query.",
        vulnerable_diff="""--- a/app/db/repositories.py
+++ b/app/db/repositories.py
@@ -10,3 +10,3 @@
 def search_users(db, query_str: str):
-    # Safe parameterized query
-    return db.execute("SELECT * FROM users WHERE name = :q", {"q": query_str}).fetchall()
+    # Raw string format allows SQL injection
+    return db.execute(f"SELECT * FROM users WHERE name = '{query_str}'").fetchall()
""",
        patched_diff="""--- a/app/db/repositories.py
+++ b/app/db/repositories.py
@@ -10,3 +10,3 @@
 def search_users(db, query_str: str):
-    return db.execute(f"SELECT * FROM users WHERE name = '{query_str}'").fetchall()
+    # Parameterized query with strict type binding
+    return db.execute("SELECT * FROM users WHERE name = :q", {"q": query_str}).fetchall()
""",
        caller_callee_context="""# app/api/users.py (Caller)
@router.get("/users/search")
async def search_endpoint(q: str = Query(...), db = Depends(get_db)):
    return search_users(db, q)
""",
        vulnerable_evidence_nodes=["app/db/repositories.py::search_users", "db.execute"],
        patched_falsification_nodes=["app/db/repositories.py::search_users", "db.execute:param_binding"],
    ),

    # ── CASE 2: MERN SQL/NoSQL Injection (CWE-89) ──────────────────────────────
    BenchmarkCase(
        case_id="JS-CVE-2023-8902",
        language="javascript",
        cwe="CWE-89",
        title="NoSQL Query Selector Injection in Express Authentication",
        target_file="src/controllers/authController.js",
        description="Passing unvalidated req.body directly to User.findOne vs. schema-enforced string sanitize.",
        vulnerable_diff="""--- a/src/controllers/authController.js
+++ b/src/controllers/authController.js
@@ -14,3 +14,3 @@
 exports.login = async (req, res) => {
-    const user = await User.findOne({ username: String(req.body.username), password: req.body.password });
+    const user = await User.findOne({ username: req.body.username, password: req.body.password });
     if (!user) return res.status(401).json({ error: "Invalid credentials" });
""",
        patched_diff="""--- a/src/controllers/authController.js
+++ b/src/controllers/authController.js
@@ -14,3 +14,3 @@
 exports.login = async (req, res) => {
-    const user = await User.findOne({ username: req.body.username, password: req.body.password });
+    const safeUsername = typeof req.body.username === 'string' ? req.body.username.trim() : "";
+    const user = await User.findOne({ username: safeUsername, password: req.body.password });
""",
        caller_callee_context="""// src/routes/authRoutes.js (Caller)
const router = require('express').Router();
const { validateLoginSchema } = require('../middleware/validator');
router.post('/login', validateLoginSchema, authController.login);
""",
        vulnerable_evidence_nodes=["src/controllers/authController.js::login", "User.findOne"],
        patched_falsification_nodes=["src/controllers/authController.js::login", "validateLoginSchema"],
    ),

    # ── CASE 3: Python Stored/Reflected XSS (CWE-79) ───────────────────────────
    BenchmarkCase(
        case_id="PY-CVE-2022-7901",
        language="python",
        cwe="CWE-79",
        title="Unescaped HTML Template Rendering (XSS)",
        target_file="app/views/comments.py",
        description="Wrapping user-submitted markdown in markupsafe.Markup without sanitization.",
        vulnerable_diff="""--- a/app/views/comments.py
+++ b/app/views/comments.py
@@ -8,3 +8,3 @@
 def render_comment(user_text: str):
-    clean_html = nh3.clean(user_text)
-    return Markup(clean_html)
+    return Markup(f"<div class='comment'>{user_text}</div>")
""",
        patched_diff="""--- a/app/views/comments.py
+++ b/app/views/comments.py
@@ -8,3 +8,3 @@
 def render_comment(user_text: str):
-    return Markup(f"<div class='comment'>{user_text}</div>")
+    clean_text = html.escape(user_text)
+    return Markup(f"<div class='comment'>{clean_text}</div>")
""",
        caller_callee_context="""# app/controllers/feed.py (Caller)
def display_feed(post_id):
    comments = get_comments(post_id)
    return [render_comment(c.text) for c in comments]
""",
        vulnerable_evidence_nodes=["app/views/comments.py::render_comment", "markupsafe.Markup"],
        patched_falsification_nodes=["app/views/comments.py::render_comment", "html.escape"],
    ),

    # ── CASE 4: MERN React XSS via dangerouslySetInnerHTML (CWE-79) ───────────
    BenchmarkCase(
        case_id="JS-CVE-2023-7902",
        language="javascript",
        cwe="CWE-79",
        title="React DOM XSS via raw dangerouslySetInnerHTML",
        target_file="src/components/UserProfile.jsx",
        description="Setting raw user bio string in dangerouslySetInnerHTML without DOMPurify.",
        vulnerable_diff="""--- a/src/components/UserProfile.jsx
+++ b/src/components/UserProfile.jsx
@@ -12,3 +12,3 @@
 export function UserProfile({ user }) {
-    return <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user.bio) }} />;
+    return <div dangerouslySetInnerHTML={{ __html: user.bio }} />;
 }
""",
        patched_diff="""--- a/src/components/UserProfile.jsx
+++ b/src/components/UserProfile.jsx
@@ -12,3 +12,3 @@
 export function UserProfile({ user }) {
-    return <div dangerouslySetInnerHTML={{ __html: user.bio }} />;
+    return <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user.bio) }} />;
 }
""",
        caller_callee_context="""// src/pages/ProfilePage.jsx (Caller)
import { UserProfile } from '../components/UserProfile';
export default function ProfilePage() {
    const { user } = useAuth();
    return <UserProfile user={user} />;
}
""",
        vulnerable_evidence_nodes=["src/components/UserProfile.jsx::UserProfile", "dangerouslySetInnerHTML"],
        patched_falsification_nodes=["src/components/UserProfile.jsx::UserProfile", "DOMPurify.sanitize"],
    ),

    # ── CASE 5: Python Path Traversal (CWE-22) ─────────────────────────────────
    BenchmarkCase(
        case_id="PY-CVE-2023-2201",
        language="python",
        cwe="CWE-22",
        title="Arbitrary File Read via Unvalidated Filename",
        target_file="app/services/filestore.py",
        description="Concatenating untrusted filename to base dir without checking realpath boundary.",
        vulnerable_diff="""--- a/app/services/filestore.py
+++ b/app/services/filestore.py
@@ -15,3 +15,3 @@
 def retrieve_report(filename: str) -> bytes:
-    safe_name = os.path.basename(filename)
-    full_path = os.path.join(UPLOAD_DIR, safe_name)
+    full_path = os.path.join(UPLOAD_DIR, filename)
     with open(full_path, "rb") as f:
         return f.read()
""",
        patched_diff="""--- a/app/services/filestore.py
+++ b/app/services/filestore.py
@@ -15,3 +15,4 @@
 def retrieve_report(filename: str) -> bytes:
-    full_path = os.path.join(UPLOAD_DIR, filename)
+    safe_name = os.path.basename(filename)
+    full_path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_name))
+    if not full_path.startswith(os.path.abspath(UPLOAD_DIR)):
+        raise PermissionError("Path traversal detected")
     with open(full_path, "rb") as f:
""",
        caller_callee_context="""# app/api/reports.py (Caller)
@router.get("/download")
def download_report(file: str):
    return Response(content=retrieve_report(file), media_type="application/pdf")
""",
        vulnerable_evidence_nodes=["app/services/filestore.py::retrieve_report", "open"],
        patched_falsification_nodes=["app/services/filestore.py::retrieve_report", "os.path.basename"],
    ),

    # ── CASE 6: MERN Path Traversal (CWE-22) ───────────────────────────────────
    BenchmarkCase(
        case_id="JS-CVE-2023-2202",
        language="javascript",
        cwe="CWE-22",
        title="Path Traversal in Static Asset Delivery",
        target_file="server/routes/assets.js",
        description="Unrestricted file path resolving outside public assets folder.",
        vulnerable_diff="""--- a/server/routes/assets.js
+++ b/server/routes/assets.js
@@ -10,3 +10,3 @@
 router.get('/assets/:filename', (req, res) => {
-    const filePath = path.resolve(ASSETS_DIR, path.basename(req.params.filename));
+    const filePath = path.join(ASSETS_DIR, req.params.filename);
     res.sendFile(filePath);
 });
""",
        patched_diff="""--- a/server/routes/assets.js
+++ b/server/routes/assets.js
@@ -10,3 +10,4 @@
 router.get('/assets/:filename', (req, res) => {
-    const filePath = path.join(ASSETS_DIR, req.params.filename);
+    const safeFile = path.basename(req.params.filename);
+    const filePath = path.resolve(ASSETS_DIR, safeFile);
     if (!filePath.startsWith(ASSETS_DIR)) return res.status(403).send("Forbidden");
     res.sendFile(filePath);
 });
""",
        caller_callee_context="""// server/app.js (Caller)
const assetsRouter = require('./routes/assets');
app.use('/static', assetsRouter);
""",
        vulnerable_evidence_nodes=["server/routes/assets.js::get", "res.sendFile"],
        patched_falsification_nodes=["server/routes/assets.js::get", "path.basename"],
    ),

    # ── CASE 7: Python Command Injection (CWE-78) ──────────────────────────────
    BenchmarkCase(
        case_id="PY-CVE-2023-7801",
        language="python",
        cwe="CWE-78",
        title="OS Command Injection in Network Utility",
        target_file="app/utils/network.py",
        description="Invoking shell=True with user-controlled host parameter.",
        vulnerable_diff="""--- a/app/utils/network.py
+++ b/app/utils/network.py
@@ -6,3 +6,3 @@
 def ping_host(host: str) -> str:
-    res = subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True, check=True)
+    res = subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
     return res
""",
        patched_diff="""--- a/app/utils/network.py
+++ b/app/utils/network.py
@@ -6,3 +6,3 @@
 def ping_host(host: str) -> str:
-    res = subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
+    res = subprocess.run(["ping", "-c", "1", host], capture_output=True, text=True, check=True)
     return res.stdout
""",
        caller_callee_context="""# app/api/diagnostics.py (Caller)
@router.post("/ping")
def ping_api(data: HostPayload):
    return {"result": ping_host(data.host)}
""",
        vulnerable_evidence_nodes=["app/utils/network.py::ping_host", "subprocess.check_output"],
        patched_falsification_nodes=["app/utils/network.py::ping_host", "subprocess.run:list_args"],
    ),

    # ── CASE 8: MERN Command Injection (CWE-78) ────────────────────────────────
    BenchmarkCase(
        case_id="JS-CVE-2023-7802",
        language="javascript",
        cwe="CWE-78",
        title="Command Injection via child_process.exec in Git Helper",
        target_file="lib/gitHelper.js",
        description="Unquoted branch argument passed into exec bash string.",
        vulnerable_diff="""--- a/lib/gitHelper.js
+++ b/lib/gitHelper.js
@@ -5,3 +5,3 @@
 exports.checkoutBranch = (branchName, callback) => {
-    execFile('git', ['checkout', branchName], callback);
+    exec(`git checkout ${branchName}`, callback);
 };
""",
        patched_diff="""--- a/lib/gitHelper.js
+++ b/lib/gitHelper.js
@@ -5,3 +5,3 @@
 exports.checkoutBranch = (branchName, callback) => {
-    exec(`git checkout ${branchName}`, callback);
+    execFile('git', ['checkout', branchName], callback);
 };
""",
        caller_callee_context="""// routes/deploy.js (Caller)
router.post('/deploy', (req, res) => {
    gitHelper.checkoutBranch(req.body.branch, (err) => {
        res.json({ status: err ? 'failed' : 'ok' });
    });
});
""",
        vulnerable_evidence_nodes=["lib/gitHelper.js::checkoutBranch", "child_process.exec"],
        patched_falsification_nodes=["lib/gitHelper.js::checkoutBranch", "child_process.execFile"],
    ),

    # ── CASE 9: Python Missing Access Guard (CWE-287) ──────────────────────────
    BenchmarkCase(
        case_id="PY-CVE-2023-2871",
        language="python",
        cwe="CWE-287",
        title="Missing Authorization Check on Tenant Deletion",
        target_file="app/api/tenants.py",
        description="Admin endpoint exposed without role requirement decorator.",
        vulnerable_diff="""--- a/app/api/tenants.py
+++ b/app/api/tenants.py
@@ -12,3 +12,2 @@
-@router.delete("/tenant/{tenant_id}")
-@require_role("superadmin")
+@router.delete("/tenant/{tenant_id}")
 async def delete_tenant(tenant_id: str, db=Depends(get_db)):
     return await db.tenants.delete(tenant_id)
""",
        patched_diff="""--- a/app/api/tenants.py
+++ b/app/api/tenants.py
@@ -12,2 +12,3 @@
 @router.delete("/tenant/{tenant_id}")
+@require_role("superadmin")
 async def delete_tenant(tenant_id: str, db=Depends(get_db)):
""",
        caller_callee_context="""# app/security/guards.py (Guard definition)
def require_role(role: str):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if not user or user.role != role:
                raise HTTPException(403, "Access Forbidden")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
""",
        vulnerable_evidence_nodes=["app/api/tenants.py::delete_tenant"],
        patched_falsification_nodes=["app/api/tenants.py::delete_tenant", "require_role"],
    ),

    # ── CASE 10: MERN Broken Object Level Authorization (CWE-287) ──────────────
    BenchmarkCase(
        case_id="JS-CVE-2023-2872",
        language="javascript",
        cwe="CWE-287",
        title="IDOR / Missing Ownership Guard on Document Update",
        target_file="src/controllers/docController.js",
        description="Updating document directly by ID without verifying document owner.",
        vulnerable_diff="""--- a/src/controllers/docController.js
+++ b/src/controllers/docController.js
@@ -8,3 +8,3 @@
 exports.updateDocument = async (req, res) => {
-    const doc = await Document.findOneAndUpdate({ _id: req.params.id, ownerId: req.user.id }, req.body);
+    const doc = await Document.findByIdAndUpdate(req.params.id, req.body);
     res.json(doc);
 };
""",
        patched_diff="""--- a/src/controllers/docController.js
+++ b/src/controllers/docController.js
@@ -8,3 +8,3 @@
 exports.updateDocument = async (req, res) => {
-    const doc = await Document.findByIdAndUpdate(req.params.id, req.body);
+    const doc = await Document.findOneAndUpdate({ _id: req.params.id, ownerId: req.user.id }, req.body);
     if (!doc) return res.status(404).json({ error: "Document not found or forbidden" });
     res.json(doc);
 };
""",
        caller_callee_context="""// src/routes/docRoutes.js (Caller)
router.put('/docs/:id', authenticateToken, docController.updateDocument);
""",
        vulnerable_evidence_nodes=["src/controllers/docController.js::updateDocument", "Document.findByIdAndUpdate"],
        patched_falsification_nodes=["src/controllers/docController.js::updateDocument", "ownerId: req.user.id"],
    ),
]
