from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Lightweight liveness endpoint.

    This endpoint intentionally does not check external dependencies.
    """
    return {"status": "ok"}
