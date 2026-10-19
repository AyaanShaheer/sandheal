from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import get_logger

logger = get_logger(__name__)


def get_request_id(request: Request) -> str | None:
    """
    Return the correlation ID attached by RequestIdMiddleware.
    """

    return getattr(request.state, "request_id", None)


def build_error_body(
    detail: object,
    request_id: str | None,
) -> dict[str, object]:
    """
    Build a consistent error body.

    The `detail` key keeps the shape FastAPI already uses, so existing
    clients are unaffected. The correlation ID is additive.
    """

    body: dict[str, object] = {"detail": detail}

    if request_id:
        body["request_id"] = request_id

    return body


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Return a consistent body for handled HTTP errors.
    """

    request_id = get_request_id(request)

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_body(exc.detail, request_id),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Return a consistent body for request validation failures.
    """

    request_id = get_request_id(request)

    return JSONResponse(
        status_code=422,
        content=build_error_body(exc.errors(), request_id),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Return a generic body for an unexpected server error.

    The exception is logged with its traceback and the correlation ID, so
    a failure can be traced without ever leaking internals to the caller.
    """

    request_id = get_request_id(request)

    logger.exception(
        "Unhandled error while processing %s %s (request_id=%s).",
        request.method,
        request.url.path,
        request_id,
        exc_info=exc,
    )

    return JSONResponse(
        status_code=500,
        content=build_error_body("Internal Server Error", request_id),
    )
