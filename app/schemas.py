from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class JudgeStatus(str, Enum):
    AC = "AC"
    WA = "WA"
    TLE = "TLE"
    MLE = "MLE"
    RE = "RE"
    CE = "CE"
    UNK = "UNK"


class EvalStatus(str, Enum):
    pending = "pending"
    success = "success"
    error = "error"


# --- Problem schemas ---

class TestCaseItem(BaseModel):
    input: str
    output: str


class SampleItem(BaseModel):
    input: str
    output: str


class ProblemCreate(BaseModel):
    id: str
    title: str
    description: str = ""
    input_description: str = ""
    output_description: str = ""
    samples: list[SampleItem] = []
    constraints: str = ""
    testcases: list[TestCaseItem] = []
    hint: str = ""
    source: str = ""
    tags: list[str] = []
    time_limit: float = 1.0
    memory_limit: int = 128
    author: str = ""
    difficulty: str = ""


class ProblemBrief(BaseModel):
    id: str
    title: str
    tags: list[str] = []
    difficulty: str = ""
    author: str = ""


# --- Language schemas ---

class LanguageCreate(BaseModel):
    id: str
    name: str
    extension: str
    compile_cmd: str = ""
    run_cmd: str
    time_limit: float = 1.0
    memory_limit: int = 128


# --- Judge schemas ---

class JudgeRequest(BaseModel):
    problem_id: str
    language: str
    code: str


class JudgeResultItem(BaseModel):
    id: int
    result: str
    time: float = 0.0
    memory: int = 0


class JudgeResponse(BaseModel):
    submission_id: str
    status: str
    score: float
    counts: int
    results: list[JudgeResultItem] = []
    detail: str = ""


# --- User schemas ---

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6)
    email: str = ""


class UserLogin(BaseModel):
    username: str
    password: str


class RoleChange(BaseModel):
    role: str


# --- Submission schemas ---

class SubmissionBrief(BaseModel):
    submission_id: str
    user_id: str
    problem_id: str
    language: str
    status: str
    score: float
    created_at: str


# --- Log schemas ---

class LogEntry(BaseModel):
    id: str
    submission_id: str
    user_id: str
    problem_id: str
    status: str
    score: float
    detail: str
    created_at: str


# --- API response wrappers ---

class ApiResponse(BaseModel):
    code: int
    msg: str
    data: Any = None


class PagedData(BaseModel):
    total: int
    items: list[Any]
