import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection, create_engine, make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.infrastructure import models  # noqa: F401  (registers the ORM tables)
from app.infrastructure.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

ASYNC_DRIVERS = frozenset(
    {
        "aiosqlite",
        "asyncpg",
        "aiomysql",
        "aioodbc",
    }
)


def get_url() -> str:
    """
    Resolve the database URL.

    It comes from the Alembic configuration when one was supplied, and
    otherwise from the application settings, so the CLI and the
    application always target the same database.
    """

    configured = config.get_main_option("sqlalchemy.url")

    if configured:
        return configured

    return get_settings().database_url


def is_async_url(url: str) -> bool:
    return make_url(url).get_driver_name() in ASYNC_DRIVERS


def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.
    """

    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_sync_migrations() -> None:
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            do_run_migrations(connection)
    finally:
        connectable.dispose()


def run_migrations_online() -> None:
    if is_async_url(get_url()):
        asyncio.run(run_async_migrations())
    else:
        run_sync_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
