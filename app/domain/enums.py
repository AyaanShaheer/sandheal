from enum import StrEnum


class RunStatus(StrEnum):
    """
    Lifecycle states for a SandHeal repair run.
    """

    RECEIVED = "received"
    REPRODUCING = "reproducing"
    ANALYZING = "analyzing"
    RESEARCHING = "researching"
    GENERATING_REPAIRS = "generating_repairs"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    CREATING_PR = "creating_pr"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    }
)
