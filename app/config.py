from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "OJ System"
    debug: bool = False
    secret_key: str = "oj-system-secret-key-change-in-production"

    problems_dir: Path = Path("/home/graphcity/oj-system/problems")
    logs_dir: Path = Path("/home/graphcity/oj-system/logs")
    work_dir: Path = Path("/home/graphcity/oj-system/work")

    database_url: str = "sqlite+aiosqlite:////home/graphcity/oj-system/oj.db"

    model_config = {"env_prefix": "OJ_", "env_file": ".env"}


settings = Settings()
