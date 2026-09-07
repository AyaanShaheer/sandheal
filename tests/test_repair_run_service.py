import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.application.repair_runs import RepairRunService
from app.domain.job_enums import RepairJobStatus
from app.infrastructure.database import Base
from app.infrastructure.repositories.repair_job import RepairJobRepository
from app.infrastructure.repositories.repair_run import RepairRunRepository
from app.integrations.github.models import GitHubWorkflowFailure


@pytest.fixture
async def session() -> AsyncSession:
    """
    Create an isolated in-memory database for each test.
    """

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


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
