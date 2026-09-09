import logging
import urllib.request
import urllib.error
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from ai_service.config import settings

logger = logging.getLogger(__name__)


class JoernClient:
    """
    Client for interacting with the Joern CPG (Code Property Graph) Server.
    Communicates via CPGQL over HTTP / cpgqls-client, with static AST heuristics fallback
    when the Joern container is unavailable.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        auth_user: Optional[str] = None,
        auth_password: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.url = (url or getattr(settings, "joern_url", "http://localhost:8088")).rstrip("/")
        self.auth_user = auth_user or getattr(settings, "joern_auth_user", "admin")
        self.auth_password = auth_password or getattr(settings, "joern_auth_password", "admin")
        self.timeout = timeout or getattr(settings, "joern_timeout", 30)
        self._cpgqls_client = None

    def _get_cpgqls_client(self):
        if self._cpgqls_client is None:
            try:
                from cpgqls_client import CPGQLSClient
                auth = (self.auth_user, self.auth_password) if self.auth_user else None
                # Host/port extraction
                endpoint = self.url.replace("http://", "").replace("https://", "")
                self._cpgqls_client = CPGQLSClient(endpoint, auth_credentials=auth)
            except Exception as e:
                logger.debug(f"cpgqls-client init error: {e}")
                self._cpgqls_client = None
        return self._cpgqls_client

    def is_available(self) -> bool:
        """Check if Joern HTTP server is running and reachable."""
        try:
            req = urllib.request.Request(f"{self.url}/query-sync", headers={"Content-Type": "application/json"})
            # Sending a light ping query
            data = json.dumps({"query": "cpg.metaData.version.l"}).encode("utf-8")
            with urllib.request.urlopen(req, data=data, timeout=3) as resp:
                return resp.status in (200, 400)
        except Exception:
            return False

    def execute_cpgql(self, query: str) -> Dict[str, Any]:
        """Execute a raw CPGQL query against Joern."""
        if not self.is_available():
            return {
                "success": False,
                "stdout": "",
                "stderr": "Joern server is not running or unreachable",
                "engine": "offline",
            }

        client = self._get_cpgqls_client()
        if client:
            try:
                res = client.execute(query)
                return {
                    "success": True,
                    "stdout": res.get("stdout", ""),
                    "stderr": res.get("stderr", ""),
                    "engine": "joern_cpgqls",
                }
            except Exception as e:
                logger.debug(f"CPGQL execution error via client: {e}")

        # HTTP Fallback direct query
        try:
            req = urllib.request.Request(
                f"{self.url}/query-sync",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"query": query}).encode("utf-8"),
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return {
                    "success": True,
                    "stdout": body,
                    "stderr": "",
                    "engine": "joern_http",
                }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "engine": "offline",
            }

    def import_code(self, repo_path: str, project_name: str) -> Dict[str, Any]:
        """Import repository into Joern CPG database."""
        # Convert path to posix for Joern docker container
        clean_path = Path(repo_path).as_posix()
        cpgql = f'importCode("{clean_path}", "{project_name}")'
        res = self.execute_cpgql(cpgql)
        if not res["success"]:
            logger.info(f"Joern import_code offline: will use AST/Neo4j fallback for {project_name}")
        return res

    def check_dataflow(
        self,
        source_pattern: str,
        sink_pattern: str,
        repo_path: Optional[str] = None,
        repo_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Check if tainted data flows from source to sink across procedural boundaries.
        Example: source='req.body', sink='query' or 'execute'.
        """
        # 1. Try Joern CPGQL query if available
        cpgql = (
            f'def src = cpg.call.name(".*{source_pattern}.*"); '
            f'def snk = cpg.call.name(".*{sink_pattern}.*"); '
            f'snk.reachableByFlows(src).p'
        )
        res = self.execute_cpgql(cpgql)

        if res["success"] and res["stdout"]:
            stdout = res["stdout"].strip()
            reachable = "List(" in stdout and len(stdout) > 10 and "List()" not in stdout
            return {
                "reachable": reachable,
                "source": source_pattern,
                "sink": sink_pattern,
                "engine": res["engine"],
                "flow_traces": [stdout] if reachable else [],
                "sanitized": not reachable,
            }

        # 2. Heuristic static fallback (when Joern container is offline)
        return self._heuristic_dataflow_check(source_pattern, sink_pattern, repo_path or repo_id)

    def get_reachable_guards(
        self,
        symbol_name: str,
        repo_path: Optional[str] = None,
        repo_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Check control-flow guards (e.g. if/else conditions) that control execution of symbol_name.
        Used for the Falsification Protocol: verifying whether a check/sanitizer actually wraps the sink.
        """
        cpgql = f'cpg.call.name(".*{symbol_name}.*").controlledBy.code.l'
        res = self.execute_cpgql(cpgql)

        if res["success"] and res["stdout"]:
            raw = res["stdout"].strip()
            guards = []
            if "List(" in raw:
                # Parse list elements
                matches = re.findall(r'"([^"]*)"', raw)
                guards = matches if matches else [raw]
            return {
                "symbol": symbol_name,
                "guarded": len(guards) > 0,
                "guards": guards,
                "engine": res["engine"],
            }

        # Heuristic static fallback
        return self._heuristic_guards_check(symbol_name, repo_path or repo_id)

    def get_callers_with_args(
        self,
        symbol_name: str,
        repo_path: Optional[str] = None,
        repo_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Retrieve callers of symbol_name along with the arguments passed at call sites.
        """
        cpgql = (
            f'cpg.call.name(".*{symbol_name}.*")'
            f'.map(c => s"${{c.method.name}} -> ${{c.argument.code.l}}").l'
        )
        res = self.execute_cpgql(cpgql)

        if res["success"] and res["stdout"]:
            return {
                "symbol": symbol_name,
                "callers_with_args": res["stdout"],
                "engine": res["engine"],
            }

        return self._heuristic_callers_with_args(symbol_name, repo_path or repo_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Static AST Heuristic Fallbacks (Active when Docker Joern container is offline)
    # ──────────────────────────────────────────────────────────────────────────

    def _heuristic_dataflow_check(
        self,
        source_pattern: str,
        sink_pattern: str,
        repo_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Heuristic check looking for source and sink patterns in local repository files."""
        if not repo_path or not Path(repo_path).exists():
            return {
                "reachable": False,
                "source": source_pattern,
                "sink": sink_pattern,
                "engine": "static_heuristic",
                "flow_traces": [],
                "sanitized": True,
                "note": "Joern server offline; no local repo path provided for heuristic scan",
            }

        detected_flows = []
        is_reachable = False
        is_sanitized = False

        sanitizer_keywords = ["sanitize", "escape", "clean", "validate", "check", "param", "prepared", "dompurify", "basename"]

        for file_path in Path(repo_path).rglob("*"):
            if file_path.is_file() and file_path.suffix in (".py", ".js", ".ts", ".jsx", ".tsx"):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if source_pattern.lower() in content.lower() and sink_pattern.lower() in content.lower():
                        # Check if a sanitizer keyword also appears
                        has_sanitizer = any(k in content.lower() for k in sanitizer_keywords)
                        if has_sanitizer:
                            is_sanitized = True
                        else:
                            is_reachable = True
                            detected_flows.append(f"{file_path.name}: {source_pattern} -> {sink_pattern} (no sanitizer detected)")
                except Exception:
                    continue

        return {
            "reachable": is_reachable,
            "source": source_pattern,
            "sink": sink_pattern,
            "engine": "static_heuristic",
            "flow_traces": detected_flows,
            "sanitized": is_sanitized and not is_reachable,
        }

    def _heuristic_guards_check(self, symbol_name: str, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Heuristic scan searching for if-conditions enclosing calls to symbol_name."""
        guards = []
        if repo_path and Path(repo_path).exists():
            for file_path in Path(repo_path).rglob("*"):
                if file_path.is_file() and file_path.suffix in (".py", ".js", ".ts"):
                    try:
                        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                        for i, line in enumerate(lines):
                            if symbol_name in line:
                                # Look backwards 5 lines for an if statement
                                for prev_idx in range(max(0, i - 5), i):
                                    prev_line = lines[prev_idx].strip()
                                    if prev_line.startswith(("if ", "if(", "elif ", "while ")):
                                        guards.append(f"{file_path.name}:{prev_idx+1} {prev_line}")
                    except Exception:
                        continue

        return {
            "symbol": symbol_name,
            "guarded": len(guards) > 0,
            "guards": guards,
            "engine": "static_heuristic",
        }

    def _heuristic_callers_with_args(self, symbol_name: str, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Heuristic search for call sites and passed arguments."""
        calls = []
        if repo_path and Path(repo_path).exists():
            pattern = re.compile(rf"{re.escape(symbol_name)}\((.*?)\)", re.DOTALL)
            for file_path in Path(repo_path).rglob("*"):
                if file_path.is_file() and file_path.suffix in (".py", ".js", ".ts"):
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                        for match in pattern.finditer(text):
                            calls.append(f"{file_path.name}: {symbol_name}({match.group(1).strip()})")
                    except Exception:
                        continue

        return {
            "symbol": symbol_name,
            "callers_with_args": calls,
            "engine": "static_heuristic",
        }


# Global singleton instance
joern_client = JoernClient()
