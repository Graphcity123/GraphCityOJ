"""SQLAlchemy ORM models for the OJ system."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON,
    String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── User ──────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    username = Column(String(40), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=False)  # salt:hash
    role = Column(String(20), nullable=False, default="user")
    join_time = Column(String(20), default="")
    submit_count = Column(Integer, default=0)
    resolve_count = Column(Integer, default=0)
    _resolved_problems = Column(JSON, default=list)  # internal tracking

    submissions = relationship("Submission", back_populates="user")


# ── Problem ───────────────────────────────────────────────────

class Problem(Base):
    __tablename__ = "problems"

    id = Column(String(64), primary_key=True)  # auto-generated folder_id
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    input_description = Column(Text, default="")
    output_description = Column(Text, default="")
    constraints = Column(Text, default="")
    hint = Column(Text, default="")
    source = Column(String(200), default="")
    author = Column(String(100), default="")
    difficulty = Column(String(20), default="easy")
    tags = Column(JSON, default=list)
    samples = Column(JSON, default=list)
    time_limit = Column(Float, default=1.0)
    memory_limit = Column(Integer, default=256)
    testcase_count = Column(Integer, default=0)
    testcases_json = Column(JSON, default=list)  # inline fallback
    public_cases = Column(Boolean, default=True)
    created_by = Column(String(64), default="")
    created_at = Column(String(30), default="")
    updated_at = Column(String(30), default="")

    submissions = relationship("Submission", back_populates="problem")


# ── Language ──────────────────────────────────────────────────

class Language(Base):
    __tablename__ = "languages"

    name = Column(String(50), primary_key=True)  # e.g. "python", "cpp"
    file_ext = Column(String(20), nullable=False)
    compile_cmd = Column(String(500), default="")
    run_cmd = Column(String(500), nullable=False)
    time_limit = Column(Float, default=1.0)
    memory_limit = Column(Integer, default=256)


# ── Submission ────────────────────────────────────────────────

class Submission(Base):
    __tablename__ = "submissions"

    submission_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)
    problem_id = Column(String(64), ForeignKey("problems.id"), nullable=False)
    language = Column(String(50), nullable=False)
    code = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    score = Column(Integer, default=0)
    counts = Column(Integer, default=0)
    results = Column(JSON, default=list)  # list of {id, result, time, memory}
    detail = Column(Text, default="")
    created_at = Column(String(30), default="")

    user = relationship("User", back_populates="submissions")
    problem = relationship("Problem", back_populates="submissions")


# ── Audit Log ─────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), default="")
    problem_id = Column(String(64), default="")
    action = Column(String(50), default="")
    time = Column(String(30), default="")
    status = Column(String(10), default="")
    timestamp = Column(String(30), default="")
