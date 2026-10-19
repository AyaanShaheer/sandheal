from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.infrastructure.database import get_session

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


def build_ready_response() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
        },
    )


def build_unavailable_response(exc: Exception) -> JSONResponse:
    logger.warning("Readiness check failed: %s", exc)

    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "detail": "Database is not reachable.",
        },
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Lightweight liveness endpoint.

    This endpoint intentionally does not check external dependencies.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """
    Readiness endpoint.

    Unlike `/health`, this endpoint verifies that the database is
    reachable, so a broken dependency is reported instead of being
    silently served.
    """

    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return build_unavailable_response(exc)

    return build_ready_response()
