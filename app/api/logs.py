from __future__ import annotations

import copy
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ApiResponse, PagedData
from app.storage import (
    add_audit,
    get_audit_logs,
    get_logs,
    get_problem,
    get_submission,
    get_user,
    next_id,
    save_log,
    save_problem,
)
from app.utils.auth import get_current_user_or_none, require_admin, require_login
from app.utils.exceptions import PermissionDenied, ProblemNotFound, SubmissionNotFound

router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/logs/")
async def query_logs(
    req: Request,
    submission_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    user = require_login(req)
    sub = None
    if submission_id:
        sub = get_submission(submission_id)
        if sub is None:
            raise SubmissionNotFound(submission_id)
        # Permission: admin or submission owner
        if user.get("role") != "admin" and sub["user_id"] != user["user_id"]:
            # Check if public_cases
            problem = get_problem(sub["problem_id"])
            if problem and not problem.get("public_cases", False):
                raise PermissionDenied("Cannot view logs for this submission")

    all_logs = list(get_logs().values())
    if submission_id:
        all_logs = [lg for lg in all_logs if lg.get("submission_id") == submission_id]

    total = len(all_logs)
    start = (page - 1) * page_size
    items = [copy.deepcopy(lg) for lg in all_logs[start:start + page_size]]
    # Remove password from items
    for item in items:
        item.pop("password", None)

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
