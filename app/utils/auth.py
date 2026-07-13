from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status


class UserRole(str, Enum):
    admin = "admin"
    teacher = "teacher"
    student = "student"
    banned = "banned"


SESSION_USER_KEY = "user"


def get_current_user(request: Request) -> dict[str, Any]:
    """Get current user from session. Raises 401 if not logged in."""
    user = request.session.get(SESSION_USER_KEY)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login first",
        )
    # Check if banned
    if user.get("role") == "banned":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been banned",
        )
    return user


def get_current_user_or_none(request: Request) -> dict[str, Any] | None:
    """Get current user or None if not logged in."""
    return request.session.get(SESSION_USER_KEY)


def require_admin(request: Request) -> dict[str, Any]:
    """Get current user and ensure admin role."""
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )
    return user


def require_login(request: Request) -> dict[str, Any]:
    """Get current user, must be logged in."""
    return get_current_user(request)
