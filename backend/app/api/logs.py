from __future__ import annotations

import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ApiResponse, LogVisibilityUpdate
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
from app.utils.auth import get_current_user, require_admin, require_login
from app.utils.exceptions import PermissionDenied, ProblemNotFound, SubmissionNotFound

router = APIRouter(prefix="/api", tags=["logs"])


def _parse_submission_results(sub: dict) -> list[dict]:
    results = sub.get("results", [])
    if isinstance(results, str):
        try:
            return _json.loads(results)
        except (_json.JSONDecodeError, TypeError):
            return []
    return list(results) if results else []


@router.get("/submissions/{submission_id}/log")
async def query_submission_log(req: Request, submission_id: str):
    user = require_login(req)
    sub = await get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)

    is_owner = sub["user_id"] == user["user_id"]
    is_admin = user.get("role") == "admin"

    if not is_admin and not is_owner:
        raise PermissionDenied("Cannot view logs for this submission")

    problem = await get_problem(sub["problem_id"])
    public_cases = problem.get("public_cases", True) if problem else True

    details = _parse_submission_results(sub)
    if not is_admin and not public_cases:
        details = []

    await add_audit({
        "user_id": user["user_id"],
        "problem_id": sub["problem_id"],
        "action": "view_log",
        "time": datetime.now(timezone.utc).isoformat().split("T")[0],
        "status": "200" if (is_admin or public_cases) else "403",
    })

    return ApiResponse(code=200, msg="success", data={
        "details": details,
        "score": sub.get("score", 0),
        "counts": sub.get("counts", 0),
    })


@router.put("/problems/{problem_id}/log_visibility")
async def set_log_visibility(req: Request, problem_id: str):
    user = require_admin(req)
    problem = await get_problem(problem_id)
    if problem is None:
        raise ProblemNotFound(problem_id)

    # Toggle when no body; otherwise use body value
    body_data = None
    try:
        body_raw = await req.json()
        body_data = LogVisibilityUpdate(**body_raw)
    except Exception:
        pass

    if body_data is not None and body_data.public_cases is not None:
        problem["public_cases"] = body_data.public_cases
    else:
        problem["public_cases"] = False

    await save_problem(problem_id, problem)
    return ApiResponse(code=200, msg="log visibility updated", data={
        "problem_id": problem_id,
        "public_cases": problem["public_cases"],
    })


@router.get("/logs/access/")
async def query_access_logs(
    req: Request,
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
):
    require_admin(req)
    all_logs = [lg for lg in await get_audit_logs() if lg.get("action") == "view_log"]

    if user_id:
        all_logs = [lg for lg in all_logs if lg.get("user_id") == user_id]
    if problem_id:
        all_logs = [lg for lg in all_logs if lg.get("problem_id") == problem_id]

    total = len(all_logs)

    # Pagination: same rules as submissions list
    if page is None and page_size is None:
        paged = all_logs
    elif page is not None and page_size is None:
        raise HTTPException(status_code=400, detail="page_size is required when page is set")
    else:
        if page is None:
            page = 1
        page_size = page_size or 20
        start = (page - 1) * page_size
        paged = all_logs[start:start + page_size]

    items = [{k: lg[k] for k in ("user_id", "problem_id", "action", "time", "status") if k in lg} for lg in paged]

    return ApiResponse(code=200, msg="success", data=items)
