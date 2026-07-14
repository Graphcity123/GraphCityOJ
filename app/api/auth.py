from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import ApiResponse, UserLogin
from app.storage import get_user_by_username
from app.utils.auth import SESSION_USER_KEY, get_current_user
from app.utils.exceptions import InvalidCredentials, AccountBanned

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def _verify_password(password: str, stored: str) -> bool:
    import hashlib
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt, hash_val = parts
    return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val


@router.post("/login")
async def login(req: Request, body: UserLogin):
    user = get_user_by_username(body.username)
    if user is None or not body.password:
        raise InvalidCredentials()
    if user.get("role") == "banned":
        raise AccountBanned()
    if not _verify_password(body.password, user["password"]):
        raise InvalidCredentials()

    session_user = {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    }
    req.session[SESSION_USER_KEY] = session_user
    return ApiResponse(code=200, msg="login success", data=session_user)


@router.post("/logout")
async def logout(req: Request):
    get_current_user(req)
    req.session.pop(SESSION_USER_KEY, None)
    return ApiResponse(code=200, msg="logout success", data=None)
