import sqlite3
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine

from app.infrastructure import models  # noqa: F401  (registers the ORM tables)
from app.infrastructure.database import Base
from app.infrastructure.migrations import (
    BASELINE_REVISION,
    build_config,
    current_revision,
    head_revision,
    is_unversioned_but_populated,
    migrations_available,
    run_migrations,
)


def make_url(tmp_path: Path, name: str = "migrations.db") -> str:
    return f"sqlite+aiosqlite:///{tmp_path / name}"


def table_names(database_path: Path) -> set[str]:
    connection = sqlite3.connect(database_path)

    try:
        rows = connection.execute("select name from sqlite_master where type='table'").fetchall()

        return {row[0] for row in rows}
    finally:
        connection.close()


def test_migrations_are_shipped_with_the_package() -> None:
    assert migrations_available() is True


def test_fresh_database_is_migrated(tmp_path: Path) -> None:
    database_url = make_url(tmp_path)

    run_migrations(database_url)

    assert current_revision(database_url) == head_revision()
    assert {"repair_runs", "repair_jobs", "alembic_version"} <= table_names(
        tmp_path / "migrations.db"
    )


def test_migrated_schema_matches_the_orm_metadata(tmp_path: Path) -> None:
    """
    The migrations and the ORM models must never drift apart.
    """

    database_url = make_url(tmp_path)

    run_migrations(database_url)

    # `check` compares the database against the metadata and raises when
    # they differ.
    command.check(build_config(database_url))


def test_migration_is_idempotent(tmp_path: Path) -> None:
    database_url = make_url(tmp_path)

    run_migrations(database_url)
    run_migrations(database_url)

    assert current_revision(database_url) == head_revision()


def test_legacy_database_is_stamped_instead_of_migrated(tmp_path: Path) -> None:
    """
    A database created before Alembic existed already has the schema, so it
    must be stamped with the baseline rather than migrated.
    """

    database_path = tmp_path / "migrations.db"
    database_url = make_url(tmp_path)

    engine = create_engine(f"sqlite:///{database_path}")

    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    assert "alembic_version" not in table_names(database_path)
    assert is_unversioned_but_populated(database_url) is True

    run_migrations(database_url)

    assert current_revision(database_url) == BASELINE_REVISION
    assert {"repair_runs", "repair_jobs", "alembic_version"} <= table_names(database_path)


def test_a_versioned_database_is_not_stamped(tmp_path: Path) -> None:
    database_url = make_url(tmp_path)

    run_migrations(database_url)

    assert is_unversioned_but_populated(database_url) is False


def test_empty_database_is_not_stamped(tmp_path: Path) -> None:
    database_url = make_url(tmp_path)

    assert is_unversioned_but_populated(database_url) is False


@pytest.mark.anyio
async def test_lifespan_applies_the_migrations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The application must bring the database up to date on startup.
    """

    import app.main as app_main
    from app.core.config import Settings

    database_url = make_url(tmp_path, "lifespan.db")

    monkeypatch.setattr(
        app_main,
        "get_settings",
        lambda: Settings(
            environment="test",
            github_webhook_secret="test-secret",
            database_url=database_url,
        ),
    )

    application = app_main.create_app()

    async with app_main.lifespan(application):
        pass

    assert current_revision(database_url) == head_revision()
