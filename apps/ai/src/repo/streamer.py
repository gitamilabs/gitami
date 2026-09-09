import io
import tarfile
import urllib.request
import urllib.error
from typing import List, Optional, Set
from src.parsing.models import ParseResult
from src.parsing.parser import CodeParser

IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".next",
    "out",
    "coverage",
    ".idea",
    ".vscode",
}

IGNORED_EXTENSIONS: Set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
    ".zip",
    ".tar",
    ".gz",
    ".pdf",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
}


def stream_and_parse_github_repo(
    full_name: str,
    token: Optional[str] = None,
    branch: str = "main",
    parser: Optional[CodeParser] = None,
) -> List[ParseResult]:
    """
    Streams a repository tarball from GitHub directly into memory (0 local disk writes),
    decompresses files in-memory, and parses them with Tree-sitter AST parser.
    """
    url = f"https://api.github.com/repos/{full_name}/tarball/{branch}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Sentinel-AI-Service",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            tar_bytes = response.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub Tarball API failed with status {e.code}: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch repository archive: {str(e)}")

    if parser is None:
        parser = CodeParser()

    parse_results: List[ParseResult] = []

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            # GitHub tarballs prefix files with '{owner}-{repo}-{commit_sha}/'
            parts = member.name.split("/")
            if len(parts) <= 1:
                continue

            # Normalized relative path inside the repo
            rel_path = "/".join(parts[1:])

            # Skip ignored directories
            if any(part in IGNORED_DIRECTORIES for part in parts[1:]):
                continue

            # Skip binary / non-code extensions
            dot_idx = rel_path.rfind(".")
            if dot_idx != -1:
                ext = rel_path[dot_idx:].lower()
                if ext in IGNORED_EXTENSIONS:
                    continue

            # Extract file bytes directly from in-memory tarball
            f = tar.extractfile(member)
            if f is None:
                continue

            code_bytes = f.read()

            # Skip very large files (> 1MB)
            if len(code_bytes) > 1024 * 1024:
                continue

            res = parser.parse_code_bytes(code_bytes, rel_path)
            if res:
                parse_results.append(res)

    return parse_results
