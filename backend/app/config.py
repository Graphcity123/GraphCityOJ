from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

# Auto-detect project root: go up 3 levels from app/config.py
_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "GCOJ"
    debug: bool = False
    secret_key: str = "gcoj-secret-key-change-in-production"

    problems_dir: Path = _BASE_DIR / "problems"
    work_dir: Path = _BASE_DIR / "work"

    database_url: str = f"sqlite+aiosqlite:///{_BASE_DIR}/oj.db"

    model_config = {"env_prefix": "OJ_", "env_file": ".env"}


settings = Settings()
