import json

import pytest

from app.domain.errors import InvalidWebhookPayloadError
from app.domain.failures import WorkflowFailure
from app.integrations.github.webhook import (
    normalize_workflow_run,
    parse_json_payload,
)


def build_payload(
    *,
    action: str = "completed",
    conclusion: str = "failure",
    repository: dict[str, object] | None = None,
    workflow_run: dict[str, object] | None = None,
) -> dict[str, object]:
    """
    Build a representative GitHub workflow_run payload.
    """

    payload: dict[str, object] = {"action": action}

    if repository is not None:
        payload["repository"] = repository

    if workflow_run is not None:
        payload["workflow_run"] = {**workflow_run, "conclusion": conclusion}

    return payload


VALID_REPOSITORY = {"full_name": "AyaanShaheer/test-repo"}
VALID_WORKFLOW_RUN = {
    "id": 123456,
    "name": "CI",
    "head_sha": "abc123",
    "head_branch": "main",
    "conclusion": "failure",
}


def test_valid_payload_is_normalized() -> None:
    failure = normalize_workflow_run(
        build_payload(repository=VALID_REPOSITORY, workflow_run=VALID_WORKFLOW_RUN),
        delivery_id="delivery-123",
    )

    assert isinstance(failure, WorkflowFailure)
    assert failure.delivery_id == "delivery-123"
    assert failure.repository == "AyaanShaheer/test-repo"
    assert failure.commit_sha == "abc123"
    assert failure.workflow_name == "CI"
    assert failure.workflow_run_id == 123456
    assert failure.branch == "main"
    assert failure.conclusion == "failure"


def test_incomplete_action_is_ignored() -> None:
    assert (
        normalize_workflow_run(
            build_payload(
                action="requested",
                repository=VALID_REPOSITORY,
                workflow_run=VALID_WORKFLOW_RUN,
            ),
            delivery_id="delivery-123",
        )
        is None
    )


def test_successful_workflow_is_ignored() -> None:
    assert (
        normalize_workflow_run(
            build_payload(
                conclusion="success",
                repository=VALID_REPOSITORY,
                workflow_run=VALID_WORKFLOW_RUN,
            ),
            delivery_id="delivery-123",
        )
        is None
    )


def test_missing_repository_is_rejected() -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        normalize_workflow_run(
            build_payload(workflow_run=VALID_WORKFLOW_RUN),
            delivery_id="delivery-123",
        )

    assert str(error.value) == "Missing repository payload."


def test_missing_workflow_run_is_rejected() -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        normalize_workflow_run(
            build_payload(repository=VALID_REPOSITORY),
            delivery_id="delivery-123",
        )

    assert str(error.value) == "Missing workflow_run payload."


@pytest.mark.parametrize(
    ("workflow_run", "expected_detail"),
    [
        (
            {**VALID_WORKFLOW_RUN, "id": None},
            "Missing workflow_run.id.",
        ),
        (
            {**VALID_WORKFLOW_RUN, "name": None},
            "Missing workflow_run.name.",
        ),
        (
            {**VALID_WORKFLOW_RUN, "head_sha": None},
            "Missing workflow_run.head_sha.",
        ),
        (
            {**VALID_WORKFLOW_RUN, "head_branch": None},
            "Missing workflow_run.head_branch.",
        ),
    ],
)
def test_missing_workflow_run_fields_are_rejected(
    workflow_run: dict[str, object],
    expected_detail: str,
) -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        normalize_workflow_run(
            build_payload(repository=VALID_REPOSITORY, workflow_run=workflow_run),
            delivery_id="delivery-123",
        )

    assert str(error.value) == expected_detail


def test_missing_repository_full_name_is_rejected() -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        normalize_workflow_run(
            build_payload(
                repository={"full_name": None},
                workflow_run=VALID_WORKFLOW_RUN,
            ),
            delivery_id="delivery-123",
        )

    assert str(error.value) == "Missing repository.full_name."


def test_valid_json_object_is_parsed() -> None:
    payload = parse_json_payload(json.dumps({"action": "completed"}).encode())

    assert payload == {"action": "completed"}


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        parse_json_payload(b'{"action": "completed"')

    assert str(error.value) == "Malformed JSON payload."


def test_non_object_json_is_rejected() -> None:
    with pytest.raises(InvalidWebhookPayloadError) as error:
        parse_json_payload(b"[1, 2, 3]")

    assert str(error.value) == "Webhook payload must be a JSON object."
