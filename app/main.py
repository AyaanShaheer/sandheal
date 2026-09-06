from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """
    Application factory.

    Keeping application construction inside a factory makes the
    application easier to test and extend.
    """
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    application.include_router(health_router)

    return application


app = create_app()
