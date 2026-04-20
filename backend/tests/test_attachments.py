"""Unit tests for /api/attachments — TASK-07."""
import io
import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import register_and_login


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    yield tmp_path


def _auth(client: TestClient, name: str) -> TestClient:
    return register_and_login(client, name, f"{name}@test.com")


def _login(client: TestClient, name: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={"email": f"{name}@test.com", "password": "password123", "persistent": False},
    )
    assert r.status_code == 200, r.text
    return client


def _create_room(client: TestClient, name: str, visibility: str = "public") -> dict:
    r = client.post("/api/rooms", json={"name": name, "visibility": visibility})
    assert r.status_code == 201, r.text
    return r.json()


def _file(name: str = "hello.txt", data: bytes = b"hello world", mime: str = "text/plain"):
    return {"file": (name, io.BytesIO(data), mime)}


# ─── POST /api/attachments/{room_id} ─────────────────────────────────────────


def test_upload_attachment_happy_path_returns_201(client: TestClient, _upload_dir):
    _auth(client, "att_up1")
    room = _create_room(client, "att-up-room")
    r = client.post(f"/api/attachments/{room['id']}", files=_file())
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["original_filename"] == "hello.txt"
    assert data["mime_type"] == "text/plain"
    assert data["size_bytes"] == len(b"hello world")
    assert data["comment"] is None
    # file is persisted on disk
    assert (_upload_dir / data["id"] / "hello.txt").read_bytes() == b"hello world"


def test_upload_attachment_with_comment(client: TestClient):
    _auth(client, "att_up2")
    room = _create_room(client, "att-comment-room")
    r = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(),
        data={"comment": "look at this"},
    )
    assert r.status_code == 201
    assert r.json()["comment"] == "look at this"


def test_upload_attachment_non_member_returns_403(client: TestClient):
    _auth(client, "att_up3")
    room = _create_room(client, "att-403-room", visibility="private")
    client.cookies.clear()
    _auth(client, "att_outsider")
    r = client.post(f"/api/attachments/{room['id']}", files=_file())
    assert r.status_code == 403


def test_upload_attachment_unauthenticated_returns_401(client: TestClient):
    r = client.post(f"/api/attachments/{uuid.uuid4()}", files=_file())
    assert r.status_code == 401


def test_upload_attachment_too_large_returns_413(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 10)
    _auth(client, "att_up4")
    room = _create_room(client, "att-size-room")
    r = client.post(f"/api/attachments/{room['id']}", files=_file(data=b"x" * 11))
    assert r.status_code == 413


def test_upload_image_over_3mb_returns_413(client: TestClient, monkeypatch):
    """Images use MAX_IMAGE_SIZE_BYTES (3 MB), not MAX_FILE_SIZE_BYTES."""
    monkeypatch.setattr(settings, "MAX_IMAGE_SIZE_BYTES", 100)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 20 * 1024 * 1024)
    _auth(client, "att_img_big")
    room = _create_room(client, "att-img-big-room")
    r = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(name="pic.png", data=b"x" * 101, mime="image/png"),
    )
    assert r.status_code == 413
    assert "limit" in r.json()["detail"].lower()


def test_upload_image_under_3mb_succeeds(client: TestClient):
    """Image under the 3 MB default limit uploads fine."""
    _auth(client, "att_img_ok")
    room = _create_room(client, "att-img-ok-room")
    r = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(name="pic.png", data=b"x" * 1024, mime="image/png"),
    )
    assert r.status_code == 201
    assert r.json()["mime_type"] == "image/png"


def test_upload_non_image_between_3mb_and_20mb_succeeds(client: TestClient, monkeypatch):
    """A ~5 MB non-image should pass (uses the 20 MB limit, not the 3 MB image limit)."""
    monkeypatch.setattr(settings, "MAX_IMAGE_SIZE_BYTES", 3 * 1024 * 1024)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 20 * 1024 * 1024)
    _auth(client, "att_big_doc")
    room = _create_room(client, "att-big-doc-room")
    r = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(name="doc.bin", data=b"x" * (5 * 1024 * 1024), mime="application/octet-stream"),
    )
    assert r.status_code == 201


