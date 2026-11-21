import hashlib
import hmac
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import settings
from src.web.app import app
from src.web.middleware.internal_auth import (
    INTERNAL_AUTH_HEADER,
    DEFAULT_MAX_DRIFT_MS,
    DEFAULT_WHITELIST_PATHS,
    InternalServiceAuthMiddleware,
    sign_internal_token,
    verify_internal_token,
)


# =============================================================================
# 1. Configuration & Token Signing / Verification Helper Unit Tests
# =============================================================================

def test_config_defines_internal_api_secret():
    """Verify that settings defines internal_api_secret with the expected fallback."""
    assert hasattr(settings, "internal_api_secret")
    assert settings.internal_api_secret == "gitami_dev_internal_api_secret_default_32bytes"


def test_sign_internal_token_format_and_reproducibility():
    """Verify sign_internal_token produces <timestamp>.<signatureHex> using HMAC-SHA256."""
    fixed_ts = 1700000000000
    secret = "custom_test_secret"
    token = sign_internal_token(secret=secret, timestamp_ms=fixed_ts)

    parts = token.split(".")
    assert len(parts) == 2
    ts_part, sig_part = parts
    assert ts_part == str(fixed_ts)
    assert len(sig_part) == 64

    # Calculate expected HMAC independently
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        str(fixed_ts).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert sig_part == expected_sig


def test_verify_internal_token_valid():
    """Verify a freshly signed token passes verification."""
    token = sign_internal_token()
    valid, reason = verify_internal_token(token)
    assert valid is True
    assert reason is None


def test_verify_internal_token_missing_or_empty():
    """Verify missing, empty, or non-string tokens fail verification."""
    for bad in ["", "   ", None, 12345]:
        valid, reason = verify_internal_token(bad)  # type: ignore
        assert valid is False
        assert "missing" in reason.lower() or "invalid" in reason.lower()


def test_verify_internal_token_malformed_structure():
    """Verify tokens without exactly one dot or missing segments fail verification."""
    malformed_tokens = [
        "nodottoken",
        "too.many.dots.here",
        ".onlysignature",
        "1700000000000.",
        "notanumber.64charshere",
    ]
    for token in malformed_tokens:
        valid, reason = verify_internal_token(token)
        assert valid is False
        assert reason is not None


def test_verify_internal_token_invalid_signature_format():
    """Verify signatures that are not 64-char hex strings fail verification."""
    valid, reason = verify_internal_token(f"{int(time.time() * 1000)}.nothex!")
    assert valid is False
    assert "signature" in reason.lower()


def test_verify_internal_token_drift_expired_past():
    """Verify tokens older than 60,000ms are rejected due to replay protection."""
    now_ms = 1700000000000
    expired_ts = now_ms - 60001  # 60.001s in the past
    token = sign_internal_token(timestamp_ms=expired_ts)

    valid, reason = verify_internal_token(token, current_time_ms=now_ms)
    assert valid is False
    assert "expired" in reason.lower() or "drift" in reason.lower()


def test_verify_internal_token_drift_future():
    """Verify tokens from more than 60,000ms in the future are rejected."""
    now_ms = 1700000000000
    future_ts = now_ms + 60001  # 60.001s in the future
    token = sign_internal_token(timestamp_ms=future_ts)

    valid, reason = verify_internal_token(token, current_time_ms=now_ms)
    assert valid is False
    assert "expired" in reason.lower() or "drift" in reason.lower()


def test_verify_internal_token_drift_boundary():
    """Verify tokens within the 60,000ms window are accepted."""
    now_ms = 1700000000000
    valid_past_ts = now_ms - 59000  # 59s in past
    token = sign_internal_token(timestamp_ms=valid_past_ts)

    valid, reason = verify_internal_token(token, current_time_ms=now_ms)
    assert valid is True
    assert reason is None


def test_verify_internal_token_tampered_signature():
    """Verify tampered HMAC signature fails verification."""
    now_ms = int(time.time() * 1000)
    token = sign_internal_token(timestamp_ms=now_ms)
    ts, sig = token.split(".")
    tampered_sig = "0" * 64 if sig != "0" * 64 else "1" * 64
    tampered_token = f"{ts}.{tampered_sig}"

    valid, reason = verify_internal_token(tampered_token)
    assert valid is False
    assert "signature" in reason.lower()


def test_verify_internal_token_different_secret():
    """Verify token signed with secret A fails verification against secret B."""
    token = sign_internal_token(secret="secret_a")
    valid, reason = verify_internal_token(token, secret="secret_b")
    assert valid is False
    assert "signature" in reason.lower()


# =============================================================================
# 2. FastAPI Middleware HTTP Acceptance Criteria (using FastAPI TestClient)
# =============================================================================

@pytest.fixture
def auth_test_client():
    """Isolated TestClient for the primary FastAPI app."""
    return TestClient(app)


