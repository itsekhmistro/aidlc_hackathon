"""Promote a user to global admin (TASK-13 §1.1).

The `is_admin` flag gates the Jabber admin dashboards. Bootstrap flow:

    docker compose exec backend uv run python -m app.scripts.make_admin ivan

No self-service UI and no auto-seed migration — the first admin is granted
explicitly by someone with DB access, by design. Flipping the flag does NOT
invalidate the target's active session; they will see the nav item appear
after the next `/api/auth/me` refetch (react-query hooks do this on focus).

Idempotent: re-running on an already-admin user prints a note and exits 0.
"""
from __future__ import annotations

import argparse
import sys

from sqlmodel import Session, select

from app.core.db import engine
from app.models.user import User


def promote(username: str) -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            print(f"error: user '{username}' not found", file=sys.stderr)
            return 1
        if user.deleted_at is not None:
            print(f"error: user '{username}' is soft-deleted", file=sys.stderr)
            return 1
        if user.is_admin:
            print(f"note: user '{username}' is already admin — nothing to do")
            return 0
        user.is_admin = True
        session.add(user)
        session.commit()
        print(f"ok: user '{username}' promoted to admin")
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Grant global admin to a user by username.")
    p.add_argument("username")
    args = p.parse_args()
    return promote(args.username)


if __name__ == "__main__":
    raise SystemExit(main())
