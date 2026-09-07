from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.job_enums import RepairJobStatus
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

    async def create(
        self,
        run_id: UUID,
    ) -> RepairJobRecord:
        """
        Create a pending asynchronous repair job independently.

        This method retains the original behavior for callers that
        explicitly want a standalone RepairJob creation.
        """

        job = await self.add_pending(run_id)

        await self._session.commit()

        return job
