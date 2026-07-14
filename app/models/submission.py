from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class JudgeStatus(str, Enum):
    pending = "pending"
    running = "running"
    accepted = "accepted"
    wrong_answer = "wrong_answer"
    time_limit_exceeded = "time_limit_exceeded"
    memory_limit_exceeded = "memory_limit_exceeded"
    runtime_error = "runtime_error"
    compile_error = "compile_error"


class Submission(BaseModel):
    id: str
    problem_id: str
    user_id: str
    language: str
    code: str
    status: JudgeStatus = JudgeStatus.pending
    score: float = 0.0
    detail: str = ""
