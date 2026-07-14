from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JudgeLog(BaseModel):
    id: str
    submission_id: str
    user_id: str
    problem_id: str
    status: str
    score: float
    detail: str
    created_at: datetime
