import asyncio
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import Base


@pytest.fixture
async def session() -> AsyncSession:
    """
    Create an isolated in-memory database for each test.
    """

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


@pytest.fixture
def concurrent_engine(tmp_path: Path) -> AsyncEngine:
    """
    Create a file-backed SQLite engine that supports two concurrent writers.

    An in-memory database served by a StaticPool shares a single connection
    between sessions, which serialises transactions and hides real race
    conditions. A file-backed database gives every session its own
    connection, so the UNIQUE constraint is what actually arbitrates a race.
    """

    database_path = tmp_path / "sandheal-concurrency.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    yield engine

    asyncio.run(engine.dispose())