def test_upload_attachment_sanitizes_path_traversal(client: TestClient, _upload_dir):
    _auth(client, "att_up5")
    room = _create_room(client, "att-sanitize-room")
    r = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(name="../../evil.txt"),
    )
    assert r.status_code == 201
    assert r.json()["original_filename"] == "evil.txt"
    # Must not have escaped the upload directory
    escaped = _upload_dir.parent / "evil.txt"
    assert not escaped.exists()


# ─── GET /api/attachments/{attachment_id} ────────────────────────────────────


def test_download_attachment_by_uploader_returns_file(client: TestClient):
    _auth(client, "att_dl1")
    room = _create_room(client, "att-dl-room")
    up = client.post(f"/api/attachments/{room['id']}", files=_file(data=b"payload"))
    att_id = up.json()["id"]
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 200
    assert r.content == b"payload"


def test_download_attachment_by_room_member_returns_file(client: TestClient):
    _auth(client, "att_dl_owner")
    room = _create_room(client, "att-dl-member-room", visibility="public")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]

    client.cookies.clear()
    _auth(client, "att_dl_joiner")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 200


def test_download_attachment_by_non_member_returns_403(client: TestClient):
    _auth(client, "att_dl_owner2")
    room = _create_room(client, "att-dl-403-room", visibility="private")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]

    client.cookies.clear()
    _auth(client, "att_dl_outsider")
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 403


def test_download_attachment_by_banned_uploader_returns_403(client: TestClient):
    """A user who gets banned from a room loses access to files they uploaded there."""
    # owner creates room
    _auth(client, "att_ban_owner")
    room = _create_room(client, "att-ban-room", visibility="public")

    # bannable joins and uploads a file
    client.cookies.clear()
    _auth(client, "att_ban_victim")
    client.post(f"/api/rooms/{room['id']}/join")
    up = client.post(f"/api/attachments/{room['id']}", files=_file(data=b"secret"))
    att_id = up.json()["id"]

    # Sanity: uploader can download while still a member
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 200

    # owner bans the uploader
    members = client.get(f"/api/rooms/{room['id']}/members").json()
    victim_id = next(m["user_id"] for m in members if m["username"] == "att_ban_victim")
    client.cookies.clear()
    _login(client, "att_ban_owner")
    assert client.delete(f"/api/rooms/{room['id']}/members/{victim_id}").status_code == 204

    # banned uploader tries to download → 403
    client.cookies.clear()
    _login(client, "att_ban_victim")
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 403


def test_download_attachment_not_found_returns_404(client: TestClient):
    _auth(client, "att_dl2")
    r = client.get(f"/api/attachments/{uuid.uuid4()}")
    assert r.status_code == 404


def test_download_attachment_unauthenticated_returns_401(client: TestClient):
    r = client.get(f"/api/attachments/{uuid.uuid4()}")
    assert r.status_code == 401


def test_download_attachment_file_missing_on_disk_returns_404(client: TestClient, _upload_dir):
    _auth(client, "att_dl3")
    room = _create_room(client, "att-missing-room")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]
    # Nuke the file on disk
    import shutil
    shutil.rmtree(_upload_dir / att_id)
    r = client.get(f"/api/attachments/{att_id}")
    assert r.status_code == 404


# ─── DELETE /api/attachments/{attachment_id} ─────────────────────────────────


def test_delete_attachment_by_uploader_returns_204(client: TestClient, _upload_dir):
    _auth(client, "att_del1")
    room = _create_room(client, "att-del-room")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]

    r = client.delete(f"/api/attachments/{att_id}")
    assert r.status_code == 204
    # Storage dir should be gone
    assert not (_upload_dir / att_id).exists()
    # Subsequent download should be 404
    r2 = client.get(f"/api/attachments/{att_id}")
    assert r2.status_code == 404


