from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.github import router as github_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.infrastructure.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Initialize local database tables when the application starts.

    This is intentionally simple for development.
    Production schema management will use Alembic migrations.
    """

    from app.infrastructure.models.repair_run import RepairRunRecord

    del RepairRunRecord

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield


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

    application.include_router(health_router)
    application.include_router(github_router)

    return application


app = create_app()
