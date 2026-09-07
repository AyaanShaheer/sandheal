from datetime import UTC
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import Base
from app.infrastructure.repositories.repair_run import (
    RepairRunRepository,
)
from app.integrations.github.models import GitHubWorkflowFailure


@pytest.fixture
async def session() -> AsyncSession:
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
async def test_create_failure_run(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    run, created = await repository.create_from_github_failure(build_failure_event())

    assert created is True
    assert isinstance(run.id, UUID)
    assert run.status.value == "received"
    assert run.repository == "AyaanShaheer/test-repo"
    assert run.commit_sha == "abc123"


@pytest.mark.anyio
async def test_created_run_has_utc_timestamps(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    run, _ = await repository.create_from_github_failure(build_failure_event())

    assert run.created_at.tzinfo == UTC
    assert run.updated_at.tzinfo == UTC


@pytest.mark.anyio
async def test_get_by_delivery_id(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    created_run, _ = await repository.create_from_github_failure(
        build_failure_event(delivery_id="delivery-456")
    )

    loaded_run = await repository.get_by_delivery_id("delivery-456")

    assert loaded_run is not None
    assert loaded_run.id == created_run.id


@pytest.mark.anyio
async def test_get_by_id(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    created_run, _ = await repository.create_from_github_failure(build_failure_event())

    loaded_run = await repository.get_by_id(created_run.id)

    assert loaded_run is not None
    assert loaded_run.id == created_run.id


@pytest.mark.anyio
async def test_duplicate_delivery_is_idempotent(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    first_run, first_created = await repository.create_from_github_failure(
        build_failure_event(delivery_id="delivery-same")
    )

    second_run, second_created = await repository.create_from_github_failure(
        build_failure_event(delivery_id="delivery-same")
    )

    assert first_created is True
    assert second_created is False

    assert second_run.id == first_run.id


@pytest.mark.anyio
async def test_different_deliveries_create_different_runs(
    session: AsyncSession,
) -> None:
    repository = RepairRunRepository(session)

    first_run, _ = await repository.create_from_github_failure(
        build_failure_event(delivery_id="delivery-one")
    )

    second_run, _ = await repository.create_from_github_failure(
        build_failure_event(delivery_id="delivery-two")
    )

    assert first_run.id != second_run.id


@pytest.mark.asyncio
@pytest.mark.anyio
async def test_concurrent_duplicate_delivery_is_idempotent(
    session: AsyncSession,
) -> None:
    """
    Verify that the database uniqueness constraint protects against
    duplicate creation when two repository operations race.

    This test uses two sessions against the same database.
    """

    engine = session.bind

    if engine is None:
        raise AssertionError("Test session has no bound engine.")

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    first_session = session_factory()
    second_session = session_factory()

    try:
        first_repository = RepairRunRepository(first_session)
        second_repository = RepairRunRepository(second_session)

        event = build_failure_event(
            delivery_id="concurrent-delivery",
        )

        first_existing = await first_repository.get_by_delivery_id(
            event.delivery_id,
        )
        second_existing = await second_repository.get_by_delivery_id(
            event.delivery_id,
        )

        assert first_existing is None
        assert second_existing is None

        first_run, first_created = await first_repository.create_from_github_failure(
            event,
        )

        second_run, second_created = await second_repository.create_from_github_failure(
            event,
        )

        assert first_created is True
        assert second_created is False
        assert first_run.id == second_run.id

    finally:
        await first_session.close()
        await second_session.close()
