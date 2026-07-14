from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class User(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole = UserRole.student
    is_active: bool = True
