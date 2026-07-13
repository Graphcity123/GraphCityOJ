from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request

from app.schemas import ApiResponse, PagedData, SubmissionBrief
from app.storage import get_submission, get_submissions, save_submission
from app.utils.auth import get_current_user, require_admin, require_login
from app.utils.exceptions import PermissionDenied, SubmissionNotFound
from app.utils.judge_engine import run_judge
from app.config import settings

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("/")
async def list_submissions(
    req: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    language: str | None = Query(default=None),
):
    require_login(req)
    all_subs = list(get_submissions().values())

    # Apply filters
    if user_id:
        all_subs = [s for s in all_subs if s["user_id"] == user_id]
    if problem_id:
        all_subs = [s for s in all_subs if s["problem_id"] == problem_id]
    if status:
        all_subs = [s for s in all_subs if s["status"] == status]
    if language:
        all_subs = [s for s in all_subs if s["language"] == language]

    total = len(all_subs)
    start = (page - 1) * page_size
    items = []
    for s in all_subs[start:start + page_size]:
        items.append(SubmissionBrief(
            submission_id=s["submission_id"],
            user_id=s["user_id"],
            problem_id=s["problem_id"],
            language=s["language"],
            status=s["status"],
            score=s["score"],
            created_at=s["created_at"],
        ).model_dump())

    return ApiResponse(code=200, msg="success", data=PagedData(total=total, items=items).model_dump())


@router.get("/{submission_id}")
async def get_submission_detail(req: Request, submission_id: str):
    user = require_login(req)
    sub = get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)
    # Permission: self or admin
    if user.get("role") != "admin" and sub["user_id"] != user["user_id"]:
        raise PermissionDenied("Cannot view other users submissions")
    return ApiResponse(code=200, msg="success", data=copy.deepcopy(sub))


@router.put("/{submission_id}/rejudge")
async def rejudge_submission(req: Request, submission_id: str):
    require_admin(req)
    sub = get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)

    # Reset to pending and re-run
    sub["status"] = "pending"
    sub["score"] = 0.0
    sub["results"] = []
    sub["detail"] = ""
    save_submission(submission_id, sub)

    work_dir = settings.work_dir / f"{submission_id}_rejudge"
    result = await run_judge(
        problem_id=sub["problem_id"],
        language=sub["language"],
        code=sub["code"],
        work_dir=work_dir,
    )

    sub["status"] = result["status"]
    sub["score"] = result["score"]
    sub["results"] = result["results"]
    sub["detail"] = result["detail"]
    sub["counts"] = result["counts"]
    save_submission(submission_id, sub)

    return ApiResponse(code=200, msg="rejudge completed", data=copy.deepcopy(sub))
