import uuid

import pytest
from tests.conftest import register_and_login
from app.core.presence import presence_manager


# ── Bulk presence — offline (no live connections, no DB record) ───────────────


def test_bulk_presence_unknown_user_returns_offline(client):
    register_and_login(client, "alice", "alice@test.com")
    random_uid = str(uuid.uuid4())
    r = client.post("/api/presence/bulk", json={"user_ids": [random_uid]})
    assert r.status_code == 200
    data = r.json()
    assert data["presences"][random_uid] == "offline"


def test_bulk_presence_requires_auth(client):
    r = client.post("/api/presence/bulk", json={"user_ids": [str(uuid.uuid4())]})
    assert r.status_code == 401


def test_bulk_presence_empty_list_returns_empty_dict(client):
    register_and_login(client, "alice", "alice@test.com")
    r = client.post("/api/presence/bulk", json={"user_ids": []})
    assert r.status_code == 200
    assert r.json()["presences"] == {}


def test_bulk_presence_falls_back_to_db_status(client, session):
    from app.models.user import Presence, User
    from app.core.security import get_password_hash
    from sqlmodel import Session

    register_and_login(client, "alice", "alice@test.com")

    # Create a user directly in DB with a presence record set to "afk"
    target_user = User(username="ghost", email="ghost@test.com", hashed_password=get_password_hash("x"))
    session.add(target_user)
    session.commit()
    session.refresh(target_user)

    presence = Presence(user_id=target_user.id, status="afk")
    session.add(presence)
    session.commit()

    # No live WS connection → compute_status returns "offline" → should fall back to DB "afk"
    uid_str = str(target_user.id)
    r = client.post("/api/presence/bulk", json={"user_ids": [uid_str]})
    assert r.status_code == 200
    # offline in live presence_manager → falls back to DB → should be "afk"
    assert r.json()["presences"][uid_str] == "afk"


def test_bulk_presence_multiple_users(client):
    register_and_login(client, "alice", "alice@test.com")
    uid1 = str(uuid.uuid4())
    uid2 = str(uuid.uuid4())
    r = client.post("/api/presence/bulk", json={"user_ids": [uid1, uid2]})
    assert r.status_code == 200
    presences = r.json()["presences"]
    assert uid1 in presences
    assert uid2 in presences
    assert presences[uid1] == "offline"
    assert presences[uid2] == "offline"


# ── PresenceManager unit logic (no HTTP) ─────────────────────────────────────


@pytest.fixture(autouse=False)
def clean_presence():
    """Reset presence_manager state between tests."""
    yield
    presence_manager.connections.clear()
    presence_manager.tab_status.clear()


def test_presence_manager_compute_status_no_connections():
    uid = uuid.uuid4()
    assert presence_manager.compute_status(uid) == "offline"


def test_presence_manager_compute_status_online_tab():
    import asyncio

    uid = uuid.uuid4()
    tab = "tab-1"

    class FakeWS:
        async def send_json(self, data): pass

    asyncio.run(presence_manager.connect(uid, tab, FakeWS()))
    presence_manager.tab_status[tab] = "online"
    assert presence_manager.compute_status(uid) == "online"

    asyncio.run(presence_manager.disconnect(uid, tab))


def test_presence_manager_compute_status_afk_tab():
    import asyncio

    uid = uuid.uuid4()
    tab = "tab-afk"

    class FakeWS:
        async def send_json(self, data): pass

    asyncio.run(presence_manager.connect(uid, tab, FakeWS()))
    presence_manager.tab_status[tab] = "afk"
    assert presence_manager.compute_status(uid) == "afk"

    asyncio.run(presence_manager.disconnect(uid, tab))


def test_presence_manager_online_wins_over_afk():
    import asyncio

    uid = uuid.uuid4()
    tab1, tab2 = "tab-a", "tab-b"

    class FakeWS:
        async def send_json(self, data): pass

    asyncio.run(presence_manager.connect(uid, tab1, FakeWS()))
    asyncio.run(presence_manager.connect(uid, tab2, FakeWS()))
    presence_manager.tab_status[tab1] = "afk"
    presence_manager.tab_status[tab2] = "online"
    assert presence_manager.compute_status(uid) == "online"

    asyncio.run(presence_manager.disconnect(uid, tab1))
    asyncio.run(presence_manager.disconnect(uid, tab2))


def test_presence_manager_disconnect_returns_offline_when_no_tabs_remain():
    import asyncio

    uid = uuid.uuid4()
    tab = "tab-only"

    class FakeWS:
        async def send_json(self, data): pass

    asyncio.run(presence_manager.connect(uid, tab, FakeWS()))
    status = asyncio.run(presence_manager.disconnect(uid, tab))
    assert status == "offline"
