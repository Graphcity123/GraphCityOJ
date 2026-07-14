from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.schemas import ApiResponse, ProblemCreate
from app.storage import delete_problem, get_problem, get_problems, save_problem
from app.utils.auth import require_login
from app.utils.exceptions import DuplicateProblem, PermissionDenied, ProblemNotFound

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("/")
async def list_problems(req: Request):
    require_login(req)
    all_problems = list(get_problems().values())
    items = [{"id": p["id"], "title": p["title"]} for p in all_problems]
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
    return ApiResponse(code=200, msg="success", data={
        "id": p["id"],
        "title": p.get("title", ""),
        "description": p.get("description", ""),
        "input_description": p.get("input_description", ""),
        "output_description": p.get("output_description", ""),
        "samples": p.get("samples", []),
        "constraints": p.get("constraints", ""),
        "testcases": p.get("testcases", []),
        "hint": p.get("hint", ""),
        "source": p.get("source", ""),
        "tags": p.get("tags", []),
        "time_limit": p.get("time_limit", 3.0),
        "memory_limit": p.get("memory_limit", 128),
        "author": p.get("author", ""),
        "difficulty": p.get("difficulty", ""),
    })


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
