from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.config import settings
from app.schemas import ApiResponse, ProblemCreate
from app.storage import delete_problem, get_problem, get_problems, save_problem
from app.utils.auth import require_admin, require_login
from app.utils.exceptions import DuplicateProblem, PermissionDenied, ProblemNotFound

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("/")
async def list_problems(req: Request):
    require_login(req)
    all_problems = list((await get_problems()).values())
    items = [{"id": p["id"], "title": p["title"]} for p in all_problems]
    return ApiResponse(code=200, msg="success", data=items)


@router.post("/")
async def create_problem(req: Request, body: ProblemCreate):
    require_login(req)
    problem_id = body.id
    if await get_problem(problem_id) is not None:
        raise DuplicateProblem(problem_id)
    now = datetime.now(timezone.utc).isoformat()
    data = body.model_dump()
    data["public_cases"] = True
    data["created_at"] = now
    data["created_by"] = req.session.get("user", {}).get("user_id", "")
    await save_problem(problem_id, data)
    return ApiResponse(code=200, msg="add success", data={"id": problem_id})


@router.post("/upload")
async def upload_problem(
    req: Request,
    problem_md: UploadFile = File(...),
    testcases_zip: UploadFile = File(...),
):
    """Upload a problem with .md description and .zip test cases."""
    require_admin(req)

    # Validate file types
    if not problem_md.filename or not problem_md.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="problem_md must be a .md file")
    if not testcases_zip.filename or not testcases_zip.filename.endswith(".zip"):
        raise HTTPException(status_code=400,
                            detail="testcases_zip must be a .zip file")

    # Generate auto ID — numeric sequential
    existing = (await get_problems()).keys()
    nums = [int(k) for k in existing if k.isdigit()]
    folder_id = str(max(nums) + 1) if nums else "1"
    prob_dir = settings.problems_dir / folder_id
    prob_dir.mkdir(parents=True, exist_ok=True)

    # Save problem.md
    md_content = await problem_md.read()
    (prob_dir / "problem.md").write_bytes(md_content)
    md_text = md_content.decode("utf-8", errors="replace")

    # Parse YAML front-matter from markdown
    metadata = _parse_md_frontmatter(md_text)

    # Extract testcases.zip
    zip_content = await testcases_zip.read()
    testcase_count = _extract_and_validate_testcases(
        zip_content, prob_dir)

    # Create DB record
    now = datetime.now(timezone.utc).isoformat()
    user_id = req.session.get("user", {}).get("user_id", "")
    data = {
        "id": folder_id,
        "title": metadata.get("title", folder_id),
        "description": metadata.get("description", md_text),
        "input_description": metadata.get("input_description", ""),
        "output_description": metadata.get("output_description", ""),
        "constraints": metadata.get("constraints", ""),
        "hint": metadata.get("hint", ""),
        "source": metadata.get("source", ""),
        "author": metadata.get("author", ""),
        "difficulty": metadata.get("difficulty", "easy"),
        
        "samples": metadata.get("samples", []),
        "time_limit": float(metadata.get("time_limit", 1.0)),
        "memory_limit": int(metadata.get("memory_limit", 256)),
        "testcase_count": testcase_count,
        "public_cases": True,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    await save_problem(folder_id, data)

    # Write config.json
    _write_config(prob_dir, data)

    return ApiResponse(code=200, msg="upload success", data={"id": folder_id})


@router.get("/{problem_id}")
async def get_problem_detail(req: Request, problem_id: str):
    require_login(req)
    p = await get_problem(problem_id)
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
    if await get_problem(problem_id) is None:
        raise ProblemNotFound(problem_id)
    await delete_problem(problem_id)
    # Also delete disk files
    prob_dir = settings.problems_dir / problem_id
    if prob_dir.exists():
        shutil.rmtree(prob_dir, ignore_errors=True)
    return ApiResponse(code=200, msg="delete success", data={"id": problem_id})


# ── Helpers ───────────────────────────────────────────────────

def _parse_md_frontmatter(text: str) -> dict:
    """Parse YAML-style front matter from markdown (between --- lines)."""
    result: dict = {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return result
    # Find closing ---
    end = 1
    while end < len(lines) and lines[end].strip() != "---":
        end += 1
    if end >= len(lines):
        return result

    fm_lines = lines[1:end]
    for line in fm_lines:
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            # Parse lists [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            result[key] = val

    # Put the body (after front matter) into description
    body = "\n".join(lines[end + 1:]).strip()
    if body:
        result["description"] = body

    return result


def _extract_and_validate_testcases(zip_bytes: bytes,
                                    prob_dir: Path) -> int:
    """Extract testcases.zip, validate N.in/N.out pairs, return count."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(temp_dir)

        files = os.listdir(temp_dir)
        in_files = sorted([f for f in files if f.endswith(".in")])
        out_files = sorted([f for f in files if f.endswith(".out")])

        if not in_files:
            raise HTTPException(status_code=400,
                                detail="ZIP must contain at least one .in file")

        # Validate pairing
        in_nums = set()
        for f in in_files:
            try:
                n = int(f[:-3])
                in_nums.add(n)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid test case name: {f}, expected N.in")

        out_nums = set()
        for f in out_files:
            try:
                n = int(f[:-4])
                out_nums.add(n)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid test case name: {f}, expected N.out")

        if in_nums != out_nums:
            raise HTTPException(
                status_code=400,
                detail=f"Mismatched test cases: .in has {sorted(in_nums)}, "
                       f".out has {sorted(out_nums)}")

        # Move files to problem directory
        for n in sorted(in_nums):
            src_in = temp_dir / f"{n}.in"
            src_out = temp_dir / f"{n}.out"
            shutil.move(str(src_in), str(prob_dir / f"{n}.in"))
            shutil.move(str(src_out), str(prob_dir / f"{n}.out"))

        return len(in_nums)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _write_config(prob_dir: Path, data: dict) -> None:
    """Write config.json to the problem directory."""
    config = {k: data[k] for k in (
        "id", "title", "time_limit", "memory_limit",
        "difficulty", "author", "testcase_count",
    ) if k in data}
    (prob_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

