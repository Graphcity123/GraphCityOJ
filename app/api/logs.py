from __future__ import annotations

import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ApiResponse, PagedData
from app.storage import (
    add_audit,
    get_audit_logs,
    get_logs,
    get_logs_by_submission,
    get_problem,
    get_submission,
    get_user,
    save_problem,
)
from app.utils.auth import require_admin, require_login
from app.utils.exceptions import PermissionDenied, ProblemNotFound, SubmissionNotFound

router = APIRouter(prefix="/api", tags=["logs"])


def _parse_log_detail(log: dict) -> dict:
    """Parse the stored detail JSON string into a results array."""
    log = dict(log)
    detail_raw = log.pop("detail", "[]")
    try:
        log["results"] = _json.loads(detail_raw) if isinstance(detail_raw, str) else (detail_raw or [])
    except (_json.JSONDecodeError, TypeError):
        log["results"] = []
    return log


@router.get("/logs/")
async def query_logs(
    req: Request,
    submission_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    user = require_login(req)

    if submission_id:
        sub = get_submission(submission_id)
        if sub is None:
            raise SubmissionNotFound(submission_id)
        if user.get("role") != "admin" and sub["user_id"] != user["user_id"]:
            problem = get_problem(sub["problem_id"])
            if problem and not problem.get("public_cases", True):
                raise PermissionDenied("Cannot view logs for this submission")
        all_logs = get_logs_by_submission(submission_id)
    else:
        all_entries = list(get_logs().values())
        if user.get("role") != "admin":
            filtered = []
            for lg in all_entries:
                if lg["user_id"] == user["user_id"]:
                    filtered.append(lg)
                else:
                    problem = get_problem(lg.get("problem_id", ""))
                    if problem and problem.get("public_cases", True):
                        filtered.append(lg)
            all_logs = filtered
        else:
            all_logs = all_entries

    total = len(all_logs)
    start = (page - 1) * page_size
    items = [_parse_log_detail(lg) for lg in all_logs[start:start + page_size]]

    add_audit({
        "action": "query_logs",
        "user_id": user["user_id"],
        "username": user.get("username", ""),
        "submission_id": submission_id or "all",
        "ip": req.client.host if req.client else "",
    })

    return ApiResponse(code=200, msg="success", data=PagedData(total=total, items=items).model_dump())


@router.get("/logs/audit")
async def query_audit_logs(
    req: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    require_admin(req)
    audit = get_audit_logs()
    total = len(audit)
    start = (page - 1) * page_size
    items = audit[start:start + page_size]
    return ApiResponse(code=200, msg="success", data=PagedData(total=total, items=items).model_dump())


@router.get("/problems/{problem_id}/public_cases")
async def get_public_cases(req: Request, problem_id: str):
    require_login(req)
    problem = get_problem(problem_id)
    if problem is None:
        raise ProblemNotFound(problem_id)
    return ApiResponse(code=200, msg="success", data={"public_cases": problem.get("public_cases", True)})


@router.put("/problems/{problem_id}/public_cases")
async def set_public_cases(req: Request, problem_id: str):
    user = require_login(req)
    if user.get("role") not in ("admin", "teacher"):
        raise PermissionDenied("Only admin or teacher can change public_cases")
    problem = get_problem(problem_id)
    if problem is None:
        raise ProblemNotFound(problem_id)
    current = problem.get("public_cases", True)
    problem["public_cases"] = not current
    save_problem(problem_id, problem)
    return ApiResponse(code=200, msg="public_cases toggled", data={"public_cases": problem["public_cases"]})
