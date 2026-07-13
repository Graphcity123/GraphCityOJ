from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# --- In-memory storage (replaced by SQLite in Step 6) ---

_problems: dict[str, dict[str, Any]] = {}
_users: dict[str, dict[str, Any]] = {}
_submissions: dict[str, dict[str, Any]] = {}
_logs: dict[str, dict[str, Any]] = {}
_languages: dict[str, dict[str, Any]] = {}
_audit_logs: list[dict[str, Any]] = []
_counters: dict[str, int] = defaultdict(int)


def reset_storage() -> None:
    """Clear all in-memory data."""
    _problems.clear()
    _users.clear()
    _submissions.clear()
    _logs.clear()
    _languages.clear()
    _audit_logs.clear()
    _counters.clear()


def next_id(prefix: str) -> str:
    _counters[prefix] += 1
    return f"{prefix}_{_counters[prefix]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Problem access ---

def get_problems() -> dict[str, dict[str, Any]]:
    return _problems

def get_problem(problem_id: str) -> dict[str, Any] | None:
    return _problems.get(problem_id)

def save_problem(problem_id: str, data: dict[str, Any]) -> None:
    _problems[problem_id] = data

def delete_problem(problem_id: str) -> None:
    _problems.pop(problem_id, None)


# --- User access ---

def get_users() -> dict[str, dict[str, Any]]:
    return _users

def get_user(user_id: str) -> dict[str, Any] | None:
    return _users.get(user_id)

def get_user_by_username(username: str) -> dict[str, Any] | None:
    for u in _users.values():
        if u["username"] == username:
            return u
    return None

def save_user(user_id: str, data: dict[str, Any]) -> None:
    _users[user_id] = data


# --- Submission access ---

def get_submissions() -> dict[str, dict[str, Any]]:
    return _submissions

def get_submission(submission_id: str) -> dict[str, Any] | None:
    return _submissions.get(submission_id)

def save_submission(submission_id: str, data: dict[str, Any]) -> None:
    _submissions[submission_id] = data


# --- Log access ---

def get_logs() -> dict[str, dict[str, Any]]:
    return _logs

def save_log(log_id: str, data: dict[str, Any]) -> None:
    _logs[log_id] = data

def get_logs_by_submission(submission_id: str) -> list[dict[str, Any]]:
    return [lg for lg in _logs.values() if lg.get("submission_id") == submission_id]


# --- Language access ---

def get_languages() -> dict[str, dict[str, Any]]:
    return _languages

def save_language(lang_id: str, data: dict[str, Any]) -> None:
    _languages[lang_id] = data


# --- Audit ---

def add_audit(entry: dict[str, Any]) -> None:
    entry["timestamp"] = _now_iso()
    _audit_logs.append(entry)

def get_audit_logs() -> list[dict[str, Any]]:
    return _audit_logs
