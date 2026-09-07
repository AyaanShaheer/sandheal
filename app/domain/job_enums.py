from enum import StrEnum


class RepairJobStatus(StrEnum):
    """
    Lifecycle states for an asynchronous repair job.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
