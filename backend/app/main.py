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

    # Sync problems from disk to DB
    from app.storage import get_problem, get_problems, save_problem
    from app.config import settings
    import logging
    _log = logging.getLogger("uvicorn")
    if settings.problems_dir.exists():
        _log.info(f"Scanning problems dir: {settings.problems_dir}")
        for folder in sorted(settings.problems_dir.iterdir()):
            if not folder.is_dir():
                continue
            pid = folder.name
            if not pid.isdigit():
                _log.info(f"  Skip non-numeric: {pid}")
                continue
            if await get_problem(pid) is not None:
                _log.info(f"  Already in DB: {pid}")
                continue
            _log.info(f"  Registering problem: {pid}")
            # Discover testcase count and config from disk
            tc_count = len([f for f in folder.iterdir()
                           if f.name.endswith(".in")])
            cfg_file = folder / "config.json"
            title = pid
            time_limit = 1.0
            memory_limit = 256
            difficulty = "easy"
            if cfg_file.exists():
                import json
                try:
                    cfg = json.loads(cfg_file.read_text())
                    title = cfg.get("title", pid)
                    time_limit = cfg.get("time_limit", 1.0)
                    memory_limit = cfg.get("memory_limit", 256)
                    difficulty = cfg.get("difficulty", "easy")
                except Exception:
                    pass
            samples = []
            if tc_count > 0:
                in1 = folder / "1.in"
                out1 = folder / "1.out"
                if in1.exists() and out1.exists():
                    samples = [{
                        "input": in1.read_text().strip(),
                        "output": out1.read_text().strip(),
                    }]
            try:
                await save_problem(pid, {
                    "id": pid, "title": title,
                    "description": "", "input_description": "",
                    "output_description": "", "constraints": "",
                    "samples": samples,
                    "testcases": [],
                    "testcase_count": tc_count,
                    "time_limit": time_limit, "memory_limit": memory_limit,
                    "difficulty": difficulty,
                })
                _log.info(f"    Registered: {pid} ({title}, {tc_count} testcases)")
            except Exception as e:
                _log.error(f"    Failed to register {pid}: {e}")
    else:
        _log.warning(f"Problems dir not found: {settings.problems_dir}")
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
