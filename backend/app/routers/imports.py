"""Smart Import: a link or pasted text → a recipe or event draft to review.

Pages are fetched with core.safe_fetch (SSRF guard on every hop, pinned
connection, 3 MB cap, 20 s timeout); parsing is in integrations.smart_import.
Nothing is saved here.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.safe_fetch import fetch_public
from app.core.security import get_current_user
from app.integrations.smart_import import NothingToImport, parse_event, parse_recipe
from app.models.family import Family
from app.models.user import User
from app.schemas.meals import EventDraft, ImportRequest, RecipeDraft

router = APIRouter()

MAX_PAGE_BYTES = 3_000_000
HEADERS = {
    "User-Agent": "OpenFamHub/1.0 (family organizer; recipe and event import)",
    "Accept": "text/html,application/xhtml+xml,application/ld+json;q=0.9,*/*;q=0.5",
}


def importer(user: User = Depends(get_current_user)) -> User:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't import")
    return user


async def page_text(data: ImportRequest) -> str:
    if not data.url:
        return data.text or ""
    try:
        body = await fetch_public(data.url, max_bytes=MAX_PAGE_BYTES, fetch_label="That page", size_label="That page",
                                  timeout=20.0, headers=HEADERS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Couldn't read that link: {exc}")
    except Exception:  # noqa: BLE001  - timeouts, TLS and connection errors
        raise HTTPException(status_code=400, detail="Couldn't read that link")
    return body.decode("utf-8", errors="replace")


@router.post("/recipe", response_model=RecipeDraft)
async def import_recipe(data: ImportRequest, user: User = Depends(importer)):
    content = await page_text(data)
    try:
        return RecipeDraft(**parse_recipe(content, source_url=data.url))
    except NothingToImport as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/event", response_model=EventDraft)
async def import_event(data: ImportRequest, db: AsyncSession = Depends(get_db), user: User = Depends(importer)):
    family = await db.get(Family, user.family_id)
    content = await page_text(data)
    try:
        return EventDraft(**parse_event(content, family.timezone if family else "UTC", source_url=data.url))
    except NothingToImport as exc:
        raise HTTPException(status_code=400, detail=str(exc))
