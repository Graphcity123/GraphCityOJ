from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class TestCase(BaseModel):
    id: int
    score: float = 100.0
    input_file: Path | None = None
    output_file: Path | None = None


class ProblemConfig(BaseModel):
    id: str
    title: str
    description: str = ""
    time_limit_ms: int = Field(default=1000, ge=100, le=30000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)

    model_config = {"extra": "forbid"}


class JudgeConfig(BaseModel):
    compare_mode: str = "exact"
    language: str = "python"

    @field_validator("compare_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = {"exact", "ignore_space", "special"}
        if v not in allowed:
            msg = f"compare_mode must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v

    model_config = {"extra": "forbid"}


class Problem(BaseModel):
    problem: ProblemConfig
    judge: JudgeConfig
    testcases: list[TestCase] = []
