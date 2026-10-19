from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.main import create_app


def build_client() -> TestClient:
    """
    Build a client that does not raise server exceptions.

    Starlette re-raises unhandled exceptions after sending the response, so
    a test that asserts the 500 body has to opt out of that behaviour.
    """

    return TestClient(create_app(), raise_server_exceptions=False)


def test_every_response_carries_a_request_id() -> None:
    client = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_a_supplied_request_id_is_echoed() -> None:
    client = build_client()

    response = client.get(
        "/health",
        headers={"X-Request-ID": "caller-supplied-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "caller-supplied-id"


def test_request_ids_are_unique_per_request() -> None:
    client = build_client()

    first = client.get("/health")
    second = client.get("/health")

    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_handled_errors_include_the_request_id() -> None:
    client = build_client()

    response = client.get(
        "/does-not-exist",
        headers={"X-Request-ID": "trace-me"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    assert response.json()["request_id"] == "trace-me"


def test_validation_errors_include_the_request_id() -> None:
    from pydantic import BaseModel

    class Payload(BaseModel):
        name: str

    app = create_app()

    @app.post("/validate")
    async def validate(payload: Payload) -> dict[str, str]:
        return {"name": payload.name}

    client = TestClient(app)

    response = client.post("/validate", json={})

    assert response.status_code == 422
    assert "request_id" in response.json()


def test_unhandled_errors_do_not_leak_internals() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"
    assert "secret internal detail" not in response.text


def test_unhandled_errors_still_carry_a_request_id() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom", headers={"X-Request-ID": "trace-me"})

    assert response.status_code == 500
    assert response.json()["request_id"] == "trace-me"


@pytest.mark.anyio
async def test_readiness_reports_ready_when_the_database_answers(
    session: AsyncSession,
) -> None:
    import httpx

    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.anyio
async def test_readiness_reports_unavailable_when_the_database_fails() -> None:
    import httpx

    class FailingSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("database is down")

    app = create_app()

    async def override_get_session() -> AsyncGenerator[object, None]:
        yield FailingSession()

    app.dependency_overrides[get_session] = override_get_session

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
