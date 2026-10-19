from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RunStatus
from app.domain.errors import RunNotFoundError
from app.domain.failures import WorkflowFailure
from app.domain.job_enums import RepairJobStatus
from app.domain.models import RepairJob, RepairRun
from app.infrastructure.repositories.repair_job import (
    RepairJobRepository,
)
from app.infrastructure.repositories.repair_run import (
    RepairRunRepository,
)


class RepairRunService:
    """
    Application-level orchestration for creating and managing
    RepairRuns and their associated jobs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repair_runs = RepairRunRepository(session)
        self._repair_jobs = RepairJobRepository(session)

    async def create_from_github_failure(
        self,
        failure_event: WorkflowFailure,
    ) -> tuple[RepairRun, bool]:
        """
        Atomically create a RepairRun and its first pending RepairJob.

        Returns:
            (run, created)

            created=True:
                New RepairRun and RepairJob committed.

            created=False:
                Delivery already existed; no new records created.
        """

        existing = await self._repair_runs.get_by_delivery_id(
            failure_event.delivery_id,
        )

        if existing is not None:
            return existing, False

        try:
            run = await self._repair_runs.add_from_github_failure(
                failure_event,
            )

            await self._repair_jobs.add_pending(
                run.id,
            )

            await self._session.commit()

            return run, True

        except IntegrityError:
            await self._session.rollback()

            existing = await self._repair_runs.get_by_delivery_id(
                failure_event.delivery_id,
            )

            if existing is None:
                raise

            return existing, False

        except Exception:
            await self._session.rollback()
            raise

    async def advance_run(
        self,
        run_id: UUID,
        new_status: RunStatus,
    ) -> RepairRun:
        """
        Move a persisted repair run to the next lifecycle state.

        The transition is validated by the domain state machine, so an
        illegal transition raises InvalidTransitionError and leaves the
        stored run untouched.

        Returns:
            The updated RepairRun.

        Raises:
            RunNotFoundError: when no run exists with the given ID.
            InvalidTransitionError: when the transition is not permitted.
        """

        run = await self._repair_runs.apply_status_transition(
            run_id,
            new_status,
        )

        if run is None:
            raise RunNotFoundError(f"Repair run '{run_id}' does not exist.")

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return run

    async def advance_job(
        self,
        job_id: UUID,
        new_status: RepairJobStatus,
    ) -> RepairJob:
        """
        Move a persisted repair job to the next lifecycle state.

        The transition is validated by the domain state machine, so an
        illegal transition raises InvalidTransitionError and leaves the
        stored job untouched.

        Returns:
            The updated RepairJob.

        Raises:
            RunNotFoundError: when no job exists with the given ID.
            InvalidTransitionError: when the transition is not permitted.
        """

        job = await self._repair_jobs.apply_status_transition(
            job_id,
            new_status,
        )

        if job is None:
            raise RunNotFoundError(f"Repair job '{job_id}' does not exist.")

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return job
