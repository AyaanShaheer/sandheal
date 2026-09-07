from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import RepairRun
from app.infrastructure.repositories.repair_job import (
    RepairJobRepository,
)
from app.infrastructure.repositories.repair_run import (
    RepairRunRepository,
)
from app.integrations.github.models import GitHubWorkflowFailure


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
        failure_event: GitHubWorkflowFailure,
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
