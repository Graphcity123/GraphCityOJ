from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    ApiResponse,
    PagedData,
    RoleChange,
    UserLogin,
    UserRegister,
)
from app.storage import (
    get_user,
    get_user_by_username,
    get_users,
    next_id,
    save_user,
)
from app.utils.auth import (
    SESSION_USER_KEY,
    get_current_user,
    require_admin,
)
from app.utils.exceptions import PermissionDenied, UserNotFound

router = APIRouter(prefix="/api/users", tags=["users"])


def _hash_password(password: str) -> str:
    """Simple salted SHA-256 hash (bcrypt preferred but kept simple for this experiment)."""
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt, hash_val = parts
    return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val


@router.post("/register")
async def register(body: UserRegister):
    existing = get_user_by_username(body.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' already exists")

    user_id = next_id("usr")
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "user_id": user_id,
        "username": body.username,
        "password": _hash_password(body.password),
        "email": body.email,
        "role": "student",
        "join_time": now.split("T")[0],
        "submit_count": 0,
        "resolve_count": 0,
    }
    save_user(user_id, user_data)
    return ApiResponse(code=200, msg="user registered successfully", data={"user_id": user_id})


@router.post("/login")
async def login(req: Request, body: UserLogin):
    user = get_user_by_username(body.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.get("role") == "banned":
        raise HTTPException(status_code=403, detail="Account has been banned")
    if not _verify_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Store session
    session_user = {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }
    req.session[SESSION_USER_KEY] = session_user
    return ApiResponse(code=200, msg="login success", data=session_user)


@router.get("/logout")
async def logout(req: Request):
    req.session.pop(SESSION_USER_KEY, None)
    return ApiResponse(code=200, msg="logout success", data=None)


@router.get("/")
async def list_users(
    req: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    require_admin(req)
    all_users = list(get_users().values())
    total = len(all_users)
    start = (page - 1) * page_size
    items = []
    for u in all_users[start:start + page_size]:
        items.append({
            "user_id": u["user_id"],
            "username": u["username"],
            "join_time": u.get("join_time", ""),
            "submit_count": u.get("submit_count", 0),
            "resolve_count": u.get("resolve_count", 0),
            "role": u.get("role", "student"),
        })
    return ApiResponse(code=200, msg="success", data=PagedData(total=total, items=items).model_dump())


@router.get("/{user_id}")
async def get_user_info(req: Request, user_id: str):
    req_user = get_current_user(req)
    u = get_user(user_id)
    if u is None:
        raise UserNotFound(user_id)
    # Permission: self or admin
    if req_user.get("role") != "admin" and user_id != req_user["user_id"]:
        raise PermissionDenied("Cannot view other users info")
    return ApiResponse(code=200, msg="success", data={
        "user_id": u["user_id"],
        "username": u["username"],
        "email": u.get("email", ""),
        "role": u.get("role", "student"),
        "join_time": u.get("join_time", ""),
        "submit_count": u.get("submit_count", 0),
        "resolve_count": u.get("resolve_count", 0),
    })


@router.put("/{user_id}/role")
async def change_user_role(req: Request, user_id: str, body: RoleChange):
    require_admin(req)
    u = get_user(user_id)
    if u is None:
        raise UserNotFound(user_id)
    allowed_roles = {"admin", "student", "banned", "teacher"}
    if body.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role '{body.role}'")
    u["role"] = body.role
    save_user(user_id, u)
    return ApiResponse(code=200, msg="role updated", data=None)
