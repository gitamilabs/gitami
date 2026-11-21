import hashlib
import hmac
import time
from typing import Set

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import settings

INTERNAL_AUTH_HEADER = "X-Gitami-Internal-Auth"
DEFAULT_MAX_DRIFT_MS = 60_000
DEFAULT_WHITELIST_PATHS: frozenset[str] = frozenset({
    "/api/health",
    "/health",
    "/docs",
    "/openapi.json",
})


def sign_internal_token(
    secret: str | None = None,
    timestamp_ms: int | None = None,
) -> str:
    """
    Signs an internal service token formatted as `<timestamp>.<signature>` using HMAC-SHA256.

    Args:
        secret: Optional secret key. Defaults to settings.internal_api_secret.
        timestamp_ms: Optional timestamp in milliseconds. Defaults to current Unix time.

    Returns:
        Token string `<timestamp>.<signature>`.
    """
    effective_secret = secret if secret is not None else settings.internal_api_secret
    effective_ts = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    ts_str = str(effective_ts)

    signature = hmac.new(
        effective_secret.encode("utf-8"),
        ts_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{ts_str}.{signature}"


def verify_internal_token(
    token: str,
    secret: str | None = None,
    max_drift_ms: int = DEFAULT_MAX_DRIFT_MS,
    current_time_ms: int | None = None,
) -> tuple[bool, str | None]:
    """
    Verifies an internal service token against the internal API secret and checks
    for timestamp drift (replay protection).

    Args:
        token: The `<timestamp>.<signature>` token string.
        secret: Optional secret key override. Defaults to settings.internal_api_secret.
        max_drift_ms: Maximum allowable timestamp drift in milliseconds.
        current_time_ms: Optional current time in milliseconds override (useful for testing).

    Returns:
        (True, None) if the token is valid, or (False, reason) if verification fails.
    """
    if not token or not isinstance(token, str) or not token.strip():
        return False, "Missing or invalid internal authentication token"

    token = token.strip()
    parts = token.split(".")
    if len(parts) != 2:
        return False, "Malformed token format: expected <timestamp>.<signature>"

    timestamp_str, provided_sig = parts[0], parts[1]
    if not timestamp_str or not provided_sig:
        return False, "Malformed token format: expected <timestamp>.<signature>"

    try:
        timestamp_num = int(timestamp_str)
    except ValueError:
        return False, "Invalid timestamp in token: expected integer milliseconds"

    if str(timestamp_num) != timestamp_str or timestamp_num <= 0:
        return False, "Invalid timestamp in token"

    now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
    drift = abs(now_ms - timestamp_num)
    if drift > max_drift_ms:
        return False, f"Token expired: drift of {drift}ms exceeds limit of {max_drift_ms}ms"

    if len(provided_sig) != 64 or not all(c in "0123456789abcdefABCDEF" for c in provided_sig):
        return False, "Invalid signature format: expected 64-character hexadecimal digest"

    effective_secret = secret if secret is not None else settings.internal_api_secret
    expected_sig = hmac.new(
        effective_secret.encode("utf-8"),
        timestamp_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_sig.lower(), expected_sig.lower()):
        return False, "Invalid internal service signature"

    return True, None


class InternalServiceAuthMiddleware:
    """
    ASGI middleware that validates the `X-Gitami-Internal-Auth` header on incoming requests.
    Rejects unsigned, expired (> 60s drift), or invalid HMAC-SHA256 signatures with HTTP 401 Unauthorized.
    Operational endpoints (/api/health, /health, /docs, /openapi.json) and OPTIONS requests bypass authentication.
    """

    def __init__(
        self,
        app: ASGIApp,
        secret: str | None = None,
        whitelist_paths: Set[str] | frozenset[str] | None = None,
        max_drift_ms: int = DEFAULT_MAX_DRIFT_MS,
    ):
        self.app = app
        self.secret = secret
        self.whitelist_paths = (
            set(whitelist_paths)
            if whitelist_paths is not None
            else set(DEFAULT_WHITELIST_PATHS)
        )
        self.max_drift_ms = max_drift_ms

    def _is_whitelisted(self, path: str) -> bool:
        norm_path = path.rstrip("/") if path != "/" else "/"
        if norm_path in self.whitelist_paths or path in self.whitelist_paths:
            return True
        if path == "/docs" or path.startswith("/docs/"):
            return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_whitelisted(path):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_header = headers.get(INTERNAL_AUTH_HEADER)

        if not auth_header:
            response = JSONResponse(
                status_code=401,
                content={"detail": "Missing internal authentication header (X-Gitami-Internal-Auth)"},
            )
            await response(scope, receive, send)
            return

        valid, reason = verify_internal_token(
            auth_header,
            secret=self.secret,
            max_drift_ms=self.max_drift_ms,
        )

        if not valid:
            response = JSONResponse(
                status_code=401,
                content={"detail": f"Unauthorized: {reason}"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
