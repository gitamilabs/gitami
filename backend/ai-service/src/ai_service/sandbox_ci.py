"""
sandbox_ci.py

CI-style "does it build and pass tests" check, run in an ephemeral Docker
container. Designed to sit alongside the existing RAG/graph review pipeline
in the AI Service: its output (pass/fail, logs, failing test names) gets
merged into the final PR review payload sent back to the API Service.

Usage (async, e.g. from a background task or job queue worker):

    result = await run_ci_check(
        repo_url="https://github.com/org/repo.git",
        ref="refs/pull/123/head",   # or a commit SHA / branch name
        repo_root_files=["package.json", "index.js"],
        timeout_seconds=300,
    )

Requires: pip install docker
Requires: Docker connection configured via environment variables 
(DOCKER_HOST, DOCKER_TLS_VERIFY, DOCKER_CERT_PATH) or local daemon.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import shlex
import time
import uuid
from enum import Enum
from typing import Optional

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

logger = logging.getLogger("sandbox_ci")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Base images per detected project type. Build your own hardened variants
# (non-root user, pinned versions, common tools pre-installed) rather than
# using these directly in production — this is a starting point.
LANGUAGE_IMAGES = {
    "node": "node:20-slim",
    "python": "python:3.11-slim",
    "go": "golang:1.22-alpine",
    "rust": "rust:1.78-slim",
    "java": "maven:3.9-eclipse-temurin-21",
}

CONTAINER_RESOURCE_LIMITS = dict(
    mem_limit="1g",
    memswap_limit="1g",       # prevents unbounded swap usage
    cpu_quota=100000,          # 1 CPU (period defaults to 100000)
    pids_limit=256,
    network_mode="bridge",     # consider "none" once deps are vendored/cached
    security_opt=["no-new-privileges"],
    cap_drop=["ALL"],
)


class CIStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BUILD_ERROR = "build_error"
    TIMEOUT = "timeout"
    INFRA_ERROR = "infra_error"
    UNSUPPORTED = "unsupported"


@dataclasses.dataclass
class CIResult:
    status: CIStatus
    project_type: Optional[str]
    exit_code: Optional[int]
    duration_seconds: float
    logs: str
    failing_tests: list[str] = dataclasses.field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Project type detection + command selection
# ---------------------------------------------------------------------------

# Each entry: (marker files to look for, language key, install cmd, test cmd)
DETECTION_RULES = [
    (["package.json"], "node", "npm ci || npm install", "npm test --if-present"),
    (["pyproject.toml"], "python", "pip install -e . || pip install -r requirements.txt || true", "pytest -q"),
    (["requirements.txt"], "python", "pip install -r requirements.txt", "pytest -q"),
    (["go.mod"], "go", "go mod download", "go test ./..."),
    (["Cargo.toml"], "rust", "cargo fetch", "cargo test --quiet"),
    (["pom.xml"], "java", "mvn -q -DskipTests install", "mvn -q test"),
]


def _build_clone_and_run_script(repo_url: str, ref: str, install_cmd: str, test_cmd: str) -> str:
    """
    Shell script executed as the container's entrypoint: clone at the given
    ref, install deps, run tests. Runs as a single shell so we get one clean
    exit code and combined stdout/stderr stream.
    """
    # ref can be a branch, tag, SHA, or "refs/pull/N/head" for a PR ref.
    return f"""
