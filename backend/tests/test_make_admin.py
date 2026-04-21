"""Tests for the `app.scripts.make_admin` CLI (TASK-13 §1.1).

The CLI is the only way to grant the first admin — broken behavior here
leaks directly into "operator can't reach /admin/jabber on a fresh
deploy". Coverage: happy path, not-found, soft-deleted, idempotent
re-run, return codes.

We swap out `make_admin.engine` for an in-memory SQLite engine for the
duration of each test so we can run against a clean DB without touching
Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlmodel import Session, SQLModel, select

from app.models.user import User
from app.scripts import make_admin


@pytest.fixture(name="mem_engine", scope="function")
def _mem_engine_fixture(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(make_admin, "engine", engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def _seed_user(engine, username: str, *, is_admin: bool = False, deleted: bool = False) -> None:
    with Session(engine) as s:
        s.add(
            User(
                username=username,
                email=f"{username}@test.example",
                hashed_password="x",
                is_admin=is_admin,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )
        s.commit()


def _is_admin(engine, username: str) -> bool:
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        assert user is not None
        return user.is_admin


def test_promote_flips_flag_and_returns_zero(mem_engine, capsys):
    _seed_user(mem_engine, "ivan")
    assert _is_admin(mem_engine, "ivan") is False

    rc = make_admin.promote("ivan")

    assert rc == 0
    assert _is_admin(mem_engine, "ivan") is True
    out = capsys.readouterr().out
    assert "promoted to admin" in out


def test_promote_unknown_user_returns_one(mem_engine, capsys):
    rc = make_admin.promote("ghost")

    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_promote_already_admin_is_idempotent(mem_engine, capsys):
    _seed_user(mem_engine, "ivan", is_admin=True)

    rc = make_admin.promote("ivan")

    assert rc == 0  # idempotent success
    assert _is_admin(mem_engine, "ivan") is True
    out = capsys.readouterr().out
    assert "already admin" in out


def test_promote_soft_deleted_user_refuses(mem_engine, capsys):
    _seed_user(mem_engine, "ghost", deleted=True)

    rc = make_admin.promote("ghost")

    assert rc == 1
    err = capsys.readouterr().err
    assert "soft-deleted" in err
    # Flag must NOT have been flipped on a tombstone.
    assert _is_admin(mem_engine, "ghost") is False


def test_main_dispatches_to_promote(mem_engine, monkeypatch, capsys):
    """argparse surface + exit code propagation."""
    _seed_user(mem_engine, "ivan")
    monkeypatch.setattr("sys.argv", ["make_admin", "ivan"])

    rc = make_admin.main()

    assert rc == 0
    assert _is_admin(mem_engine, "ivan") is True
