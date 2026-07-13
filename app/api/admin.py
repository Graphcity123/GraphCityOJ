from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.schemas import ApiResponse
from app.storage import (
    get_problems,
    get_submissions,
    get_users,
    reset_storage,
    save_problem,
    save_submission,
    save_user,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/api", tags=["admin"])

_DEFAULT_ADMIN = {
    "user_id": "admin",
    "username": "admin",
    "password": "sha256:init",
    "role": "admin",
    "join_time": "",
    "submit_count": 0,
    "resolve_count": 0,
    "email": "",
}


def _create_default_admin():
    """Create default admin if not exists."""
    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    pw = "admintestpassword"
    stored = salt + ":" + hashlib.sha256((salt + pw).encode()).hexdigest()
    admin = dict(_DEFAULT_ADMIN)
    admin["password"] = stored
    admin["join_time"] = datetime.now(timezone.utc).isoformat().split("T")[0]
    save_user("admin", admin)


@router.post("/reset/")
async def system_reset(req: Request):
    # Allow reset even without admin (for CI/testing)
    reset_storage()
    _create_default_admin()
    return ApiResponse(code=200, msg="system reset successfully", data=None)


@router.get("/export/")
async def export_data(req: Request):
    require_admin(req)
    users = []
    for u in get_users().values():
        users.append({
            "user_id": u["user_id"],
            "username": u["username"],
            "password": u.get("password", ""),
            "role": u.get("role", "student"),
            "join_time": u.get("join_time", ""),
            "submit_count": u.get("submit_count", 0),
            "resolve_count": u.get("resolve_count", 0),
        })

    problems = []
    for p in get_problems().values():
        problems.append({
            "id": p["id"],
            "title": p["title"],
            "description": p.get("description", ""),
            "input_description": p.get("input_description", ""),
            "output_description": p.get("output_description", ""),
            "samples": p.get("samples", []),
            "constraints": p.get("constraints", ""),
            "testcases": p.get("testcases", []),
            "hint": p.get("hint", ""),
            "source": p.get("source", ""),
            "tags": p.get("tags", []),
            "time_limit": p.get("time_limit", 1.0),
            "memory_limit": p.get("memory_limit", 128),
            "author": p.get("author", ""),
            "difficulty": p.get("difficulty", ""),
            "public_cases": p.get("public_cases", True),
        })

    submissions = []
    for s in get_submissions().values():
        submissions.append({
            "submission_id": s["submission_id"],
            "user_id": s["user_id"],
            "problem_id": s["problem_id"],
            "language": s["language"],
            "code": s["code"],
            "status": s["status"],
            "details": s.get("results", []),
            "score": s["score"],
            "counts": s.get("counts", 0),
        })

    data = {"users": users, "problems": problems, "submissions": submissions}
    return ApiResponse(code=200, msg="success", data=data)


@router.post("/import/")
async def import_data(req: Request, file: UploadFile = File(...)):
    require_admin(req)
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files supported")

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    # Import users (merge: latest wins for duplicates)
    if "users" in data:
        for u in data["users"]:
            uid = u["user_id"]
            existing = get_users().get(uid)
            if existing:
                existing.update(u)
            else:
                save_user(uid, dict(u))

    # Import problems
    if "problems" in data:
        for p in data["problems"]:
            pid = p["id"]
            save_problem(pid, dict(p))

    # Import submissions
    if "submissions" in data:
        for s in data["submissions"]:
            sid = s["submission_id"]
            save_submission(sid, dict(s))

    return ApiResponse(code=200, msg="import success", data=None)
