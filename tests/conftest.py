import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import reset_storage
from app.utils.rate_limiter import judge_rate_limiter
from app.api.admin import _create_default_admin, _register_default_languages


@pytest.fixture(scope="function")
def client():
    """Return a TestClient with clean state (admin + default languages pre-created)."""
    reset_storage()
    judge_rate_limiter.reset()
    _create_default_admin()
    _register_default_languages()
    with TestClient(app) as c:
        yield c
