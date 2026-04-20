from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlmodel import Session, SQLModel

import app.core.db as db_module
from app.core.db import get_session
from app.main import app


@pytest.fixture(name="session", scope="function")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client", scope="function")
def client_fixture(session: Session, monkeypatch):
    def get_session_override():
        return session

    # Route the WS endpoint's non-DI session access through the same
    # in-memory SQLite session the rest of the tests see. ws.py refers
    # to `app.core.db.session_scope` (module attribute) exactly so this
    # patch works — see the docstring on session_scope().
    @contextmanager
    def test_session_scope():
        yield session

    monkeypatch.setattr(db_module, "session_scope", test_session_scope)
    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str, email: str, password: str = "password123") -> TestClient:
    """Register a user and return the client with the auth cookie set."""
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    return client
