from datetime import UTC
from uuid import UUID

import pytest

from app.domain.enums import RunStatus
from app.domain.models import RepairRun


def test_new_run_starts_in_received_state() -> None:
    run = RepairRun()

    assert run.status == RunStatus.RECEIVED


def test_new_run_has_unique_id() -> None:
    run_one = RepairRun()
    run_two = RepairRun()

    assert run_one.id != run_two.id
    assert isinstance(run_one.id, UUID)


def test_new_run_has_utc_timestamps() -> None:
    run = RepairRun()

    assert run.created_at.tzinfo == UTC
    assert run.updated_at.tzinfo == UTC


def test_valid_transition_changes_status() -> None:
    run = RepairRun()

    run.transition_to(RunStatus.REPRODUCING)

    assert run.status == RunStatus.REPRODUCING


def test_invalid_transition_raises_value_error() -> None:
    run = RepairRun()

    with pytest.raises(ValueError, match="Invalid transition"):
        run.transition_to(RunStatus.VERIFYING)


def test_invalid_transition_does_not_mutate_state() -> None:
    run = RepairRun()

    with pytest.raises(ValueError):
        run.transition_to(RunStatus.VERIFYING)

    assert run.status == RunStatus.RECEIVED


@pytest.mark.parametrize(
    "terminal_status",
    [
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    ],
)
def test_terminal_states_cannot_transition(
    terminal_status: RunStatus,
) -> None:
    run = RepairRun()

    run.status = terminal_status

    with pytest.raises(ValueError, match="terminal run"):
        run.transition_to(RunStatus.ANALYZING)

    assert run.status == terminal_status


def test_verification_can_return_to_execution() -> None:
    run = RepairRun()

    run.transition_to(RunStatus.REPRODUCING)
    run.transition_to(RunStatus.ANALYZING)
    run.transition_to(RunStatus.GENERATING_REPAIRS)
    run.transition_to(RunStatus.EXECUTING)
    run.transition_to(RunStatus.VERIFYING)
    run.transition_to(RunStatus.EXECUTING)

    assert run.status == RunStatus.EXECUTING


def test_repository_and_commit_are_optional() -> None:
    run = RepairRun()

    assert run.repository is None
    assert run.commit_sha is None


def test_repository_and_commit_can_be_set() -> None:
    run = RepairRun(
        repository="AyaanShaheer/example",
        commit_sha="abc123",
    )

    assert run.repository == "AyaanShaheer/example"
    assert run.commit_sha == "abc123"


def test_run_serializes_to_json() -> None:
    run = RepairRun(
        repository="AyaanShaheer/example",
        commit_sha="abc123",
    )

    payload = run.model_dump(mode="json")

    assert payload["status"] == "received"
    assert payload["repository"] == "AyaanShaheer/example"
    assert payload["commit_sha"] == "abc123"
    assert isinstance(payload["id"], str)
