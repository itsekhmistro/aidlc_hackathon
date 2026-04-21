"""FastAPI → Prosody bridge (TASK-13).

Thin async wrappers around Prosody's ``mod_http_api`` admin endpoints.

Design invariant (specs/13-jabber-design.md §3.3): bridge failures MUST NOT
propagate to the caller. Registration, password change, and account delete
must all succeed in FastAPI even if Prosody is unreachable or misconfigured.
The functions swallow errors, log at WARNING/ERROR, and return False. The
only successful path returns True.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return f"http://{settings.XMPP_HOST}:{settings.XMPP_HTTP_PORT}"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.XMPP_ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }


async def _post(path: str, payload: dict, *, action: str, username: str) -> bool:
    """Common POST path for all three bridge calls.

    Swallows transport errors + 5xx; logs at WARNING. 4xx on the admin token
    is logged at ERROR because it indicates a deployment bug the operator
    needs to see immediately, but still does not raise.
    """
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=1.0)) as client:
            resp = await client.post(url, json=payload, headers=_headers())
        if resp.status_code in (200, 201, 204):
            logger.info("xmpp.%s ok username=%s status=%s", action, username, resp.status_code)
            return True
        if resp.status_code in (401, 403):
            logger.error(
                "xmpp.%s auth_failed username=%s status=%s — check XMPP_ADMIN_TOKEN",
                action,
                username,
                resp.status_code,
            )
            return False
        logger.warning(
            "xmpp.%s failed username=%s status=%s body=%s",
            action,
            username,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("xmpp.%s transport_error username=%s err=%s", action, username, exc)
        return False
    except Exception as exc:  # noqa: BLE001 — spec: never raise out of bridge
        logger.warning("xmpp.%s unexpected_error username=%s err=%s", action, username, exc)
        return False


async def provision_xmpp_user(username: str, password: str) -> bool:
    """Create a JID on Prosody with the given plaintext password.

    Returns True on 2xx from Prosody, False on every other outcome (including
    disabled bridge). Caller must not block flow on the return value.
    """
    if not settings.XMPP_ENABLED:
        return True
    return await _post(
        "/admin/create_user",
        {"username": username, "password": password},
        action="provision",
        username=username,
    )


async def change_xmpp_password(username: str, password: str) -> bool:
    """Rotate the JID's password to match FastAPI."""
    if not settings.XMPP_ENABLED:
        return True
    return await _post(
        "/admin/change_user_password",
        {"username": username, "password": password},
        action="change_password",
        username=username,
    )


async def disable_xmpp_user(username: str) -> bool:
    """Delete the JID (Prosody has no soft-disable; delete reclaims the name)."""
    if not settings.XMPP_ENABLED:
        return True
    return await _post(
        "/admin/delete_user",
        {"username": username},
        action="disable",
        username=username,
    )
