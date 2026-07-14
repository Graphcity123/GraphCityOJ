from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "GCOJ"
    debug: bool = False
    secret_key: str = "gcoj-secret-key-change-in-production"

    problems_dir: Path = Path("/home/graphcity/GCOJ/backend/problems")
    work_dir: Path = Path("/home/graphcity/GCOJ/backend/work")

    database_url: str = (
        "sqlite+aiosqlite:////home/graphcity/GCOJ/backend/oj.db"
    )

    model_config = {"env_prefix": "OJ_", "env_file": ".env"}


settings = Settings()
