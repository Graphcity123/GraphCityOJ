from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.storage import reset_storage


@pytest.fixture(autouse=True)
async def reset_state():
    """Reset in-memory storage before each test."""
    reset_storage()
    yield


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    return client