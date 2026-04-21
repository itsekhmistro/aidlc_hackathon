"""Unit tests for backend/app/core/xmpp.py — the FastAPI→Prosody bridge.

We patch httpx at import-time inside the module so each test captures the
call + returns a deterministic response. We never hit a real Prosody here.

Bridge invariant: no call should ever raise out of the three public
wrappers, and XMPP_ENABLED=False must short-circuit them entirely. Tests
cover both paths.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.core import xmpp as xmpp_mod


class _FakeAsyncClient:
    """Minimal stand-in for httpx.AsyncClient.

    The bridge uses `async with httpx.AsyncClient(...) as c: c.post(...)`,
    so we implement the context manager protocol plus a post(). The
    factory captures every call into `calls` for assertions.
    """

    def __init__(self, *_, **__):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def _install_fake_httpx(monkeypatch, *, status_code: int = 200, raise_exc: Exception | None = None):
    calls: list[dict] = []

    class _Client(_FakeAsyncClient):
        async def post(self, url, json=None, headers=None):
            calls.append({"url": url, "json": json, "headers": headers})
            if raise_exc is not None:
                raise raise_exc
            return SimpleNamespace(status_code=status_code, text="")

    monkeypatch.setattr(xmpp_mod.httpx, "AsyncClient", _Client)
    return calls


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


@pytest.fixture(autouse=True)
def _enable_xmpp(monkeypatch):
    monkeypatch.setattr(xmpp_mod.settings, "XMPP_ENABLED", True)
    monkeypatch.setattr(xmpp_mod.settings, "XMPP_HOST", "prosody-test")
    monkeypatch.setattr(xmpp_mod.settings, "XMPP_HTTP_PORT", 5280)
    monkeypatch.setattr(xmpp_mod.settings, "XMPP_ADMIN_TOKEN", "test-token")


def test_provision_calls_create_user_with_bearer(monkeypatch):
    calls = _install_fake_httpx(monkeypatch, status_code=201)
    assert _run(xmpp_mod.provision_xmpp_user("alice", "s3cret")) is True
    assert len(calls) == 1
    c = calls[0]
    assert c["url"] == "http://prosody-test:5280/admin/create_user"
    assert c["json"] == {"username": "alice", "password": "s3cret"}
    assert c["headers"]["Authorization"] == "Bearer test-token"


def test_change_password_hits_dedicated_endpoint(monkeypatch):
    calls = _install_fake_httpx(monkeypatch, status_code=200)
    assert _run(xmpp_mod.change_xmpp_password("alice", "new-pw")) is True
    assert calls[0]["url"].endswith("/admin/change_user_password")
    assert calls[0]["json"] == {"username": "alice", "password": "new-pw"}


def test_disable_calls_delete_user(monkeypatch):
    calls = _install_fake_httpx(monkeypatch, status_code=204)
    assert _run(xmpp_mod.disable_xmpp_user("alice")) is True
    assert calls[0]["url"].endswith("/admin/delete_user")
    assert calls[0]["json"] == {"username": "alice"}


def test_xmpp_disabled_short_circuits(monkeypatch):
    monkeypatch.setattr(xmpp_mod.settings, "XMPP_ENABLED", False)
    calls = _install_fake_httpx(monkeypatch, status_code=500)  # would fail if we reached it
    assert _run(xmpp_mod.provision_xmpp_user("x", "y")) is True
    assert _run(xmpp_mod.change_xmpp_password("x", "y")) is True
    assert _run(xmpp_mod.disable_xmpp_user("x")) is True
    assert calls == []


def test_transport_error_never_raises(monkeypatch):
    _install_fake_httpx(monkeypatch, raise_exc=httpx.ConnectError("boom"))
    # All three return False, no exception propagates.
    assert _run(xmpp_mod.provision_xmpp_user("a", "b")) is False
    assert _run(xmpp_mod.change_xmpp_password("a", "b")) is False
    assert _run(xmpp_mod.disable_xmpp_user("a")) is False


def test_5xx_returns_false_without_raising(monkeypatch):
    _install_fake_httpx(monkeypatch, status_code=502)
    assert _run(xmpp_mod.provision_xmpp_user("a", "b")) is False


def test_401_returns_false_without_raising(monkeypatch):
    # Admin-token misconfig — logs ERROR, still no raise, still False.
    _install_fake_httpx(monkeypatch, status_code=401)
    assert _run(xmpp_mod.provision_xmpp_user("a", "b")) is False
