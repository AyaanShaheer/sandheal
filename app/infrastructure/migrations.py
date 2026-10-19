from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from app.core.logger import get_logger

logger = get_logger(__name__)

MIGRATIONS_PATH = Path(__file__).resolve().parent.parent / "migrations"

BASELINE_REVISION = "0001_baseline"

EXPECTED_TABLES = frozenset({"repair_runs", "repair_jobs"})


def migrations_available() -> bool:
    """
    Return True when the migration scripts ship with the installation.
    """

    return (MIGRATIONS_PATH / "env.py").is_file()


def build_config(database_url: str) -> Config:
    """
    Build an Alembic configuration that points at the packaged migrations.
    """

    config = Config()

    config.set_main_option("script_location", str(MIGRATIONS_PATH))
    config.set_main_option("sqlalchemy.url", database_url)

    return config


def _sync_database_url(database_url: str) -> str:
    """
    Return a synchronous URL for a driver that only ships an async version.
    """

    url = make_url(database_url)

    if url.get_driver_name() == "aiosqlite":
        return url.set(drivername="sqlite").render_as_string(hide_password=False)

    return url.render_as_string(hide_password=False)


def is_unversioned_but_populated(database_url: str) -> bool:
    """
    Detect a database that already has the schema but no Alembic version.

    Such a database was created by an earlier `create_all` run. It has to
    be stamped with the baseline revision, because the baseline migration
    would otherwise try to create tables that already exist.
    """

    engine = create_engine(_sync_database_url(database_url))

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)

            table_names = set(inspector.get_table_names())

            if "alembic_version" in table_names:
                return False

            return EXPECTED_TABLES <= table_names
    except Exception:
        return False
    finally:
        engine.dispose()


def current_revision(database_url: str) -> str | None:
    """
    Return the revision the database is currently at, if any.
    """

    engine = create_engine(_sync_database_url(database_url))

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)

            return context.get_current_revision()
    except Exception:
        return None
    finally:
        engine.dispose()


def head_revision() -> str | None:
    """
    Return the newest revision available in the migration scripts.
    """

    script = ScriptDirectory.from_config(build_config("sqlite://"))

    return script.get_current_head()


def run_migrations(database_url: str) -> None:
    """
    Bring the database up to the newest revision.

    A database that predates Alembic but already carries the schema is
    stamped with the baseline revision instead of being migrated, so an
    existing development database keeps working.
    """

    config = build_config(database_url)

    if is_unversioned_but_populated(database_url):
        logger.warning(
            "Database has the SandHeal schema but no Alembic version. "
            "Stamping it with the baseline revision."
        )

        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
