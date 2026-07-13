from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    ApiResponse,
    PermissionChange,
    UserLogin,
    UserRegister,
)
from app.storage import (
    add_audit,
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

router = APIRouter(prefix="/api/users", tags=["user"])


def _hash_password(password: str) -> str:
    """Simple salted SHA-256 hash."""
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
    if len(body.username) < 3 or len(body.username) > 40:
        raise HTTPException(status_code=400, detail="Username must be 3-40 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
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
        "role": "user",
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


@router.get("/list")
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
            "role": u.get("role", "user"),
        })
    return ApiResponse(code=200, msg="success", data={"total": total, "users": items})


@router.get("/info/{user_id}")
async def get_user_info(req: Request, user_id: str):
    req_user = get_current_user(req)
    u = get_user(user_id)
    if u is None:
        raise UserNotFound(user_id)
    if req_user.get("role") != "admin" and user_id != req_user["user_id"]:
        raise PermissionDenied("Cannot view other users info")
    return ApiResponse(code=200, msg="success", data={
        "user_id": u["user_id"],
        "username": u["username"],
        "email": u.get("email", ""),
        "role": u.get("role", "user"),
        "join_time": u.get("join_time", ""),
        "submit_count": u.get("submit_count", 0),
        "resolve_count": u.get("resolve_count", 0),
    })


@router.put("/permission")
async def change_user_permission(req: Request, body: PermissionChange):
    admin_user = require_admin(req)
    target = get_user(body.user_id)
    if target is None:
        raise UserNotFound(body.user_id)
    allowed_roles = {"admin", "user", "banned", "teacher"}
    if body.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role '{body.role}'")
    old_role = target.get("role", "user")
    target["role"] = body.role
    save_user(body.user_id, target)

    add_audit({
        "action": "change_permission",
        "operator": admin_user["user_id"],
        "target_user": body.user_id,
        "old_role": old_role,
        "new_role": body.role,
        "detail": f"Admin {admin_user['username']} changed user {body.user_id} role from {old_role} to {body.role}",
    })

    return ApiResponse(code=200, msg="permission updated", data=None)
