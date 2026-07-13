from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.api import problems, judge, submissions, users, logs, admin

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
