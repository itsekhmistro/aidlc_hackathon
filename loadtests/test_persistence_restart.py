"""TASK-16 Scenario S5 — persistence_restart.

Validates NFR 3.3 (messages persisted across restarts) by:

1. Re-seeding load-test data with 10 rooms × 500 messages.
2. Snapshotting the full history of every seeded room.
3. ``docker compose restart backend`` and polling ``/health``.
4. Re-reading every room and asserting byte-equal ``(id, content,
   created_at, author_id)`` tuples, with no extra rows.

The test is designed to be *environmentally safe*: if the Docker CLI
isn't on ``$PATH`` or the backend isn't answering at
``http://localhost:8000``, it ``pytest.skip()``s rather than failing.
Run explicitly from ``backend/``::

    uv run pytest ../loadtests/test_persistence_restart.py -v

The test shells out to the repo-root seeder (``backend/scripts/seed_load.py``);
it is intentionally not imported as a Python module to avoid pulling the
SQLAlchemy engine into this process.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

BACKEND_URL = os.environ.get("LOADTEST_BACKEND_URL", "http://localhost:8000")
HEALTH_URL = f"{BACKEND_URL}/health"
HEALTH_TIMEOUT_S = 30.0
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _backend_healthy(timeout: float = 2.0) -> bool:
    try:
        r = httpx.get(HEALTH_URL, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _wait_for_health(deadline_s: float) -> bool:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if _backend_healthy(timeout=2.0):
            return True
        time.sleep(1.0)
    return False


def _run_seeder(token_out: Path) -> None:
    """Call the seeder as a subprocess so its engine doesn't collide with ours."""
    cmd = [
        "uv", "run", "python", "-m", "scripts.seed_load",
        "--reset",
        "--users", "50",
        "--rooms", "10",
        "--members-per-room", "5",
        "--messages", "500",
        "--big-room-size", "0",
        "--history-room-size", "0",
        "--history-room-messages", "0",
        "--token-out", str(token_out),
    ]
    result = subprocess.run(
        cmd,
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"seed_load failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _list_loadtest_rooms(client: httpx.Client) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(50):
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = client.get(f"{BACKEND_URL}/api/rooms", params=params)
        r.raise_for_status()
        page = r.json()
        page_rooms = [room for room in page if room.get("name", "").startswith("loadtest_")]
        rooms.extend(page_rooms)
        if len(page) < 100:
            break
        cursor = page[-1]["id"]
    return rooms


def _fetch_all_messages(client: httpx.Client, room_id: str) -> list[tuple[str, str, str, str]]:
    """Return a list of ``(id, content, created_at, author_id)`` tuples, oldest-first."""
    tuples: list[tuple[str, str, str, str]] = []
    cursor: str | None = None
    for _ in range(1000):  # 10 rooms × 500 msgs ÷ 100/page = 50 pages; 1000 is plenty.
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["before"] = cursor
        r = client.get(f"{BACKEND_URL}/api/rooms/{room_id}/messages", params=params)
        r.raise_for_status()
        page = r.json()
        for m in page["messages"]:
            tuples.append((
                m["id"],
                m["content"],
                m["created_at"],
                m["author_id"],
            ))
        if not page["has_more"] or not page["messages"]:
            break
        cursor = page["messages"][-1]["id"]
    tuples.sort(key=lambda t: t[2])  # by created_at ascending
    return tuples


def test_persistence_survives_backend_restart() -> None:
    # ── environment preflight ────────────────────────────────────────────
    if not _backend_healthy(timeout=2.0):
        pytest.skip(f"backend not reachable at {BACKEND_URL}")
    if not _docker_available():
        pytest.skip("docker CLI not on PATH — cannot restart backend")
    if not BACKEND_DIR.exists():
        pytest.skip(f"backend dir not found at {BACKEND_DIR}")

    with tempfile.TemporaryDirectory(prefix="s5_") as tmp:
        token_out = Path(tmp) / "tokens_s5.json"

        # 1. Seed fresh data (10 rooms × 500 msgs).
        _run_seeder(token_out)
        assert token_out.exists(), "seeder did not produce token file"
        tokens = json.loads(token_out.read_text())
        assert tokens, "seeder produced empty token list"

        cookie = {"auth_token": tokens[0]["session_token"]}
        with httpx.Client(cookies=cookie, timeout=30.0) as client:
            # 2. Pre-snapshot
            rooms = _list_loadtest_rooms(client)
            assert rooms, "no loadtest_ rooms visible after seeding"
            before: dict[str, list[tuple[str, str, str, str]]] = {}
            for room in rooms:
                before[room["id"]] = _fetch_all_messages(client, room["id"])
            total_before = sum(len(v) for v in before.values())
            assert total_before > 0, "pre-snapshot has zero messages"

            # 3. Restart backend and wait for /health
            restart = subprocess.run(
                ["docker", "compose", "restart", "backend"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if restart.returncode != 0:
                pytest.skip(
                    f"docker compose restart failed (is compose stack up?): "
                    f"{restart.stderr.strip()}"
                )
            assert _wait_for_health(HEALTH_TIMEOUT_S), (
                f"backend did not return healthy within {HEALTH_TIMEOUT_S}s"
            )

        # 4. Post-snapshot
        with httpx.Client(cookies=cookie, timeout=30.0) as client:
            after: dict[str, list[tuple[str, str, str, str]]] = {}
            for room in rooms:
                after[room["id"]] = _fetch_all_messages(client, room["id"])

        # 5. Byte-equal assertion per room + no-extra-rows invariant
        missing: list[str] = []
        extra: list[str] = []
        total_after = 0
        for room_id, pre_tuples in before.items():
            post_tuples = after.get(room_id, [])
            total_after += len(post_tuples)
            pre_set = set(pre_tuples)
            post_set = set(post_tuples)
            for t in pre_set - post_set:
                missing.append(f"room {room_id} missing {t[0]}")
            for t in post_set - pre_set:
                extra.append(f"room {room_id} gained {t[0]}")
        assert not missing, f"{len(missing)} pre-existing messages lost: {missing[:5]}"
        assert not extra, f"{len(extra)} unexpected new messages: {extra[:5]}"
        assert total_after == total_before, (
            f"count mismatch: {total_before} before, {total_after} after"
        )

        print(
            f"\nS5 verdict: {total_before} messages across {len(rooms)} rooms "
            f"survived `docker compose restart backend` byte-equal.",
            file=sys.stderr,
        )
