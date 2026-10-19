from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.repair_runs import RepairRunService
from app.core.config import Settings, get_settings
from app.core.logger import get_logger
from app.domain.errors import InvalidWebhookPayloadError
from app.domain.failures import WorkflowFailure
from app.domain.models import RepairRun
from app.infrastructure.database import get_session
from app.integrations.github.security import verify_signature
from app.integrations.github.webhook import (
    normalize_workflow_run,
    parse_json_payload,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)

MAX_BODY_BYTES = 1_048_576

MAX_DELIVERY_ID_LENGTH = 64

EXPECTED_CONTENT_TYPE = "application/json"


def build_secret_not_configured_response() -> JSONResponse:
    """
    Refuse a delivery when no usable webhook secret is configured.
    """

    logger.error(
        "Rejected GitHub webhook: GITHUB_WEBHOOK_SECRET is not configured. "
        "Set a non-placeholder secret before accepting deliveries."
    )

    return JSONResponse(
        status_code=503,
        content={
            "detail": "GitHub webhook secret is not configured.",
        },
    )


def build_invalid_signature_response(delivery_id: str | None) -> JSONResponse:
    logger.warning(
        "Rejected GitHub webhook: invalid signature (delivery=%s).",
        delivery_id,
    )

    return JSONResponse(
        status_code=403,
        content={
            "detail": "Invalid webhook signature.",
        },
    )


def build_missing_delivery_response() -> JSONResponse:
    logger.warning("Rejected GitHub webhook: missing X-GitHub-Delivery header.")

    return JSONResponse(
        status_code=400,
        content={
            "detail": "Missing X-GitHub-Delivery header.",
        },
    )


def build_ignored_response(
    reason: str,
    delivery_id: str,
) -> JSONResponse:
    """
    Acknowledge a valid delivery that SandHeal has no work for.
    """

    logger.info(
        "Ignored GitHub webhook: %s (delivery=%s).",
        reason,
        delivery_id,
    )

    return JSONResponse(
        status_code=200,
        content={
            "accepted": False,
            "reason": reason,
            "delivery_id": delivery_id,
        },
    )


def build_accepted_response(
    run: RepairRun,
    created: bool,
    failure_event: WorkflowFailure,
) -> JSONResponse:
    """
    Report the outcome of a stored repair run.
    """

    if not created:
        logger.info(
            "Duplicate GitHub delivery ignored (delivery=%s, run=%s).",
            failure_event.delivery_id,
            run.id,
        )

        return JSONResponse(
            status_code=200,
            content={
                "accepted": True,
                "duplicate": True,
                "delivery_id": failure_event.delivery_id,
                "run_id": str(run.id),
            },
        )

    logger.info(
        "Accepted GitHub failure (delivery=%s, run=%s, repository=%s).",
        failure_event.delivery_id,
        run.id,
        failure_event.repository,
    )

    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "duplicate": False,
            "delivery_id": failure_event.delivery_id,
            "run_id": str(run.id),
            "repository": failure_event.repository,
            "commit_sha": failure_event.commit_sha,
            "workflow_run_id": failure_event.workflow_run_id,
        },
    )


def build_invalid_payload_response(detail: str) -> JSONResponse:
    logger.warning("Rejected GitHub webhook: %s", detail)

    return JSONResponse(
        status_code=400,
        content={
            "detail": detail,
        },
    )


def build_oversized_body_response() -> JSONResponse:
    logger.warning("Rejected GitHub webhook: request body is too large.")

    return JSONResponse(
        status_code=413,
        content={
            "detail": "Request body is too large.",
        },
    )


def build_unsupported_content_type_response() -> JSONResponse:
    logger.warning("Rejected GitHub webhook: unsupported content type.")

    return JSONResponse(
        status_code=415,
        content={
            "detail": "Content-Type must be application/json.",
        },
    )


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """
    Receive, validate, normalize, and persist GitHub workflow failures.
    """

    if not settings.webhook_secret_configured:
        return build_secret_not_configured_response()

    content_type = request.headers.get("content-type", "")

    if content_type and not content_type.split(";")[0].strip() == EXPECTED_CONTENT_TYPE:
        return build_unsupported_content_type_response()

    content_length = request.headers.get("content-length")

    if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
        return build_oversized_body_response()

    payload = await request.body()

    if len(payload) > MAX_BODY_BYTES:
        return build_oversized_body_response()

    if not verify_signature(
        payload=payload,
        secret=settings.github_webhook_secret.get_secret_value(),
        signature_header=x_hub_signature_256,
    ):
        return build_invalid_signature_response(x_github_delivery)

    if not x_github_delivery:
        return build_missing_delivery_response()

    if len(x_github_delivery) > MAX_DELIVERY_ID_LENGTH:
        return build_invalid_payload_response("X-GitHub-Delivery header is too long.")

    if x_github_event != "workflow_run":
        return build_ignored_response(
            "unsupported_event",
            x_github_delivery,
        )

    try:
        parsed_payload = parse_json_payload(payload)

        failure_event = normalize_workflow_run(
            parsed_payload,
            delivery_id=x_github_delivery,
        )
    except InvalidWebhookPayloadError as exc:
        return build_invalid_payload_response(str(exc))

    if failure_event is None:
        return build_ignored_response(
            "not_a_failed_workflow",
            x_github_delivery,
        )

    service = RepairRunService(session)

    run, created = await service.create_from_github_failure(
        failure_event,
    )

    return build_accepted_response(run, created, failure_event)
