from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.api import problems, judge, submissions, users, logs, admin, auth
from app.storage import get_user, get_languages


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    from app.db.database import init_db
    await init_db()

    # Create default admin and languages on startup if not exist
    if await get_user("admin") is None:
        from app.api.admin import _create_default_admin as _cda
        await _cda()
    if not await get_languages():
        from app.api.admin import _register_default_languages as _rdl
        await _rdl()

    # Ensure default problem exists
    from app.storage import get_problem, save_problem
    if await get_problem("1") is None:
        await save_problem("1", {
            "id": "1", "title": "A+B Problem",
            "description": "", "input_description": "",
            "output_description": "", "constraints": "",
            "samples": [{"input": "1 2", "output": "3"}],
            "testcases": [{"input": "1 2", "output": "3"}],
            "testcase_count": 1, "time_limit": 1.0, "memory_limit": 256,
            "difficulty": "beginner",
        })
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Register routers
app.include_router(problems.router)
app.include_router(judge.router)
app.include_router(submissions.router)
app.include_router(users.router)
app.include_router(logs.router)
app.include_router(admin.router)
app.include_router(auth.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"code": 400, "msg": str(exc.errors()), "data": None},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "Internal server error", "data": None},
    )
