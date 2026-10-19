from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.repair_runs import RepairRunService
from app.domain.errors import InvalidTransitionError, RunNotFoundError
from app.domain.job_enums import RepairJobStatus
from app.domain.models import RepairJob
from app.infrastructure.models.repair_job import RepairJobRecord
from app.infrastructure.models.repair_run import RepairRunRecord
from app.infrastructure.repositories.repair_job import RepairJobRepository
from app.integrations.github.models import GitHubWorkflowFailure


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


def test_new_job_starts_in_pending_state() -> None:
    job = RepairJob(run_id=uuid4())

    assert job.status is RepairJobStatus.PENDING
    assert job.attempts == 0


def test_valid_job_transition_changes_status() -> None:
    job = RepairJob(run_id=uuid4())

    job.transition_to(RepairJobStatus.PROCESSING)

    assert job.status is RepairJobStatus.PROCESSING


def test_invalid_job_transition_raises_value_error() -> None:
    job = RepairJob(run_id=uuid4())

    with pytest.raises(ValueError, match="Invalid transition"):
        job.transition_to(RepairJobStatus.COMPLETED)

    assert job.status is RepairJobStatus.PENDING


def test_failed_job_can_be_retried() -> None:
    """
    A failed job is not terminal: it can return to PENDING.
    """

    job = RepairJob(run_id=uuid4())

    job.transition_to(RepairJobStatus.PROCESSING)
    job.transition_to(RepairJobStatus.FAILED)
    job.transition_to(RepairJobStatus.PENDING)

    assert job.status is RepairJobStatus.PENDING


def test_completed_job_is_terminal() -> None:
    job = RepairJob(run_id=uuid4())

    job.transition_to(RepairJobStatus.PROCESSING)
    job.transition_to(RepairJobStatus.COMPLETED)

    with pytest.raises(ValueError, match="terminal job"):
        job.transition_to(RepairJobStatus.PENDING)

    assert job.status is RepairJobStatus.COMPLETED


def test_status_constraint_covers_every_declared_job_status() -> None:
    """
    The database constraint must allow every status the domain defines.
    """

    constraint = next(
        constraint
        for constraint in RepairJobRecord.__table__.constraints
        if constraint.name == "ck_repair_jobs_status"
    )

    constraint_sql = str(constraint.sqltext)

    for status in RepairJobStatus:
        assert f"'{status.value}'" in constraint_sql


@pytest.mark.anyio
async def test_advance_job_persists_the_new_status(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(build_failure_event())

    job = await RepairJobRepository(session).get_by_run_id(run.id)

    assert job is not None

    updated = await service.advance_job(job.id, RepairJobStatus.PROCESSING)

    assert updated.status is RepairJobStatus.PROCESSING

    stored = await RepairJobRepository(session).get_by_id(job.id)

    assert stored is not None
    assert stored.status == RepairJobStatus.PROCESSING.value


@pytest.mark.anyio
async def test_advance_job_rejects_an_invalid_transition(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    run, _ = await service.create_from_github_failure(build_failure_event())

    job = await RepairJobRepository(session).get_by_run_id(run.id)

    assert job is not None

    with pytest.raises(InvalidTransitionError):
        await service.advance_job(job.id, RepairJobStatus.COMPLETED)

    stored = await RepairJobRepository(session).get_by_id(job.id)

    assert stored is not None
    assert stored.status == RepairJobStatus.PENDING.value


@pytest.mark.anyio
async def test_advance_job_raises_for_an_unknown_job(
    session: AsyncSession,
) -> None:
    service = RepairRunService(session)

    with pytest.raises(RunNotFoundError):
        await service.advance_job(uuid4(), RepairJobStatus.PROCESSING)


@pytest.mark.anyio
async def test_database_rejects_an_unknown_job_status(
    session: AsyncSession,
) -> None:
    """
    The status column is constrained by the database, not only by the
    application.
    """

    run, _ = await RepairRunService(session).create_from_github_failure(
        build_failure_event(),
    )

    job = RepairJobRecord(
        run_id=run.id,
        status="not-a-real-status",
        attempts=0,
    )

    session.add(job)

    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()


@pytest.mark.anyio
async def test_database_rejects_an_unknown_run_status(
    session: AsyncSession,
) -> None:
    record = RepairRunRecord(
        delivery_id="invalid-status-delivery",
        status="not-a-real-status",
        repository="AyaanShaheer/test-repo",
        commit_sha="abc123",
        workflow_name="CI",
        workflow_run_id=1,
        branch="main",
        conclusion="failure",
    )

    session.add(record)

    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()


@pytest.mark.anyio
async def test_job_record_maps_to_the_domain_model(
    session: AsyncSession,
) -> None:
    run, _ = await RepairRunService(session).create_from_github_failure(
        build_failure_event(),
    )

    job = await RepairJobRepository(session).get_by_run_id(run.id)

    assert job is not None

    domain_job = RepairJobRepository._to_domain(job)

    assert domain_job.id == job.id
    assert domain_job.run_id == run.id
    assert domain_job.status is RepairJobStatus.PENDING
    assert domain_job.attempts == 0
