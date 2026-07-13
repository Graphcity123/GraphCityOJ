from __future__ import annotations

import copy
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from app.schemas import ApiResponse, ProblemCreate
from app.storage import delete_problem, get_problem, get_problems, save_problem
from app.utils.auth import require_login
from app.utils.exceptions import DuplicateProblem, PermissionDenied, ProblemNotFound

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("/")
async def list_problems(
    req: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    require_login(req)
    all_problems = list(get_problems().values())
    total = len(all_problems)
    start = (page - 1) * page_size
    items = []
    for p in all_problems[start:start + page_size]:
        items.append({
            "id": p["id"],
            "title": p["title"],
            "tags": p.get("tags", []),
            "difficulty": p.get("difficulty", ""),
            "author": p.get("author", ""),
        })
    return ApiResponse(code=200, msg="success", data=items)


@router.post("/")
async def create_problem(req: Request, body: ProblemCreate):
    require_login(req)
    problem_id = body.id
    if get_problem(problem_id) is not None:
        raise DuplicateProblem(problem_id)
    now = datetime.now(timezone.utc).isoformat()
    data = body.model_dump()
    data["public_cases"] = True
    data["created_at"] = now
    data["created_by"] = req.session.get("user", {}).get("user_id", "")
    save_problem(problem_id, data)
    return ApiResponse(code=200, msg="add success", data={"id": problem_id})


@router.get("/{problem_id}")
async def get_problem_detail(req: Request, problem_id: str):
    require_login(req)
    p = get_problem(problem_id)
    if p is None:
        raise ProblemNotFound(problem_id)
    return ApiResponse(code=200, msg="success", data=copy.deepcopy(p))


@router.delete("/{problem_id}")
async def remove_problem(req: Request, problem_id: str):
    require_login(req)
    user = req.session.get("user", {})
    if user.get("role") != "admin":
        raise PermissionDenied("Only admin can delete problems")
    if get_problem(problem_id) is None:
        raise ProblemNotFound(problem_id)
    delete_problem(problem_id)
    return ApiResponse(code=200, msg="delete success", data={"id": problem_id})
