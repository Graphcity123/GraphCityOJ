from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query, Request

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

    sub = get_submission(submission_id)
    if sub is None:
        return

    sub["status"] = result["status"]
    sub["score"] = result["score"]
    sub["results"] = result["results"]
    sub["detail"] = result["detail"]
    sub["counts"] = result["counts"]
    save_submission(submission_id, sub)

    user_record = get_user(user_id)
    if user_record:
        user_record.setdefault("submit_count", 0)
        user_record["submit_count"] += 1
        if result["score"] == 100.0:
            user_record.setdefault("resolve_count", 0)
            user_record["resolve_count"] += 1

    log_id = next_id("log")
    save_log(log_id, {
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

    problem = get_problem(body.problem_id)
    if problem is None:
        raise ProblemNotFound(body.problem_id)

    lang_info = get_languages().get(body.language)
    if lang_info is None:
        raise LanguageNotFound(body.language)

    submission_id = next_id("sub")
    now = datetime.now(timezone.utc).isoformat()

    sub_data = {
        "submission_id": submission_id,
        "user_id": user["user_id"],
        "problem_id": body.problem_id,
        "language": body.language,
        "code": body.code,
        "status": EvalStatus.pending.value,
        "score": 0.0,
        "created_at": now,
        "results": [],
        "detail": "",
        "counts": 0,
    }
    save_submission(submission_id, sub_data)

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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    require_login(req)

    if not user_id and not problem_id:
        raise SubmissionConditionError()

    all_subs = list(get_submissions().values())

    if user_id:
        all_subs = [s for s in all_subs if s["user_id"] == user_id]
    if problem_id:
        all_subs = [s for s in all_subs if s["problem_id"] == problem_id]
    if status:
        all_subs = [s for s in all_subs if s["status"] == status]

    total = len(all_subs)
    start = (page - 1) * page_size
    items = []
    for s in all_subs[start:start + page_size]:
        brief = {"submission_id": s["submission_id"], "status": s["status"]}
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
    sub = get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)
    if user.get("role") != "admin" and sub["user_id"] != user["user_id"]:
        raise PermissionDenied("Cannot view other users submissions")
    return ApiResponse(code=200, msg="success", data={
        "score": sub.get("score", 0),
        "counts": sub.get("counts", 0),
    })


@router.put("/{submission_id}/rejudge")
async def rejudge_submission(req: Request, submission_id: str):
    require_admin(req)
    sub = get_submission(submission_id)
    if sub is None:
        raise SubmissionNotFound(submission_id)

    sub["status"] = "pending"
    sub["score"] = 0.0
    sub["results"] = []
    sub["detail"] = ""
    save_submission(submission_id, sub)

    return ApiResponse(code=200, msg="rejudge started", data={
        "submission_id": submission_id,
        "status": "pending",
    })
