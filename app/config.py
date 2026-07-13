from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "OJ System"
    debug: bool = False

    problems_dir: Path = Path("/home/graphcity/oj-system/problems")
    logs_dir: Path = Path("/home/graphcity/oj-system/logs")

    database_url: str = "sqlite+aiosqlite:////home/graphcity/oj-system/oj.db"

    model_config = {"env_prefix": "OJ_", "env_file": ".env"}


settings = Settings()
