"""Idle-reap: WS closes if no messages arrive within IDLE_TIMEOUT (spec 11-ws:127)."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.presence import presence_manager
from tests.conftest import register_and_login


@pytest.fixture(autouse=True)
def _reset_presence_manager():
    yield
    presence_manager.connections.clear()
    presence_manager.tab_status.clear()


def test_ws_closes_after_idle_timeout(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Shrink the reap window so the test finishes quickly.
    monkeypatch.setattr("app.api.routes.ws.IDLE_TIMEOUT", 0.2)

    register_and_login(client, "alice", "alice@test.com")

    with client.websocket_connect("/ws?tab_id=idle-tab") as ws:
        # Drain the initial presence.bulk frame so the server loop reaches receive_json.
        first = ws.receive_json()
        assert first["type"] == "presence.bulk"

        # Without sending anything, the server should close the socket when the
        # asyncio.wait_for timeout fires.
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_ping_resets_idle_timer(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sending any frame must reset the reap window — proves 'any recv resets'."""
    import time

    monkeypatch.setattr("app.api.routes.ws.IDLE_TIMEOUT", 0.4)
    register_and_login(client, "alice", "alice@test.com")

    with client.websocket_connect("/ws?tab_id=ping-tab") as ws:
        assert ws.receive_json()["type"] == "presence.bulk"

        # Wait most of the window, then ping.
        time.sleep(0.25)
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}

        # Wait another chunk that, combined with the first sleep, exceeds the
        # original IDLE_TIMEOUT — the ping must have reset the timer so we
        # stay open.
        time.sleep(0.25)
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