def test_whitelisted_endpoints_allow_unauthenticated(auth_test_client):
    """Verify whitelisted endpoints (/api/health, /health, /docs, /openapi.json) are open."""
    # 1. /api/health
    res_api_health = auth_test_client.get("/api/health")
    assert res_api_health.status_code == 200
    assert res_api_health.json()["status"] == "ok"

    # 2. /health
    res_health = auth_test_client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # 3. /docs
    res_docs = auth_test_client.get("/docs")
    assert res_docs.status_code == 200

    # 4. /openapi.json
    res_openapi = auth_test_client.get("/openapi.json")
    assert res_openapi.status_code == 200
    assert "openapi" in res_openapi.json()


def test_non_whitelisted_path_prefixed_docs_rejected(auth_test_client):
    """Verify paths that share a prefix with /docs (e.g. /docs-private) are NOT whitelisted."""
    response = auth_test_client.get("/docs-private")
    assert response.status_code == 401


def test_protected_endpoint_rejects_missing_header(auth_test_client):
    """Non-whitelisted endpoints without X-Gitami-Internal-Auth return 401 Unauthorized."""
    response = auth_test_client.get("/api/config")
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "missing" in data["detail"].lower() or "unauthorized" in data["detail"].lower()


def test_protected_endpoint_rejects_malformed_header(auth_test_client):
    """Non-whitelisted endpoints with malformed tokens return 401 Unauthorized."""
    response = auth_test_client.get(
        "/api/config",
        headers={INTERNAL_AUTH_HEADER: "invalid_token_without_period"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_protected_endpoint_rejects_expired_timestamp_drift(auth_test_client):
    """Requests with timestamp drift > 60,000ms return 401 Unauthorized."""
    expired_ts = int(time.time() * 1000) - 75000  # 75s in the past
    token = sign_internal_token(timestamp_ms=expired_ts)

    response = auth_test_client.get(
        "/api/config",
        headers={INTERNAL_AUTH_HEADER: token},
    )
    assert response.status_code == 401
    data = response.json()
    assert "expired" in data["detail"].lower() or "drift" in data["detail"].lower()


def test_protected_endpoint_rejects_future_timestamp_drift(auth_test_client):
    """Requests with timestamp drift > 60,000ms into the future return 401 Unauthorized."""
    future_ts = int(time.time() * 1000) + 75000  # 75s into future
    token = sign_internal_token(timestamp_ms=future_ts)

    response = auth_test_client.get(
        "/api/config",
        headers={INTERNAL_AUTH_HEADER: token},
    )
    assert response.status_code == 401
    data = response.json()
    assert "expired" in data["detail"].lower() or "drift" in data["detail"].lower()


def test_protected_endpoint_rejects_invalid_signature(auth_test_client):
    """Requests with incorrect HMAC signature return 401 Unauthorized."""
    now_ms = int(time.time() * 1000)
    fake_sig = "a" * 64
    token = f"{now_ms}.{fake_sig}"

    response = auth_test_client.get(
        "/api/config",
        headers={INTERNAL_AUTH_HEADER: token},
    )
    assert response.status_code == 401
    data = response.json()
    assert "signature" in data["detail"].lower() or "unauthorized" in data["detail"].lower()


def test_protected_endpoint_accepts_valid_internal_token(auth_test_client):
    """Requests with valid X-Gitami-Internal-Auth token return 200 OK."""
    valid_token = sign_internal_token()

    response = auth_test_client.get(
        "/api/config",
        headers={INTERNAL_AUTH_HEADER: valid_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "vector_db" in data
    assert "models" in data


def test_middleware_options_preflight_allowed(auth_test_client):
    """OPTIONS preflight requests to protected paths should bypass auth check."""
    response = auth_test_client.options(
        "/api/config",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code != 401


def test_middleware_custom_secret_isolated_app():
    """Verify middleware can be initialized with custom secret and custom whitelist."""
    custom_app = FastAPI()
    custom_secret = "isolated_test_secret_for_middleware_32b"

    custom_app.add_middleware(
        InternalServiceAuthMiddleware,
        secret=custom_secret,
        whitelist_paths={"/custom/open"},
    )

    @custom_app.get("/custom/open")
    def open_route():
        return {"open": True}

    @custom_app.get("/custom/secure")
    def secure_route():
        return {"secure": True}

    client = TestClient(custom_app)

    # Open route passes
    res_open = client.get("/custom/open")
    assert res_open.status_code == 200

    # Secure route fails without auth
    res_unauth = client.get("/custom/secure")
    assert res_unauth.status_code == 401

    # Secure route fails with default secret token
    token_wrong = sign_internal_token(secret="wrong_secret")
    res_wrong = client.get("/custom/secure", headers={INTERNAL_AUTH_HEADER: token_wrong})
    assert res_wrong.status_code == 401

    # Secure route succeeds with custom secret token
    token_right = sign_internal_token(secret=custom_secret)
    res_right = client.get("/custom/secure", headers={INTERNAL_AUTH_HEADER: token_right})
    assert res_right.status_code == 200
    assert res_right.json() == {"secure": True}
