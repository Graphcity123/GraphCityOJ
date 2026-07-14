from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from app.schemas import (
    ApiResponse,
    EvalStatus,
    JudgeRequest,
    SubmissionListData,
)
from app.storage import (
    get_languages,
    get_problem,
    get_submission,
    get_submissions,
    get_user,
    next_id,
    save_log,
    save_submission,
)
from app.utils.auth import require_admin, require_login
from app.utils.exceptions import (
    LanguageNotFound,
    PermissionDenied,
    ProblemNotFound,
    SubmissionConditionError,
    SubmissionNotFound,
)
from app.utils.judge_engine import run_judge
from app.utils.rate_limiter import judge_rate_limiter
from app.config import settings

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


async def _run_judge_and_update(
    submission_id: str, problem_id: str, language: str,
    code: str, work_dir: Any, user_id: str,
):
    result = await run_judge(
        problem_id=problem_id,
        language=language,
        code=code,
        work_dir=work_dir,
    )

    sub = await get_submission(submission_id)
    if sub is None:
        return

    sub["status"] = result["status"]
    sub["score"] = result["score"]
    sub["results"] = result["results"]
    sub["detail"] = result["detail"]
    sub["counts"] = result["counts"]
    await save_submission(submission_id, sub)

    user_record = await get_user(user_id)
    if user_record:
        user_record.setdefault("submit_count", 0)
        user_record["submit_count"] += 1
        if result["score"] == result["counts"] and result["counts"] > 0:
            user_record.setdefault("resolve_count", 0)
            user_record.setdefault("_resolved_problems", [])
            if problem_id not in user_record["_resolved_problems"]:
                user_record["_resolved_problems"].append(problem_id)
                user_record["resolve_count"] += 1

    log_id = next_id("log")
    await save_log(log_id, {
        "id": log_id,
        "submission_id": submission_id,
        "user_id": user_id,
        "problem_id": problem_id,
        "status": result["status"],
        "score": result["score"],
        "detail": json.dumps(result.get("results", [])),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/")
async def submit_judge(
    req: Request, body: JudgeRequest, background_tasks: BackgroundTasks,
):
    user = require_login(req)
    judge_rate_limiter.check(user["user_id"])

    problem = await get_problem(body.problem_id)
    if problem is None:
        raise ProblemNotFound(body.problem_id)

    lang_info = (await get_languages()).get(body.language)
    if lang_info is None:
        raise LanguageNotFound(body.language)

    sub_counter = next_id("sub")
    submission_id = sub_counter.split("_")[-1]
    now = datetime.now(timezone.utc).isoformat()

    sub_data = {
        "submission_id": submission_id,
        "user_id": user["user_id"],
        "problem_id": body.problem_id,
        "language": body.language,
        "code": body.code,
        "status": EvalStatus.pending.value,
        "score": 0,
        "created_at": now,
        "results": [],
        "detail": "",
        "counts": 0,
    }
    await save_submission(submission_id, sub_data)

    work_dir = settings.work_dir / submission_id
    background_tasks.add_task(
        _run_judge_and_update,
        submission_id, body.problem_id, body.language,
        body.code, work_dir, user["user_id"],
    )

    return ApiResponse(
        code=200, msg="success",
        data={"submission_id": submission_id, "status": EvalStatus.pending.value},
    )


@router.get("/")
async def list_submissions(
    req: Request,
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    # Anyone can view submissions; auth optional for filtering
    user = req.session.get("user") or {}

    if page is not None and page_size is None:
        raise HTTPException(status_code=400, detail="page_size is required when page is set")

    all_subs = list((await get_submissions()).values())

    if user_id:
        all_subs = [s for s in all_subs if s["user_id"] == user_id]

    if problem_id:
        all_subs = [s for s in all_subs if s["problem_id"] == problem_id]
    if status:
        all_subs = [s for s in all_subs if s["status"] == status]

    total = len(all_subs)

    # Pagination: both empty = return all; page_size only = first page
    if page is None and page_size is None:
        paged = all_subs
    else:
        if page is None:
            page = 1
        page_size = page_size or 20
        start = (page - 1) * page_size
        paged = all_subs[start:start + page_size]

    items = []
    for s in paged:
        prob = await get_problem(s.get("problem_id", ""))
        brief: dict = {
            "submission_id": s["submission_id"],
            "problem_id": s.get("problem_id", ""),
            "problem_title": prob.get("title", "") if prob else "",
            "status": s["status"],
        }
        if s.get("status") not in ("error", "pending"):
            brief["score"] = s.get("score", 0)
            brief["counts"] = s.get("counts", 0)
        items.append(brief)

    return ApiResponse(
        code=200, msg="success",
        data=SubmissionListData(total=total, submissions=items).model_dump(),
    )


@router.get("/{submission_id}")
async def get_submission_detail(req: Request, submission_id: str):
    user = require_login(req)
    sub = await get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)
    if user.get("role") != "admin" and sub["user_id"] != user["user_id"]:
        raise PermissionDenied("Cannot view other users submissions")
    return ApiResponse(code=200, msg="success", data={
        "score": sub.get("score", 0),
        "counts": sub.get("counts", 0),
        "code": sub.get("code", ""),
        "language": sub.get("language", ""),
        "problem_id": sub.get("problem_id", ""),
    })


@router.put("/{submission_id}/rejudge")
async def rejudge_submission(req: Request, submission_id: str, background_tasks: BackgroundTasks):
    require_admin(req)
    sub = await get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)

    sub["status"] = "pending"
    sub["score"] = 0
    sub["results"] = []
    sub["detail"] = ""
    await save_submission(submission_id, sub)

    work_dir = settings.work_dir / f"{submission_id}_rejudge"
    background_tasks.add_task(
        _run_judge_and_update,
        submission_id, sub["problem_id"], sub["language"],
        sub["code"], work_dir, sub["user_id"],
    )

    return ApiResponse(code=200, msg="rejudge started", data={
        "submission_id": submission_id,
        "status": "pending",
    })
