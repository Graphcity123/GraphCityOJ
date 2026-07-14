import asyncio
import os

import pytest
from fastapi.testclient import TestClient

# Use a separate test database so tests don't pollute the production DB
os.environ["OJ_DATABASE_URL"] = (
    "sqlite+aiosqlite:////home/graphcity/GCOJ/backend/test_oj.db"
)

from app.main import app  # noqa: E402
from app.storage import reset_storage  # noqa: E402
from app.utils.rate_limiter import judge_rate_limiter  # noqa: E402
from app.api.admin import _create_default_admin, _register_default_languages  # noqa: E402


@pytest.fixture(scope="function")
def client():
    """Return a TestClient with clean state (isolated test DB)."""
    async def _setup():
        await reset_storage()
        await _create_default_admin()
        await _register_default_languages()

    asyncio.run(_setup())
    judge_rate_limiter.reset()

    with TestClient(app) as c:
        yield c
