import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from src.web.middleware.internal_auth import (
    INTERNAL_AUTH_HEADER,
    sign_internal_token,
)


def _ensure_internal_auth_header(kwargs: dict) -> None:
    """Injects a valid internal auth header into kwargs if not already specified."""
    headers = kwargs.get("headers")
    if headers is None:
        kwargs["headers"] = {INTERNAL_AUTH_HEADER: sign_internal_token()}
    elif isinstance(headers, dict):
        has_auth = any(k.lower() == INTERNAL_AUTH_HEADER.lower() for k in headers.keys())
        if not has_auth:
            kwargs["headers"] = {**headers, INTERNAL_AUTH_HEADER: sign_internal_token()}


@pytest.fixture(autouse=True)
def auto_internal_auth_for_legacy_tests(request, monkeypatch):
    """
    Automatically injects a valid X-Gitami-Internal-Auth header for all existing
    test suites simulating internal gateway traffic, while allowing
    test_internal_auth_middleware to exercise unauthenticated or malformed requests directly.
    """
    if "test_internal_auth_middleware" in request.node.nodeid:
        return

    # Patch TestClient (sync HTTP tests)
    orig_sync_request = TestClient.request

    def authenticated_sync_request(self, method, url, *args, **kwargs):
        _ensure_internal_auth_header(kwargs)
        return orig_sync_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(TestClient, "request", authenticated_sync_request)

    # Patch AsyncClient (async streaming HTTP tests)
    orig_async_request = AsyncClient.request

    async def authenticated_async_request(self, method, url, *args, **kwargs):
        _ensure_internal_auth_header(kwargs)
        return await orig_async_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "request", authenticated_async_request)
