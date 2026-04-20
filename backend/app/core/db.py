from collections.abc import Generator

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
