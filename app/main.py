from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.api import problems, judge, submissions, users, logs, admin, auth

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
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
