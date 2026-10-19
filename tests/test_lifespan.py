import sqlite3
from pathlib import Path

import pytest

import app.main as app_main
from app.core.config import Settings
from app.infrastructure.database import Base


def table_names(database_path: Path) -> set[str]:
    connection = sqlite3.connect(database_path)

    try:
        rows = connection.execute("select name from sqlite_master where type='table'").fetchall()

        return {row[0] for row in rows}
    finally:
        connection.close()


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "lifespan.db"


def use_settings(
    monkeypatch: pytest.MonkeyPatch,
    database_path: Path,
    **overrides: str,
) -> None:
    """
    Point the application at explicit settings for the duration of a test.
    """

    defaults = {
        "environment": "test",
        "github_webhook_secret": "test-secret",
        "database_url": f"sqlite+aiosqlite:///{database_path}",
    }

    defaults.update(overrides)

    monkeypatch.setattr(
        app_main,
        "get_settings",
        lambda: Settings(**defaults),
    )


def test_both_tables_are_registered_on_metadata() -> None:
    """
    The ORM models must be imported for their tables to be created.
    """

    assert "repair_runs" in Base.metadata.tables
    assert "repair_jobs" in Base.metadata.tables


@pytest.mark.anyio
async def test_lifespan_creates_both_tables(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, database_path)

    application = app_main.create_app()

    async with app_main.lifespan(application):
        pass

    assert {"repair_runs", "repair_jobs"} <= table_names(database_path)


@pytest.mark.anyio
async def test_lifespan_starts_in_development_without_a_secret(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Local development must keep working, but the misconfiguration is reported.
    """

    use_settings(
        monkeypatch,
        database_path,
        environment="development",
        github_webhook_secret="",
    )

    application = app_main.create_app()

    async with app_main.lifespan(application):
        pass


@pytest.mark.anyio
async def test_lifespan_refuses_to_start_in_production_without_a_secret(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A production deployment must fail fast instead of silently accepting
    forged webhooks.
    """

    use_settings(
        monkeypatch,
        database_path,
        environment="production",
        github_webhook_secret="",
    )

    application = app_main.create_app()

    with pytest.raises(RuntimeError, match="GITHUB_WEBHOOK_SECRET"):
        async with app_main.lifespan(application):
            pass


@pytest.mark.anyio
async def test_lifespan_refuses_to_start_in_production_with_a_placeholder_secret(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(
        monkeypatch,
        database_path,
        environment="production",
        github_webhook_secret="replace-me",
    )

    application = app_main.create_app()

    with pytest.raises(RuntimeError, match="GITHUB_WEBHOOK_SECRET"):
        async with app_main.lifespan(application):
            pass


@pytest.mark.anyio
async def test_lifespan_starts_in_production_with_a_real_secret(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(
        monkeypatch,
        database_path,
        environment="production",
        github_webhook_secret="a-real-secret",
    )

    application = app_main.create_app()

    async with app_main.lifespan(application):
        pass


@pytest.mark.anyio
async def test_lifespan_can_skip_migrations(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The metadata based fallback is still available for installations that
    do not ship the migration scripts.
    """

    from sqlalchemy.ext.asyncio import create_async_engine

    use_settings(monkeypatch, database_path)

    monkeypatch.setattr(app_main, "migrations_available", lambda: False)

    fallback_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    monkeypatch.setattr(app_main, "engine", fallback_engine)

    application = app_main.create_app()

    async with app_main.lifespan(application):
        pass

    assert {"repair_runs", "repair_jobs"} <= table_names(database_path)
    assert "alembic_version" not in table_names(database_path)
