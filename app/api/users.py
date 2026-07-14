from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ApiResponse, RoleUpdate, UserRegister
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
from app.utils.exceptions import (
    DuplicateUsername,
    InvalidRole,
    PermissionDenied,
    UserNotFound,
)

router = APIRouter(prefix="/api/users", tags=["user"])


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt, hash_val = parts
    return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val


@router.post("/")
async def register(body: UserRegister):
    if len(body.username) < 3 or len(body.username) > 40:
        raise HTTPException(status_code=400, detail="Username must be 3-40 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = get_user_by_username(body.username)
    if existing is not None:
        raise DuplicateUsername(body.username)

    user_id = next_id("usr")
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "user_id": user_id,
        "username": body.username,
        "password": _hash_password(body.password),
        "role": "user",
        "join_time": now.split("T")[0],
        "submit_count": 0,
        "resolve_count": 0,
    }
    save_user(user_id, user_data)
    return ApiResponse(code=200, msg="register success", data={
        "user_id": user_id,
        "username": body.username,
        "join_time": now.split("T")[0],
        "role": "user",
        "submit_count": 0,
        "resolve_count": 0,
    })


@router.get("/")
async def list_users(
    req: Request,
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
):
    require_admin(req)
    all_users = list(get_users().values())
    total = len(all_users)

    # Pagination: both empty = return all; page_size only = first page
    if page is None and page_size is None:
        paged = all_users
    else:
        if page is None:
            page = 1
        page_size = page_size or 20
        start = (page - 1) * page_size
        paged = all_users[start:start + page_size]
    items = []
    for u in paged:
        items.append({
            "user_id": u["user_id"],
            "username": u["username"],
            "join_time": u.get("join_time", ""),
            "submit_count": u.get("submit_count", 0),
            "resolve_count": u.get("resolve_count", 0),
            "role": u.get("role", "user"),
        })
    return ApiResponse(code=200, msg="success", data={"total": total, "users": items})


@router.get("/{user_id}")
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
        "role": u.get("role", "user"),
        "join_time": u.get("join_time", ""),
        "submit_count": u.get("submit_count", 0),
        "resolve_count": u.get("resolve_count", 0),
    })


@router.put("/{user_id}/role")
async def change_user_role(req: Request, user_id: str, body: RoleUpdate):
    admin_user = require_admin(req)
    target = get_user(user_id)
    if target is None:
        raise UserNotFound(user_id)
    allowed_roles = {"admin", "user", "banned"}
    if body.role not in allowed_roles:
        raise InvalidRole(body.role)
    old_role = target.get("role", "user")
    target["role"] = body.role
    save_user(user_id, target)

    add_audit({
        "action": "change_permission",
        "operator": admin_user["user_id"],
        "target_user": user_id,
        "old_role": old_role,
        "new_role": body.role,
        "detail": f"Admin {admin_user['username']} changed user {user_id} role from {old_role} to {body.role}",
    })

    return ApiResponse(code=200, msg="role updated", data={
        "user_id": user_id,
        "role": body.role,
    })


@router.post("/admin")
async def create_admin(req: Request, body: UserRegister):
    admin_user = require_admin(req)
    if get_user_by_username(body.username) is not None:
        raise DuplicateUsername(body.username)

    user_id = next_id("usr")
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "user_id": user_id,
        "username": body.username,
        "password": _hash_password(body.password),
        "role": "admin",
        "join_time": now.split("T")[0],
        "submit_count": 0,
        "resolve_count": 0,
    }
    save_user(user_id, user_data)
    return ApiResponse(code=200, msg="success", data={
        "user_id": user_id,
        "username": body.username,
    })
