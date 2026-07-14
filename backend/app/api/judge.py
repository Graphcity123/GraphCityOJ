from __future__ import annotations

import copy

from fastapi import APIRouter, Request

from app.schemas import (
    ApiResponse,
    LanguageCreate,
)
from app.storage import get_languages, save_language
from app.utils.auth import require_login
from app.utils.exceptions import DuplicateLanguage, LanguageNotFound

router = APIRouter(prefix="/api/languages", tags=["languages"])


@router.get("/")
async def list_languages():
    langs = await get_languages()
    names = sorted(langs.keys())
    return ApiResponse(code=200, msg="success", data={"name": names})


@router.post("/")
async def register_language(req: Request, body: LanguageCreate):
    require_login(req)
    if body.name in await get_languages():
        raise DuplicateLanguage(body.name)
    data = body.model_dump()
    await save_language(body.name, data)
    return ApiResponse(code=200, msg="language registered", data={"name": body.name})
