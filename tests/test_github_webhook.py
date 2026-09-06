import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.database import Base, get_session
from app.main import create_app

WEBHOOK_SECRET = "test-secret"


def sign_payload(payload: bytes) -> str:
    """
    Generate a GitHub-compatible HMAC SHA-256 signature.
    """

    digest = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def build_payload(
    *,
    conclusion: str = "failure",
    action: str = "completed",
) -> bytes:
    """
    Build a representative GitHub workflow_run payload.
    """

    payload = {
        "action": action,
        "repository": {
            "full_name": "AyaanShaheer/test-repo",
        },
        "workflow_run": {
            "id": 123456,
            "name": "CI",
            "head_sha": "abc123def456",
            "head_branch": "main",
            "conclusion": conclusion,
        },
    }

    return json.dumps(payload).encode("utf-8")


def webhook_headers(
    payload: bytes,
    *,
    event: str = "workflow_run",
    delivery_id: str = "delivery-123",
) -> dict[str, str]:
    """
    Build standard GitHub webhook headers.
    """

    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": sign_payload(payload),
    }


@pytest.fixture
def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """
    Create an isolated SQLite database for each test.

    The fixture itself is synchronous so pytest can manage it without
    requiring an async-fixture plugin. Database setup/cleanup is
    performed explicitly with asyncio.run().
    """

    async def setup_database():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={
                "check_same_thread": False,
            },
            poolclass=StaticPool,
        )

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        return engine, factory

    engine, factory = asyncio.run(setup_database())

    yield factory

    asyncio.run(engine.dispose())


def build_client(
    factory: async_sessionmaker[AsyncSession],
) -> TestClient:
    """
    Build a FastAPI test client backed by the isolated test database.
    """

    app = create_app()

    settings = get_settings()
    settings.github_webhook_secret = WEBHOOK_SECRET

    async def override_get_session() -> AsyncGenerator[
        AsyncSession,
        None,
    ]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    return TestClient(app)


def test_failed_workflow_creates_repair_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload(
        conclusion="failure",
    )

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 202

    body = response.json()

    assert body["accepted"] is True
    assert body["duplicate"] is False
    assert body["delivery_id"] == "delivery-123"
    assert body["repository"] == "AyaanShaheer/test-repo"
    assert body["commit_sha"] == "abc123def456"
    assert body["workflow_run_id"] == 123456
    assert body["run_id"]


def test_duplicate_delivery_returns_existing_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload(
        conclusion="failure",
    )

    headers = webhook_headers(
        payload,
        delivery_id="same-delivery",
    )

    first_response = client.post(
        "/webhooks/github",
        content=payload,
        headers=headers,
    )

    second_response = client.post(
        "/webhooks/github",
        content=payload,
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 200

    first_body = first_response.json()
    second_body = second_response.json()

    assert first_body["accepted"] is True
    assert first_body["duplicate"] is False

    assert second_body["accepted"] is True
    assert second_body["duplicate"] is True

    assert first_body["run_id"] == second_body["run_id"]


def test_different_deliveries_create_different_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload(
        conclusion="failure",
    )

    first_response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(
            payload,
            delivery_id="delivery-one",
        ),
    )

    second_response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(
            payload,
            delivery_id="delivery-two",
        ),
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    first_run_id = first_response.json()["run_id"]
    second_run_id = second_response.json()["run_id"]

    assert first_run_id != second_run_id


def test_successful_workflow_is_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload(
        conclusion="success",
    )

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "not_a_failed_workflow"


def test_unrelated_event_is_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload()

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(
            payload,
            event="push",
        ),
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "unsupported_event"


def test_non_completed_workflow_action_is_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload(
        action="requested",
    )

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "not_a_failed_workflow"


def test_missing_signature_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload()

    headers = webhook_headers(payload)
    headers.pop("X-Hub-Signature-256")

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=headers,
    )

    assert response.status_code == 403


def test_invalid_signature_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = build_payload()

    headers = webhook_headers(payload)
    headers["X-Hub-Signature-256"] = "sha256=invalid"

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=headers,
    )

    assert response.status_code == 403


def test_malformed_json_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = b'{"action": "completed"'

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 400


def test_missing_required_workflow_run_data_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = json.dumps(
        {
            "action": "completed",
            "repository": {
                "full_name": "AyaanShaheer/test-repo",
            },
            "workflow_run": {
                "name": "CI",
                "head_sha": "abc123",
                "head_branch": "main",
                "conclusion": "failure",
            },
        }
    ).encode("utf-8")

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 400


def test_signature_verification_works_with_unicode_payload(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_client(session_factory)

    payload = json.dumps(
        {
            "action": "completed",
            "repository": {
                "full_name": "AyaanShaheer/unicode-repo",
            },
            "workflow_run": {
                "id": 999,
                "name": "CI 🚀",
                "head_sha": "unicode123",
                "head_branch": "main",
                "conclusion": "failure",
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")

    response = client.post(
        "/webhooks/github",
        content=payload,
        headers=webhook_headers(payload),
    )

    assert response.status_code == 202
    assert response.json()["accepted"] is True
