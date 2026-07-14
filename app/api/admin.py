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


def _register_default_languages():
    """Register default languages on system reset."""
    from app.storage import save_language
    defaults = [
        {
            "id": "python",
            "name": "Python 3",
            "file_ext": ".py",
            "compile_cmd": "",
            "run_cmd": "python3 {src}",
            "time_limit": 2.0,
            "memory_limit": 256,
        },
        {
            "id": "cpp",
            "name": "C++ (GCC 9+)",
            "file_ext": ".cpp",
            "compile_cmd": "g++ {src} -o {exe} -std=c++14 -O2",
            "run_cmd": "{exe}",
            "time_limit": 2.0,
            "memory_limit": 256,
        },
    ]
    for lang in defaults:
        save_language(lang["id"], dict(lang))


@router.post("/reset/")
async def system_reset(req: Request):
    require_admin(req)
    reset_storage()
    _create_default_admin()
    # Clear session to log out current user
    req.session.clear()
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
            "score": s["score"],
            "counts": s.get("counts", 0),
            "details": s.get("results", []),
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

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Import data must be a JSON object")

    # Validate and import users
    if "users" in data:
        if not isinstance(data["users"], list):
            raise HTTPException(status_code=400, detail="'users' must be a list")
        for u in data["users"]:
            if not isinstance(u, dict) or "user_id" not in u or "username" not in u:
                raise HTTPException(status_code=400, detail="Each user must have 'user_id' and 'username'")
            uid = u["user_id"]
            save_user(uid, dict(u))

    # Validate and import problems
    if "problems" in data:
        if not isinstance(data["problems"], list):
            raise HTTPException(status_code=400, detail="'problems' must be a list")
        for p in data["problems"]:
            if not isinstance(p, dict) or "id" not in p or "title" not in p:
                raise HTTPException(status_code=400, detail="Each problem must have 'id' and 'title'")
            pid = p["id"]
            save_problem(pid, dict(p))

    # Validate and import submissions
    if "submissions" in data:
        if not isinstance(data["submissions"], list):
            raise HTTPException(status_code=400, detail="'submissions' must be a list")
        for s in data["submissions"]:
            if not isinstance(s, dict) or "submission_id" not in s:
                raise HTTPException(status_code=400, detail="Each submission must have 'submission_id'")
            sid = s["submission_id"]
            save_submission(sid, dict(s))

    return ApiResponse(code=200, msg="import success", data=None)
