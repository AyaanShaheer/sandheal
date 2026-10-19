from enum import StrEnum


class RepairJobStatus(StrEnum):
    """
    Lifecycle states for an asynchronous repair job.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATUSES: frozenset[RepairJobStatus] = frozenset(
    {
        RepairJobStatus.COMPLETED,
        RepairJobStatus.CANCELLED,
    }
)
