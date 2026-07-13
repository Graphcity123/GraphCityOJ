from __future__ import annotations

from fastapi import HTTPException, status


class BadRequest(HTTPException):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidCredentials(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")


class AccountBanned(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been banned")


class DuplicateUsername(HTTPException):
    def __init__(self, username: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Username '{username}' already exists")


class DuplicateProblem(HTTPException):
    def __init__(self, problem_id: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Problem '{problem_id}' already exists")


class DuplicateLanguage(HTTPException):
    def __init__(self, lang: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Language '{lang}' already exists")


class InvalidRole(HTTPException):
    def __init__(self, role: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role '{role}'")


class SubmissionConditionError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of user_id or problem_id is required",
        )


class ProblemNotFound(HTTPException):
    def __init__(self, problem_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem '{problem_id}' not found",
        )


class SubmissionNotFound(HTTPException):
    def __init__(self, submission_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission '{submission_id}' not found",
        )


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConfigValidationError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class UserNotFound(HTTPException):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found",
        )


class LanguageNotFound(HTTPException):
    def __init__(self, lang_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language '{lang_id}' not found or not supported",
        )
