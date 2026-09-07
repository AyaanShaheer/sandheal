from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_session
from app.infrastructure.repositories.repair_run import RepairRunRepository
from app.integrations.github.security import verify_signature
from app.integrations.github.webhook import (
    normalize_workflow_run,
    parse_json_payload,
)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """
    Receive, validate, normalize, and persist GitHub workflow failures.
    """

    settings = get_settings()

    payload = await request.body()

    if not verify_signature(
        payload=payload,
        secret=settings.github_webhook_secret,
        signature_header=x_hub_signature_256,
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Invalid webhook signature.",
            },
        )

    if not x_github_delivery:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Missing X-GitHub-Delivery header.",
            },
        )

    parsed_payload = parse_json_payload(payload)

    if x_github_event != "workflow_run":
        return JSONResponse(
            status_code=200,
            content={
                "accepted": False,
                "reason": "unsupported_event",
                "delivery_id": x_github_delivery,
            },
        )

    failure_event = normalize_workflow_run(
        parsed_payload,
        delivery_id=x_github_delivery,
    )

    if failure_event is None:
        return JSONResponse(
            status_code=200,
            content={
                "accepted": False,
                "reason": "not_a_failed_workflow",
                "delivery_id": x_github_delivery,
            },
        )

    repository = RepairRunRepository(session)

    run, created = await repository.create_from_github_failure(
        failure_event,
    )

    if not created:
        return JSONResponse(
            status_code=200,
            content={
                "accepted": True,
                "duplicate": True,
                "delivery_id": failure_event.delivery_id,
                "run_id": str(run.id),
            },
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