def test_delete_attachment_by_non_uploader_returns_403(client: TestClient):
    _auth(client, "att_del_owner")
    room = _create_room(client, "att-del-403-room", visibility="public")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]

    client.cookies.clear()
    _auth(client, "att_del_member")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.delete(f"/api/attachments/{att_id}")
    assert r.status_code == 403


def test_delete_attachment_not_found_returns_404(client: TestClient):
    _auth(client, "att_del2")
    r = client.delete(f"/api/attachments/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_attachment_unauthenticated_returns_401(client: TestClient):
    r = client.delete(f"/api/attachments/{uuid.uuid4()}")
    assert r.status_code == 401


# ─── Message linking ─────────────────────────────────────────────────────────


def test_send_message_links_pending_attachments(client: TestClient):
    _auth(client, "att_link1")
    room = _create_room(client, "att-link-room")
    up = client.post(f"/api/attachments/{room['id']}", files=_file(name="a.txt"))
    att_id = up.json()["id"]

    r = client.post(
        f"/api/rooms/{room['id']}/messages",
        json={"content": "see file", "attachment_ids": [att_id]},
    )
    assert r.status_code == 201
    msg = r.json()
    assert len(msg["attachments"]) == 1
    assert msg["attachments"][0]["id"] == att_id
    assert msg["attachments"][0]["original_filename"] == "a.txt"


def test_send_message_ignores_attachment_uploaded_by_other_user(client: TestClient):
    _auth(client, "att_link_owner")
    room = _create_room(client, "att-link-cross-room", visibility="public")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]

    client.cookies.clear()
    _auth(client, "att_link_other")
    client.post(f"/api/rooms/{room['id']}/join")
    r = client.post(
        f"/api/rooms/{room['id']}/messages",
        json={"content": "stolen", "attachment_ids": [att_id]},
    )
    assert r.status_code == 201
    # Attachment must NOT be attached — it belongs to another user
    assert r.json()["attachments"] == []


def test_send_message_ignores_attachment_from_other_room(client: TestClient):
    _auth(client, "att_link_x1")
    room_a = _create_room(client, "room-a")
    room_b = _create_room(client, "room-b")
    up = client.post(f"/api/attachments/{room_a['id']}", files=_file())
    att_id = up.json()["id"]

    r = client.post(
        f"/api/rooms/{room_b['id']}/messages",
        json={"content": "wrong room", "attachment_ids": [att_id]},
    )
    assert r.status_code == 201
    assert r.json()["attachments"] == []


def test_send_message_without_content_but_with_attachment_succeeds(client: TestClient):
    _auth(client, "att_link_noc")
    room = _create_room(client, "att-noc-room")
    up = client.post(f"/api/attachments/{room['id']}", files=_file())
    att_id = up.json()["id"]
    r = client.post(
        f"/api/rooms/{room['id']}/messages",
        json={"content": "", "attachment_ids": [att_id]},
    )
    assert r.status_code == 201
    assert len(r.json()["attachments"]) == 1


# ─── Lifecycle ───────────────────────────────────────────────────────────────


def test_room_deletion_removes_attachment_files_from_disk(
    client: TestClient, _upload_dir
):
    """TASK-07 AC #8: deleting a room purges its attachments from disk."""
    _auth(client, "att_life_owner")
    room = _create_room(client, "att-life-room")
    up1 = client.post(f"/api/attachments/{room['id']}", files=_file(name="a.txt"))
    up2 = client.post(
        f"/api/attachments/{room['id']}",
        files=_file(name="b.png", data=b"\x89PNG", mime="image/png"),
    )
    att1, att2 = up1.json()["id"], up2.json()["id"]

    path1 = pathlib.Path(_upload_dir) / att1 / "a.txt"
    path2 = pathlib.Path(_upload_dir) / att2 / "b.png"
    assert path1.exists() and path2.exists()

    assert client.delete(f"/api/rooms/{room['id']}").status_code == 204

    # Files are gone; DB rows cascade; download returns 404
    assert not path1.exists()
    assert not path2.exists()
    assert client.get(f"/api/attachments/{att1}").status_code == 404
    assert client.get(f"/api/attachments/{att2}").status_code == 404
