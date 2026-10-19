import warnings
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.job_enums import RepairJobStatus
from app.domain.models import RepairJob
from app.infrastructure.models.repair_job import RepairJobRecord


class RepairJobRepository:
    """
    Persistence operations for asynchronous repair jobs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        job_id: UUID,
    ) -> RepairJobRecord | None:
        """
        Retrieve a repair job by its ID.
        """

        result = await self._session.execute(
            select(RepairJobRecord).where(
                RepairJobRecord.id == job_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_run_id(
        self,
        run_id: UUID,
    ) -> RepairJobRecord | None:
        """
        Retrieve the repair job associated with a repair run.
        """

        result = await self._session.execute(
            select(RepairJobRecord).where(
                RepairJobRecord.run_id == run_id,
            )
        )

        return result.scalar_one_or_none()

    async def add_pending(
        self,
        run_id: UUID,
    ) -> RepairJobRecord:
        """
        Add a pending RepairJob to the current transaction.

        This method does NOT commit.
        """

        job = RepairJobRecord(
            run_id=run_id,
            status=RepairJobStatus.PENDING.value,
            attempts=0,
        )

        self._session.add(job)

        return job

    async def apply_status_transition(
        self,
        job_id: UUID,
        new_status: RepairJobStatus,
    ) -> RepairJob | None:
        """
        Move a persisted repair job to a new status.

        The transition is validated by the domain model, so an illegal
        transition raises InvalidTransitionError before anything is written.

        Returns None when no job exists with the given ID.

        This method does NOT commit.
        """

        result = await self._session.execute(
            select(RepairJobRecord).where(
                RepairJobRecord.id == job_id,
            )
        )

        record = result.scalar_one_or_none()

        if record is None:
            return None

        job = self._to_domain(record)

        job.transition_to(new_status)

        record.status = job.status.value
        record.updated_at = job.updated_at

        await self._session.flush()

        return job

    async def create(
        self,
        run_id: UUID,
    ) -> RepairJobRecord:
        """
        Create a pending asynchronous repair job independently.

        Deprecated:
            Use RepairRunService.create_from_github_failure, which creates
            the run and its first job in a single transaction. Creating a
            job on its own breaks the "RepairRun exists if and only if its
            initial RepairJob exists" invariant.
        """

        warnings.warn(
            "RepairJobRepository.create is deprecated. "
            "Use RepairRunService.create_from_github_failure so the repair run "
            "and its job are created in a single transaction.",
            DeprecationWarning,
            stacklevel=2,
        )

        job = await self.add_pending(run_id)

        await self._session.commit()

        return job

    @staticmethod
    def _to_domain(
        record: RepairJobRecord,
    ) -> RepairJob:
        """
        Convert a database record into the domain model.
        """

        return RepairJob(
            id=record.id,
            run_id=record.run_id,
            status=RepairJobStatus(record.status),
            attempts=record.attempts,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
