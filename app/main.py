import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.github import router as github_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware
from app.infrastructure.database import Base, engine
from app.infrastructure.migrations import migrations_available, run_migrations
from app.infrastructure.models import RepairJobRecord, RepairRunRecord

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Prepare the database when the application starts.

    The schema is managed by Alembic migrations. When the migration
    scripts are not available, for example in an installation that does
    not ship them, the tables are created directly from the ORM metadata
    instead.
    """

    configure_logging()

    settings = get_settings()

    if not settings.webhook_secret_configured:
        message = (
            "GITHUB_WEBHOOK_SECRET is not configured (empty or a known placeholder). "
            "GitHub webhook deliveries will be rejected with HTTP 503."
        )

        if settings.is_production:
            raise RuntimeError(
                f"{message} Refusing to start in the '{settings.environment}' environment."
            )

        logger.error(message)

    expected_tables = {
        RepairRunRecord.__tablename__,
        RepairJobRecord.__tablename__,
    }

    missing_tables = expected_tables - set(Base.metadata.tables)

    if missing_tables:
        raise RuntimeError(
            f"ORM tables are not registered on Base.metadata: {sorted(missing_tables)}."
        )

    if settings.auto_migrate and migrations_available():
        # Alembic manages its own event loop, so it runs in a worker thread
        # instead of inside the application's event loop.
        await asyncio.to_thread(run_migrations, settings.database_url)
    else:
        if settings.auto_migrate:
            logger.warning(
                "Alembic migrations are not available in this installation. "
                "Creating the tables from the ORM metadata instead."
            )

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    """
    Application factory.
    """

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    application.add_middleware(RequestIdMiddleware)

    application.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    application.add_exception_handler(Exception, unhandled_exception_handler)

    application.include_router(health_router)
    application.include_router(github_router)

    return application


app = create_app()
