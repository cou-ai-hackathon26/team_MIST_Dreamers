"""Database connection: engine, session factory, table creation (SQLite by default)."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.models import Base

_IN_MEMORY = {"sqlite://", "sqlite:///:memory:"}


def make_engine(database_url: str) -> Engine:
    """Creates the engine. For SQLite: makes the data folder, enables foreign keys."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(database_url, pool_pre_ping=True)

    if database_url in _IN_MEMORY:
        # One shared connection, so every session sees the same in-memory database (tests).
        engine = create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        if url.database:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        # FastAPI may use the connection from another thread than the one that opened it.
        engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")  # SQLite ignores foreign keys unless asked
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Creates any missing tables. Safe to run on every start (never drops data)."""
    Base.metadata.create_all(engine)
