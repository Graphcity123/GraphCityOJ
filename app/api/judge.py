from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.schemas import (
    ApiResponse,
    EvalStatus,
    JudgeRequest,
    JudgeResponse,
    JudgeResultItem,
    LanguageCreate,
)
from app.storage import (
    get_languages,
    get_problem,
    get_user,
    next_id,
    save_language,
    save_log,
    save_submission,
)
from app.utils.auth import get_current_user_or_none, require_login
from app.utils.exceptions import LanguageNotFound, ProblemNotFound
from app.utils.judge_engine import run_judge

from app.config import settings

router = APIRouter(prefix="/api", tags=["judge"])


@router.get("/languages/")
async def list_languages():
    langs = [copy.deepcopy(l) for l in get_languages().values()]
    return ApiResponse(code=200, msg="success", data=langs)


@router.post("/languages/")
async def register_language(req: Request, body: LanguageCreate):
    require_login(req)
    if body.id in get_languages():
        raise HTTPException(status_code=409, detail=f"Language '{body.id}' already exists")
    data = body.model_dump()
    save_language(body.id, data)
    return ApiResponse(code=200, msg="language registered", data=None)


@router.post("/judge/")
async def submit_judge(req: Request, body: JudgeRequest):
    user = require_login(req)
    problem = get_problem(body.problem_id)
    if problem is None:
        raise ProblemNotFound(body.problem_id)

    lang_info = get_languages().get(body.language)
    if lang_info is None:
        raise LanguageNotFound(body.language)

    submission_id = next_id("sub")
    now = datetime.now(timezone.utc).isoformat()

    # Create submission with pending status
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

    # Run judge
    work_dir = settings.work_dir / submission_id
    result = await run_judge(
        problem_id=body.problem_id,
        language=body.language,
        code=body.code,
        work_dir=work_dir,
    )

    # Update submission with result
    sub_data["status"] = result["status"]
    sub_data["score"] = result["score"]
    sub_data["results"] = result["results"]
    sub_data["detail"] = result["detail"]
    sub_data["counts"] = result["counts"]
    save_submission(submission_id, sub_data)

    # Update user stats
    user_record = get_user(user["user_id"])
    if user_record:
        user_record.setdefault("submit_count", 0)
        user_record["submit_count"] += 1
        if result["score"] == 100.0:
            user_record.setdefault("resolve_count", 0)
            user_record["resolve_count"] += 1

    # Save judge log
    log_id = next_id("log")
    save_log(log_id, {
        "id": log_id,
        "submission_id": submission_id,
        "user_id": user["user_id"],
        "problem_id": body.problem_id,
        "status": result["status"],
        "score": result["score"],
        "detail": json.dumps(result.get("results", [])),
        "created_at": now,
    })

    response = JudgeResponse(
        submission_id=submission_id,
        status=result["status"],
        score=result["score"],
        counts=result["counts"],
        results=[JudgeResultItem(**r) for r in result["results"]],
        detail=result["detail"],
    )
    return ApiResponse(code=200, msg="success", data=response.model_dump())