set -o pipefail
git clone --quiet {shlex.quote(repo_url)} /workspace
cd /workspace
git fetch --quiet origin {shlex.quote(ref)}:ci_target
git checkout --quiet ci_target
echo "--- INSTALL ---"
{install_cmd}
echo "--- TEST ---"
{test_cmd}
""".strip()


def detect_project_type(repo_file_list: list[str]) -> Optional[tuple[str, str, str]]:
    """
    repo_file_list: filenames present at the repo root (fetch this cheaply
    via the GitHub API contents endpoint before spinning up a container --
    no need to clone twice).
    Returns (language, install_cmd, test_cmd) or None if nothing matched.
    """
    for markers, lang, install_cmd, test_cmd in DETECTION_RULES:
        if any(m in repo_file_list for m in markers):
            return lang, install_cmd, test_cmd
    return None


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

async def run_ci_check(
    repo_url: str,
    ref: str,
    repo_root_files: Optional[list[str]] = None,
    timeout_seconds: int = 300,
) -> CIResult:
    """
    Runs the build/test check in a fresh, disposable container.
    Blocking Docker SDK calls are pushed to a thread so this stays
    awaitable from FastAPI route handlers / background tasks.
    """
    detection = detect_project_type(repo_root_files or [])
    if detection is None:
        return CIResult(
            status=CIStatus.UNSUPPORTED,
            project_type=None,
            exit_code=None,
            duration_seconds=0.0,
            logs="",
            error="Could not detect a supported project type from repo root files.",
        )

    lang, install_cmd, test_cmd = detection
    image = LANGUAGE_IMAGES[lang]
    script = _build_clone_and_run_script(repo_url, ref, install_cmd, test_cmd)

    return await asyncio.to_thread(
        _run_in_container, image, script, lang, timeout_seconds
    )


def _run_in_container(image: str, script: str, lang: str, timeout_seconds: int) -> CIResult:
    # Uses standard docker environment variables (DOCKER_HOST, DOCKER_TLS_VERIFY, etc.)
    client = docker.from_env()
    container_name = f"ci-check-{uuid.uuid4().hex[:12]}"
    start = time.monotonic()
    container = None

    try:
        container = client.containers.run(
            image=image,
            command=["sh", "-c", script],
            name=container_name,
            detach=True,
            **CONTAINER_RESOURCE_LIMITS,
        )

        try:
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", -1)
            timed_out = False
        except Exception:
            # container.wait() raises on client-side timeout; the container
            # itself keeps running until we kill it below.
            timed_out = True
            exit_code = None

        logs = container.logs(stdout=True, stderr=True, tail=2000).decode(
            "utf-8", errors="replace"
        )
        duration = time.monotonic() - start

        if timed_out:
            return CIResult(
                status=CIStatus.TIMEOUT,
                project_type=lang,
                exit_code=None,
                duration_seconds=duration,
                logs=logs,
                error=f"Exceeded {timeout_seconds}s timeout.",
            )

        status = CIStatus.PASSED if exit_code == 0 else CIStatus.FAILED
        return CIResult(
            status=status,
            project_type=lang,
            exit_code=exit_code,
            duration_seconds=duration,
            logs=logs,
            failing_tests=_extract_failing_tests(logs, lang),
        )

    except (ContainerError, ImageNotFound, APIError) as e:
        return CIResult(
            status=CIStatus.INFRA_ERROR,
            project_type=lang,
            exit_code=None,
            duration_seconds=time.monotonic() - start,
            logs="",
            error=str(e),
        )
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                logger.warning("Failed to remove container %s", container_name)


def _extract_failing_tests(logs: str, lang: str) -> list[str]:
    """
    Best-effort parse of common test runner output to surface which tests
    failed. This is intentionally simple pattern matching -- swap in real
    JUnit-XML / pytest --tb / go test -json parsing for production use.
    """
    failing = []
    if lang == "python":
        failing = [
            line.split("::")[0].strip() + "::" + line.split("::")[1].split(" ")[0]
            for line in logs.splitlines()
            if line.startswith("FAILED ")
        ]
    elif lang == "node":
        failing = [
            line.strip().lstrip("✕✗x ").strip()
            for line in logs.splitlines()
            if line.strip().startswith(("✕", "✗", "  ✖"))
        ]
    elif lang == "go":
        failing = [
            line.split()[1]
            for line in logs.splitlines()
            if line.strip().startswith("--- FAIL:")
        ]
    return failing
