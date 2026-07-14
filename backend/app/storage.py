"""Async storage layer — SQLAlchemy ORM over aiosqlite.

All functions are async and compatible with FastAPI async handlers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db.models import (
    AuditLog as AuditLogModel,
    Language as LanguageModel,
    Problem as ProblemModel,
    Submission as SubmissionModel,
    User as UserModel,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_counters: dict[str, int] = {}


def next_id(prefix: str) -> str:
    _counters[prefix] = _counters.get(prefix, 0) + 1
    return f"{prefix}_{_counters[prefix]}"


def reset_counters() -> None:
    _counters.clear()


# ── Reset ─────────────────────────────────────────────────────

async def reset_storage() -> None:
    from app.db.database import drop_db, init_db
    await drop_db()
    await init_db()
    reset_counters()


# ── Problem ───────────────────────────────────────────────────

async def get_problems() -> dict[str, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ProblemModel))
        rows = result.scalars().all()
        return {r.id: _problem_to_dict(r) for r in rows}


async def get_problem(problem_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProblemModel).where(ProblemModel.id == problem_id))
        row = result.scalars().first()
        return _problem_to_dict(row) if row else None


async def save_problem(problem_id: str, data: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProblemModel).where(ProblemModel.id == problem_id))
        existing = result.scalars().first()
        if existing:
            _update_model(existing, data)
        else:
            db.add(_dict_to_problem(data))
        await db.commit()


async def delete_problem(problem_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProblemModel).where(ProblemModel.id == problem_id))
        row = result.scalars().first()
        if row:
            await db.delete(row)
            await db.commit()


# ── User ──────────────────────────────────────────────────────

async def get_users() -> dict[str, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel))
        rows = result.scalars().all()
        return {r.user_id: _user_to_dict(r) for r in rows}


async def get_user(user_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserModel).where(UserModel.user_id == user_id))
        row = result.scalars().first()
        return _user_to_dict(row) if row else None


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserModel).where(UserModel.username == username))
        row = result.scalars().first()
        return _user_to_dict(row) if row else None


async def save_user(user_id: str, data: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserModel).where(UserModel.user_id == user_id))
        existing = result.scalars().first()
        if existing:
            _update_model(existing, data)
        else:
            db.add(_dict_to_user(data))
        await db.commit()


# ── Submission ────────────────────────────────────────────────

async def get_submissions() -> dict[str, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SubmissionModel))
        rows = result.scalars().all()
        return {r.submission_id: _submission_to_dict(r) for r in rows}


async def get_submission(submission_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SubmissionModel).where(
                SubmissionModel.submission_id == submission_id))
        row = result.scalars().first()
        return _submission_to_dict(row) if row else None


async def save_submission(submission_id: str, data: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SubmissionModel).where(
                SubmissionModel.submission_id == submission_id))
        existing = result.scalars().first()
        if existing:
            _update_model(existing, data)
        else:
            db.add(_dict_to_submission(data))
        await db.commit()


# ── Language ──────────────────────────────────────────────────

async def get_languages() -> dict[str, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(LanguageModel))
        rows = result.scalars().all()
        return {r.name: _language_to_dict(r) for r in rows}


async def save_language(lang_id: str, data: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LanguageModel).where(LanguageModel.name == lang_id))
        existing = result.scalars().first()
        if existing:
            _update_model(existing, data)
        else:
            db.add(_dict_to_language(data))
        await db.commit()


# ── Log ───────────────────────────────────────────────────────

async def get_logs() -> dict[str, dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AuditLogModel))
        rows = result.scalars().all()
        return {str(r.id): _audit_to_dict(r) for r in rows}


async def save_log(log_id: str, data: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        db.add(_dict_to_audit(data))
        await db.commit()


async def get_logs_by_submission(submission_id: str) -> list[dict[str, Any]]:
    return []


# ── Audit ─────────────────────────────────────────────────────

async def add_audit(entry: dict[str, Any]) -> None:
    entry.setdefault("timestamp", _now_iso())
    async with AsyncSessionLocal() as db:
        db.add(_dict_to_audit(entry))
        await db.commit()


async def get_audit_logs() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AuditLogModel))
        rows = result.scalars().all()
        return [_audit_to_dict(r) for r in rows]


# ── Dict ↔ ORM ────────────────────────────────────────────────

def _problem_to_dict(p: ProblemModel) -> dict[str, Any]:
    # Prefer disk file for description if it exists
    desc = _load_md_from_disk(p.id) or p.description
    return {
        "id": p.id, "title": p.title, "description": desc,
        "input_description": p.input_description,
        "output_description": p.output_description,
        "constraints": p.constraints, "hint": p.hint,
        "source": p.source, "author": p.author,
        "difficulty": p.difficulty,
        "samples": p.samples or [],
        "time_limit": p.time_limit, "memory_limit": p.memory_limit,
        "testcase_count": p.testcase_count,
        "public_cases": p.public_cases,
        "created_by": p.created_by, "created_at": p.created_at,
        "updated_at": p.updated_at,
        "testcases": (_load_testcases_from_disk(p.id, p.testcase_count)
                       or p.testcases_json or []),
    }


def _dict_to_problem(data: dict[str, Any]) -> ProblemModel:
    return ProblemModel(
        id=data.get("id", ""), title=data.get("title", ""),
        description=data.get("description", ""),
        input_description=data.get("input_description", ""),
        output_description=data.get("output_description", ""),
        constraints=data.get("constraints", ""),
        hint=data.get("hint", ""), source=data.get("source", ""),
        author=data.get("author", ""),
        difficulty=data.get("difficulty", "easy"),
        time_limit=data.get("time_limit", 1.0),
        memory_limit=data.get("memory_limit", 256),
        testcase_count=data.get("testcase_count", len(data.get("testcases", []))),
        testcases_json=data.get("testcases", []),
        public_cases=data.get("public_cases", True),
        created_by=data.get("created_by", ""),
        created_at=data.get("created_at", _now_iso()),
        updated_at=data.get("updated_at", _now_iso()),
    )


def _user_to_dict(u: UserModel) -> dict[str, Any]:
    return {
        "user_id": u.user_id, "username": u.username,
        "password": u.password, "role": u.role,
        "join_time": u.join_time,
        "submit_count": u.submit_count,
        "resolve_count": u.resolve_count,
        "_resolved_problems": u._resolved_problems or [],
    }


def _dict_to_user(data: dict[str, Any]) -> UserModel:
    return UserModel(
        user_id=data.get("user_id", ""),
        username=data.get("username", ""),
        password=data.get("password", ""),
        role=data.get("role", "user"),
        join_time=data.get("join_time", ""),
        submit_count=data.get("submit_count", 0),
        resolve_count=data.get("resolve_count", 0),
        _resolved_problems=data.get("_resolved_problems", []),
    )


def _submission_to_dict(s: SubmissionModel) -> dict[str, Any]:
    return {
        "submission_id": s.submission_id,
        "user_id": s.user_id, "problem_id": s.problem_id,
        "language": s.language, "code": s.code,
        "status": s.status, "score": s.score, "counts": s.counts,
        "results": s.results or [], "detail": s.detail,
        "created_at": s.created_at,
    }


def _dict_to_submission(data: dict[str, Any]) -> SubmissionModel:
    return SubmissionModel(
        submission_id=data.get("submission_id", ""),
        user_id=data.get("user_id", ""),
        problem_id=data.get("problem_id", ""),
        language=data.get("language", ""),
        code=data.get("code", ""),
        status=data.get("status", "pending"),
        score=data.get("score", 0),
        counts=data.get("counts", 0),
        results=data.get("results", []),
        detail=data.get("detail", ""),
        created_at=data.get("created_at", _now_iso()),
    )


def _language_to_dict(l: LanguageModel) -> dict[str, Any]:
    return {
        "name": l.name, "file_ext": l.file_ext,
        "compile_cmd": l.compile_cmd, "run_cmd": l.run_cmd,
        "time_limit": l.time_limit, "memory_limit": l.memory_limit,
    }


def _dict_to_language(data: dict[str, Any]) -> LanguageModel:
    return LanguageModel(
        name=data.get("name", data.get("id", "")),
        file_ext=data.get("file_ext", ".py"),
        compile_cmd=data.get("compile_cmd", ""),
        run_cmd=data.get("run_cmd", ""),
        time_limit=data.get("time_limit", 1.0),
        memory_limit=data.get("memory_limit", 256),
    )


def _audit_to_dict(a: AuditLogModel) -> dict[str, Any]:
    return {
        "user_id": a.user_id, "problem_id": a.problem_id,
        "action": a.action, "time": a.time, "status": a.status,
        "id": str(a.id), "timestamp": a.timestamp,
    }


def _dict_to_audit(data: dict[str, Any]) -> AuditLogModel:
    return AuditLogModel(
        user_id=data.get("user_id", ""),
        problem_id=data.get("problem_id", ""),
        action=data.get("action", ""),
        time=data.get("time", ""),
        status=data.get("status", ""),
        timestamp=data.get("timestamp", _now_iso()),
    )


def _update_model(model: Any, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if hasattr(model, key):
            setattr(model, key, value)


def _load_md_from_disk(problem_id: str) -> str | None:
    """Load problem.md from disk if it exists."""
    from pathlib import Path
    from app.config import settings
    md_file = settings.problems_dir / problem_id / "problem.md"
    if md_file.exists():
        return md_file.read_text(encoding="utf-8")
    return None


def _load_testcases_from_disk(
        problem_id: str, count: int) -> list[dict[str, str]]:
    from pathlib import Path
    from app.config import settings

    testcases = []
    prob_dir = settings.problems_dir / problem_id
    for i in range(1, count + 1):
        in_file = prob_dir / f"{i}.in"
        out_file = prob_dir / f"{i}.out"
        if in_file.exists() and out_file.exists():
            testcases.append({
                "input": in_file.read_text(encoding="utf-8"),
                "output": out_file.read_text(encoding="utf-8"),
            })
    return testcases
