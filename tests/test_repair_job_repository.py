from datetime import UTC
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.domain.job_enums import RepairJobStatus
from app.infrastructure.database import Base
from app.infrastructure.models.repair_job import RepairJobRecord
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


async def create_repair_run(
    session: AsyncSession,
    *,
    delivery_id: str = "delivery-123",
):
    """
    Create a RepairRun that can be used by job tests.
    """

    repository = RepairRunRepository(session)

    event = GitHubWorkflowFailure(
        delivery_id=delivery_id,
        repository="AyaanShaheer/test-repo",
        commit_sha="abc123",
        workflow_name="CI",
        workflow_run_id=12345,
        branch="main",
        conclusion="failure",
    )

    run, _ = await repository.create_from_github_failure(event)

    return run


@pytest.mark.anyio
async def test_create_pending_job(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    job = await repository.create(run.id)

    assert job.run_id == run.id
    assert job.status == RepairJobStatus.PENDING.value
    assert job.attempts == 0


@pytest.mark.anyio
async def test_job_has_unique_id(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    job = await repository.create(run.id)

    assert job.id is not None
    assert job.id != run.id


@pytest.mark.anyio
async def test_job_has_timestamps(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    job = await repository.create(run.id)

    assert job.created_at.tzinfo == UTC
    assert job.updated_at.tzinfo == UTC


@pytest.mark.anyio
async def test_get_job_by_id(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    created_job = await repository.create(run.id)

    loaded_job = await repository.get_by_id(created_job.id)

    assert loaded_job is not None
    assert loaded_job.id == created_job.id
    assert loaded_job.run_id == run.id


@pytest.mark.anyio
async def test_get_job_by_run_id(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    created_job = await repository.create(run.id)

    loaded_job = await repository.get_by_run_id(run.id)

    assert loaded_job is not None
    assert loaded_job.id == created_job.id


@pytest.mark.anyio
async def test_unknown_job_returns_none(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    await repository.create(run.id)

    missing_job = await repository.get_by_id(
        UUID("00000000-0000-0000-0000-000000000000"),
    )

    assert missing_job is None


@pytest.mark.anyio
async def test_different_runs_can_have_different_jobs(
    session: AsyncSession,
) -> None:
    first_run = await create_repair_run(
        session,
        delivery_id="delivery-one",
    )

    second_run = await create_repair_run(
        session,
        delivery_id="delivery-two",
    )

    repository = RepairJobRepository(session)

    first_job = await repository.create(first_run.id)
    second_job = await repository.create(second_run.id)

    assert first_job.id != second_job.id
    assert first_job.run_id == first_run.id
    assert second_job.run_id == second_run.id


@pytest.mark.anyio
async def test_same_run_cannot_have_two_jobs(
    session: AsyncSession,
) -> None:
    run = await create_repair_run(session)

    repository = RepairJobRepository(session)

    first_job = await repository.create(run.id)

    second_job = RepairJobRecord(
        run_id=run.id,
        status=RepairJobStatus.PENDING.value,
        attempts=0,
    )

    session.add(second_job)

    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()

    stored_job = await session.scalar(
        select(RepairJobRecord).where(
            RepairJobRecord.run_id == run.id,
        )
    )

    assert stored_job is not None
    assert stored_job.id == first_job.id
    assert stored_job.run_id == run.id
