import json
from typing import Any

from app.domain.errors import InvalidWebhookPayloadError
from app.domain.failures import WorkflowFailure


def normalize_workflow_run(
    payload: dict[str, Any],
    *,
    delivery_id: str,
) -> WorkflowFailure | None:
    """
    Convert a GitHub workflow_run webhook payload into SandHeal's
    internal failure representation.

    Returns None when the event is valid but irrelevant to SandHeal.

    Raises:
        InvalidWebhookPayloadError: when the payload cannot be understood.
    """

    action = payload.get("action")

    if action != "completed":
        return None

    repository = payload.get("repository")
    workflow_run = payload.get("workflow_run")

    if not isinstance(repository, dict):
        raise InvalidWebhookPayloadError("Missing repository payload.")

    if not isinstance(workflow_run, dict):
        raise InvalidWebhookPayloadError("Missing workflow_run payload.")

    conclusion = workflow_run.get("conclusion")

    if conclusion != "failure":
        return None

    repository_name = repository.get("full_name")
    workflow_run_id = workflow_run.get("id")
    workflow_name = workflow_run.get("name")
    commit_sha = workflow_run.get("head_sha")
    branch = workflow_run.get("head_branch")

    if not repository_name:
        raise InvalidWebhookPayloadError("Missing repository.full_name.")

    if not workflow_run_id:
        raise InvalidWebhookPayloadError("Missing workflow_run.id.")

    if not workflow_name:
        raise InvalidWebhookPayloadError("Missing workflow_run.name.")

    if not commit_sha:
        raise InvalidWebhookPayloadError("Missing workflow_run.head_sha.")

    if not branch:
        raise InvalidWebhookPayloadError("Missing workflow_run.head_branch.")

    return WorkflowFailure(
        delivery_id=delivery_id,
        repository=repository_name,
        commit_sha=commit_sha,
        workflow_name=workflow_name,
        workflow_run_id=workflow_run_id,
        branch=branch,
        conclusion=conclusion,
    )


def parse_json_payload(payload: bytes) -> dict[str, Any]:
    """
    Parse raw webhook bytes into a JSON object.

    Raises:
        InvalidWebhookPayloadError: when the payload is not a JSON object.
    """

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InvalidWebhookPayloadError("Malformed JSON payload.") from exc

    if not isinstance(decoded, dict):
        raise InvalidWebhookPayloadError("Webhook payload must be a JSON object.")

    return decoded
