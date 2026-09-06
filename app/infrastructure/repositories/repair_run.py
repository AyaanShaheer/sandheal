from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RunStatus
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

    async def create_from_github_failure(
        self,
        failure_event,
    ) -> tuple[RepairRun, bool]:
        """
        Create a RepairRun from a normalized GitHub failure event.

        Returns:
            (run, created)

            created=True:
                A new RepairRun was created.

            created=False:
                The GitHub delivery was already processed.

        The database UNIQUE constraint on delivery_id is the final
        authority for idempotency. IntegrityError is handled so that
        concurrent duplicate deliveries resolve to the same run.
        """

        existing = await self.get_by_delivery_id(
            failure_event.delivery_id,
        )

        if existing is not None:
            return existing, False

        run = RepairRun(
            repository=failure_event.repository,
            commit_sha=failure_event.commit_sha,
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
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
