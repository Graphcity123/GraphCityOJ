from __future__ import annotations

import copy
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    ApiResponse,
    PagedData,
    ProblemBrief,
    ProblemCreate,
)
from app.storage import delete_problem, get_problem, get_problems, save_problem
from app.utils.auth import require_login
from app.utils.exceptions import PermissionDenied, ProblemNotFound

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("/")
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    all_problems = list(get_problems().values())
    total = len(all_problems)
    start = (page - 1) * page_size
    items = []
    for p in all_problems[start:start + page_size]:
        items.append(ProblemBrief(
            id=p["id"],
            title=p["title"],
            tags=p.get("tags", []),
            difficulty=p.get("difficulty", ""),
            author=p.get("author", ""),
        ).model_dump())
    return ApiResponse(code=200, msg="success", data=PagedData(total=total, items=items).model_dump())


@router.post("/")
async def create_problem(req: Request, body: ProblemCreate):
    user = require_login(req)
    problem_id = body.id
    if get_problem(problem_id) is not None:
        raise HTTPException(status_code=409, detail=f"Problem '{problem_id}' already exists")
    now = datetime.now(timezone.utc).isoformat()
    data = body.model_dump()
    data["public_cases"] = True
    data["created_at"] = now
    data["created_by"] = user["user_id"]
    save_problem(problem_id, data)
    return ApiResponse(code=200, msg="problem created", data=None)


@router.get("/{problem_id}")
async def get_problem_detail(problem_id: str):
    p = get_problem(problem_id)
    if p is None:
        raise ProblemNotFound(problem_id)
    return ApiResponse(code=200, msg="success", data=copy.deepcopy(p))


@router.delete("/{problem_id}")
async def remove_problem(req: Request, problem_id: str):
    user = require_login(req)
    if user.get("role") != "admin":
        raise PermissionDenied("Only admin can delete problems")
    if get_problem(problem_id) is None:
        raise ProblemNotFound(problem_id)
    delete_problem(problem_id)
    return ApiResponse(code=200, msg="problem deleted", data=None)
