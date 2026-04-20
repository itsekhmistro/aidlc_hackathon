from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Pool sizing — TASK-16 (NFR load-test prep).
# SQLAlchemy defaults (pool_size=5, max_overflow=10) starve at S1's 300 VUs:
# every REST hit grabs a connection for the request lifetime, and the WS
# endpoint holds one for the duration of the connection. 50 + 50 gives us
# ~100 concurrent connections before we queue — comfortable headroom for
# 300 VUs given that WS traffic spends most of its time idle in recv.
# pool_pre_ping guards against stale connections after `docker compose
# restart backend` (Scenario S5).
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_size=50,
    max_overflow=50,
    pool_pre_ping=True,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Non-DI session context for code paths that can't use ``Depends``.

    The WebSocket endpoint in ``app.api.routes.ws`` offloads DB work to
    ``asyncio.to_thread`` (see TASK-16 NFR load-test prep); FastAPI's
    ``Depends(get_session)`` would pin a pool connection for the
    connection's lifetime. Callers route through this helper instead of
    constructing ``Session(engine)`` inline so tests can override the
    scope by monkeypatching ``app.core.db.session_scope``.
    """
    with Session(engine) as session:
        yield session
