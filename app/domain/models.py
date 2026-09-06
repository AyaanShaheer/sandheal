from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.enums import TERMINAL_STATUSES, RunStatus

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


class RepairRun(BaseModel):
    """
    Core domain object representing one SandHeal repair execution.
    """

    id: UUID = Field(default_factory=uuid4)
    status: RunStatus = RunStatus.RECEIVED

    repository: str | None = None
    commit_sha: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: RunStatus) -> None:
        """
        Move the repair run to a valid next state.

        Raises:
            ValueError: if the transition is not permitted.
        """
        if self.status in TERMINAL_STATUSES:
            raise ValueError(
                f"Cannot transition terminal run from '{self.status}' to '{new_status}'."
            )

        allowed_states = ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed_states:
            raise ValueError(f"Invalid transition from '{self.status}' to '{new_status}'.")

        self.status = new_status
        self.updated_at = datetime.now(UTC)
