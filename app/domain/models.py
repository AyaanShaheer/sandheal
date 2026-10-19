from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.enums import TERMINAL_STATUSES, RunStatus
from app.domain.errors import InvalidTransitionError
from app.domain.job_enums import TERMINAL_JOB_STATUSES, RepairJobStatus

ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.RECEIVED: frozenset(
        {
            RunStatus.REPRODUCING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.REPRODUCING: frozenset(
        {
            RunStatus.ANALYZING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.ANALYZING: frozenset(
        {
            RunStatus.RESEARCHING,
            RunStatus.GENERATING_REPAIRS,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.RESEARCHING: frozenset(
        {
            RunStatus.GENERATING_REPAIRS,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.GENERATING_REPAIRS: frozenset(
        {
            RunStatus.EXECUTING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.EXECUTING: frozenset(
        {
            RunStatus.VERIFYING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.VERIFYING: frozenset(
        {
            RunStatus.CREATING_PR,
            RunStatus.EXECUTING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.CREATING_PR: frozenset(
        {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

JOB_ALLOWED_TRANSITIONS: dict[RepairJobStatus, frozenset[RepairJobStatus]] = {
    RepairJobStatus.PENDING: frozenset(
        {
            RepairJobStatus.PROCESSING,
            RepairJobStatus.FAILED,
            RepairJobStatus.CANCELLED,
        }
    ),
    RepairJobStatus.PROCESSING: frozenset(
        {
            RepairJobStatus.COMPLETED,
            RepairJobStatus.FAILED,
            RepairJobStatus.PENDING,
            RepairJobStatus.CANCELLED,
        }
    ),
    RepairJobStatus.FAILED: frozenset(
        {
            RepairJobStatus.PENDING,
            RepairJobStatus.CANCELLED,
        }
    ),
    RepairJobStatus.COMPLETED: frozenset(),
    RepairJobStatus.CANCELLED: frozenset(),
}


class RepairRun(BaseModel):
    """
    Core domain object representing one SandHeal repair execution.
    """

    id: UUID = Field(default_factory=uuid4)
    status: RunStatus = RunStatus.RECEIVED

    repository: str | None = None
    commit_sha: str | None = None

    delivery_id: str | None = None
    workflow_name: str | None = None
    workflow_run_id: int | None = None
    branch: str | None = None
    conclusion: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: RunStatus) -> None:
        """
        Move the repair run to a valid next state.

        Raises:
            InvalidTransitionError: if the transition is not permitted.
                This is a ValueError subclass, so existing handling of
                ValueError keeps working.
        """
        if self.status in TERMINAL_STATUSES:
            raise InvalidTransitionError(
                f"Cannot transition terminal run from '{self.status}' to '{new_status}'."
            )

        allowed_states = ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed_states:
            raise InvalidTransitionError(
                f"Invalid transition from '{self.status}' to '{new_status}'."
            )

        self.status = new_status
        self.updated_at = datetime.now(UTC)


class RepairJob(BaseModel):
    """
    Core domain object representing one asynchronous repair job.
    """

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID

    status: RepairJobStatus = RepairJobStatus.PENDING
    attempts: int = 0

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: RepairJobStatus) -> None:
        """
        Move the repair job to a valid next state.

        A failed job is not terminal: it can be moved back to PENDING so
        the worker can retry it.

        Raises:
            InvalidTransitionError: if the transition is not permitted.
                This is a ValueError subclass, so existing handling of
                ValueError keeps working.
        """
        if self.status in TERMINAL_JOB_STATUSES:
            raise InvalidTransitionError(
                f"Cannot transition terminal job from '{self.status}' to '{new_status}'."
            )

        allowed_states = JOB_ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed_states:
            raise InvalidTransitionError(
                f"Invalid transition from '{self.status}' to '{new_status}'."
            )

        self.status = new_status
        self.updated_at = datetime.now(UTC)
