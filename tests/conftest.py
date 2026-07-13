from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.storage import reset_storage
from app.utils.rate_limiter import judge_rate_limiter


@pytest.fixture(autouse=True)
async def reset_state():
    """Reset in-memory storage and rate limiter before each test."""
    reset_storage()
    judge_rate_limiter.reset()
    yield


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Login as admin and return authenticated client."""
    await client.post("/api/reset/")
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admintestpassword",
    })
    assert resp.status_code == 200
    return client


@pytest.fixture
async def user_client(client: AsyncClient) -> AsyncClient:
    """Register a normal user, login, return authenticated client."""
    await client.post("/api/reset/")
    await client.post("/api/users/", json={
        "username": "student1",
        "password": "test123456",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "student1",
        "password": "test123456",
    })
    assert resp.status_code == 200
    return client
