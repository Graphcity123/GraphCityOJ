import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import reset_storage
from app.utils.rate_limiter import judge_rate_limiter
from app.api.admin import _create_default_admin, _register_default_languages


@pytest.fixture(scope="function")
def client():
    """Return a TestClient with clean state."""
    async def _setup():
        await reset_storage()
        await _create_default_admin()
        await _register_default_languages()

    asyncio.run(_setup())
    judge_rate_limiter.reset()

    with TestClient(app) as c:
        yield c
