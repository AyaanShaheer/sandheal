import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.application.repair_runs import RepairRunService
from app.domain.enums import RunStatus
from app.domain.errors import InvalidTransitionError, RunNotFoundError
from app.domain.job_enums import RepairJobStatus
from app.domain.models import RepairRun
from app.infrastructure.database import Base
from app.infrastructure.models.repair_job import RepairJobRecord
from app.infrastructure.models.repair_run import RepairRunRecord
from app.infrastructure.repositories.repair_job import RepairJobRepository
from app.infrastructure.repositories.repair_run import RepairRunRepository
from app.integrations.github.models import GitHubWorkflowFailure


def build_failure_event(
    *,
    delivery_id: str = "delivery-123",
) -> GitHubWorkflowFailure:
    """
    Build a representative GitHub failure event.
    """

    return GitHubWorkflowFailure(
        delivery_id=delivery_id,
        repository="AyaanShaheer/test-repo",
        commit_sha="abc123",
        workflow_name="CI",
        workflow_run_id=12345,
        branch="main",
        conclusion="failure",
    )


@pytest.mark.anyio
async def test_creates_run_and_job_atomically(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, created = await service.create_from_github_failure(
        build_failure_event(),
    )

    assert created is True
    assert run.status.value == "received"

    job_repository = RepairJobRepository(session)

    job = await job_repository.get_by_run_id(run.id)

    assert job is not None
    assert job.run_id == run.id
    assert job.status == RepairJobStatus.PENDING.value
    assert job.attempts == 0


@pytest.mark.anyio
async def test_duplicate_delivery_does_not_create_second_job(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    event = build_failure_event(
        delivery_id="same-delivery",
    )

    first_run, first_created = await service.create_from_github_failure(event)

    second_run, second_created = await service.create_from_github_failure(event)

    assert first_created is True
    assert second_created is False
    assert first_run.id == second_run.id

    job_repository = RepairJobRepository(session)

    job = await job_repository.get_by_run_id(first_run.id)

    assert job is not None


@pytest.mark.anyio
async def test_different_deliveries_create_separate_run_and_job(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    first_run, first_created = await service.create_from_github_failure(
        build_failure_event(
            delivery_id="delivery-one",
        ),
    )

    second_run, second_created = await service.create_from_github_failure(
        build_failure_event(
            delivery_id="delivery-two",
        ),
    )

    assert first_created is True
    assert second_created is True
    assert first_run.id != second_run.id

    job_repository = RepairJobRepository(session)

    first_job = await job_repository.get_by_run_id(first_run.id)
    second_job = await job_repository.get_by_run_id(second_run.id)

    assert first_job is not None
    assert second_job is not None

    assert first_job.id != second_job.id


@pytest.mark.anyio
async def test_failed_transaction_does_not_leave_partial_job(
    session: AsyncSession,
) -> None:
    """
    Verify that a transaction rollback removes uncommitted records.

    This test manually creates both records in the same transaction,
    then rolls the transaction back.
    """

    run_repository = RepairRunRepository(session)
    job_repository = RepairJobRepository(session)

    event = build_failure_event(
        delivery_id="rollback-delivery",
    )

    run = await run_repository.add_from_github_failure(event)

    await job_repository.add_pending(run.id)

    await session.rollback()

    stored_run = await run_repository.get_by_delivery_id(
        "rollback-delivery",
    )

    stored_job = await job_repository.get_by_run_id(run.id)

    assert stored_run is None
    assert stored_job is None


@pytest.mark.anyio
async def test_created_run_keeps_the_workflow_metadata(
    session: AsyncSession,
) -> None:
    """
    The domain object must carry everything the persistence record holds,
    so later phases can work from a stored run instead of a webhook payload.
    """

    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(
        build_failure_event(),
    )

    assert run.delivery_id == "delivery-123"
    assert run.workflow_name == "CI"
    assert run.workflow_run_id == 12345
    assert run.branch == "main"
    assert run.conclusion == "failure"

    stored = await RepairRunRepository(session).get_by_delivery_id(
        "delivery-123",
    )

    assert stored is not None
    assert stored.delivery_id == "delivery-123"
    assert stored.workflow_name == "CI"
    assert stored.workflow_run_id == 12345
    assert stored.branch == "main"
    assert stored.conclusion == "failure"


@pytest.mark.anyio
async def test_advance_run_persists_the_new_status(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(
        build_failure_event(),
    )

    updated = await service.advance_run(
        run.id,
        RunStatus.REPRODUCING,
    )

    assert updated.status is RunStatus.REPRODUCING
    assert updated.updated_at >= run.updated_at

    stored = await RepairRunRepository(session).get_by_delivery_id(
        "delivery-123",
    )

    assert stored is not None
    assert stored.status is RunStatus.REPRODUCING


@pytest.mark.anyio
async def test_advance_run_walks_the_whole_lifecycle(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(
        build_failure_event(),
    )

    for status in (
        RunStatus.REPRODUCING,
        RunStatus.ANALYZING,
        RunStatus.RESEARCHING,
        RunStatus.GENERATING_REPAIRS,
        RunStatus.EXECUTING,
        RunStatus.VERIFYING,
        RunStatus.CREATING_PR,
        RunStatus.COMPLETED,
    ):
        run = await service.advance_run(run.id, status)

    assert run.status is RunStatus.COMPLETED

    stored = await RepairRunRepository(session).get_by_delivery_id(
        "delivery-123",
    )

    assert stored is not None
    assert stored.status is RunStatus.COMPLETED


@pytest.mark.anyio
async def test_advance_run_rejects_an_invalid_transition(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(
        build_failure_event(),
    )

    with pytest.raises(InvalidTransitionError):
        await service.advance_run(
            run.id,
            RunStatus.VERIFYING,
        )

    stored = await RepairRunRepository(session).get_by_delivery_id(
        "delivery-123",
    )

    assert stored is not None
    assert stored.status is RunStatus.RECEIVED


@pytest.mark.anyio
async def test_advance_run_raises_for_an_unknown_run(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    with pytest.raises(RunNotFoundError):
        await service.advance_run(
            uuid4(),
            RunStatus.REPRODUCING,
        )


@pytest.mark.anyio
async def test_service_recovers_when_a_competing_writer_wins_the_race(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Force the unique-constraint race to prove the recovery path works.

    The pre-check is made to miss the row that a competing writer already
    committed, so the insert fails on the UNIQUE(delivery_id) constraint and
    the service has to recover from the IntegrityError.
    """

    event = build_failure_event(
        delivery_id="raced-delivery",
    )

    existing_run = await RepairRunRepository(session).add_from_github_failure(
        event,
    )

    await session.commit()

    original_get_by_delivery_id = RepairRunRepository.get_by_delivery_id
    call_count = {"value": 0}

    async def flaky_get_by_delivery_id(
        self: RepairRunRepository,
        delivery_id: str,
    ) -> RepairRun | None:
        call_count["value"] += 1

        if call_count["value"] == 1:
            return None

        return await original_get_by_delivery_id(self, delivery_id)

    monkeypatch.setattr(
        RepairRunRepository,
        "get_by_delivery_id",
        flaky_get_by_delivery_id,
    )

    service = RepairRunService(session)

    run, created = await service.create_from_github_failure(event)

    assert created is False
    assert run.id == existing_run.id

    job_count = await session.scalar(
        select(func.count()).select_from(RepairJobRecord),
    )

    assert job_count == 0


@pytest.mark.anyio
async def test_concurrent_duplicate_delivery_creates_one_run_and_one_job(
    concurrent_engine: AsyncEngine,
) -> None:
    """
    Two genuinely concurrent deliveries of the same failure must produce
    exactly one repair run and exactly one repair job.
    """

    async with concurrent_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        concurrent_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    first_session = session_factory()
    second_session = session_factory()

    first_service = RepairRunService(first_session)
    second_service = RepairRunService(second_session)

    event = build_failure_event(
        delivery_id="concurrent-service-delivery",
    )

    try:
        first_result, second_result = await asyncio.gather(
            first_service.create_from_github_failure(event),
            second_service.create_from_github_failure(event),
        )

        first_run, first_created = first_result
        second_run, second_created = second_result

        assert first_created is not second_created
        assert first_run.id == second_run.id

        async with session_factory() as session:
            run_count = await session.scalar(
                select(func.count()).select_from(RepairRunRecord),
            )

            job_count = await session.scalar(
                select(func.count()).select_from(RepairJobRecord),
            )

        assert run_count == 1
        assert job_count == 1

    finally:
        await first_session.close()
        await second_session.close()
