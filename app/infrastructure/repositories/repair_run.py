import warnings
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RunStatus
from app.domain.failures import WorkflowFailure
from app.domain.models import RepairRun
from app.infrastructure.models.repair_run import RepairRunRecord


class RepairRunRepository:
    """
    Persistence operations for SandHeal repair runs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_delivery_id(
        self,
        delivery_id: str,
    ) -> RepairRun | None:
        """
        Retrieve a repair run using its GitHub delivery ID.
        """

        result = await self._session.execute(
            select(RepairRunRecord).where(
                RepairRunRecord.delivery_id == delivery_id,
            )
        )

        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_domain(record)

    async def get_by_id(
        self,
        run_id: UUID,
    ) -> RepairRun | None:
        """
        Retrieve a repair run using its SandHeal ID.
        """

        result = await self._session.execute(
            select(RepairRunRecord).where(
                RepairRunRecord.id == run_id,
            )
        )

        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_domain(record)

    async def add_from_github_failure(
        self,
        failure_event: WorkflowFailure,
    ) -> RepairRun:
        """
        Add a RepairRun to the current transaction.

        This method does NOT commit.
        """

        run = RepairRun(
            repository=failure_event.repository,
            commit_sha=failure_event.commit_sha,
            delivery_id=failure_event.delivery_id,
            workflow_name=failure_event.workflow_name,
            workflow_run_id=failure_event.workflow_run_id,
            branch=failure_event.branch,
            conclusion=failure_event.conclusion,
        )

        record = RepairRunRecord(
            id=run.id,
            status=run.status.value,
            delivery_id=failure_event.delivery_id,
            repository=failure_event.repository,
            commit_sha=failure_event.commit_sha,
            workflow_name=failure_event.workflow_name,
            workflow_run_id=failure_event.workflow_run_id,
            branch=failure_event.branch,
            conclusion=failure_event.conclusion,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

        self._session.add(record)

        return run

    async def apply_status_transition(
        self,
        run_id: UUID,
        new_status: RunStatus,
    ) -> RepairRun | None:
        """
        Move a persisted repair run to a new status.

        The transition is validated by the domain model, so an illegal
        transition raises InvalidTransitionError before anything is written.

        Returns None when no run exists with the given ID.

        This method does NOT commit.
        """

        result = await self._session.execute(
            select(RepairRunRecord).where(
                RepairRunRecord.id == run_id,
            )
        )

        record = result.scalar_one_or_none()

        if record is None:
            return None

        run = self._to_domain(record)

        run.transition_to(new_status)

        record.status = run.status.value
        record.updated_at = run.updated_at

        await self._session.flush()

        return run

    async def create_from_github_failure(
        self,
        failure_event: WorkflowFailure,
    ) -> tuple[RepairRun, bool]:
        """
        Create a RepairRun independently.

        Deprecated:
            Use RepairRunService.create_from_github_failure, which creates
            the run and its first job in a single transaction. Creating a
            run on its own breaks the "RepairRun exists if and only if its
            initial RepairJob exists" invariant.
        """

        warnings.warn(
            "RepairRunRepository.create_from_github_failure is deprecated. "
            "Use RepairRunService.create_from_github_failure so the repair run "
            "and its job are created in a single transaction.",
            DeprecationWarning,
            stacklevel=2,
        )

        existing = await self.get_by_delivery_id(
            failure_event.delivery_id,
        )

        if existing is not None:
            return existing, False

        run = await self.add_from_github_failure(
            failure_event,
        )

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()

            existing = await self.get_by_delivery_id(
                failure_event.delivery_id,
            )

            if existing is None:
                raise

            return existing, False

        return run, True

    @staticmethod
    def _to_domain(
        record: RepairRunRecord,
    ) -> RepairRun:
        """
        Convert a database record into the domain model.
        """

        return RepairRun(
            id=record.id,
            status=RunStatus(record.status),
            repository=record.repository,
            commit_sha=record.commit_sha,
            delivery_id=record.delivery_id,
            workflow_name=record.workflow_name,
            workflow_run_id=record.workflow_run_id,
            branch=record.branch,
            conclusion=record.conclusion,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
