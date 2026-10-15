"""Admin › Settings: server settings changed in the app (services/server_config.py).

Admin only, behind the password gate. Secrets are write-only: send a value to
set one, "" to clear it, leave it out to keep it. A setting fixed in `.env`
can't be changed here (409).
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.jobs.backup import reschedule_backup
from app.models.user import User
from app.services import home_assistant as ha
from app.services import notify
from app.services import server_config as cfg

router = APIRouter()

BACKUP_FIELDS = {"backup_time", "backup_retention_days"}


@router.get("")
async def read(admin: User = Depends(require_role("admin"))):
    return cfg.describe()


@router.put("")
async def change(changes: dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db),
                 admin: User = Depends(require_role("admin"))):
    try:
        clean = cfg.validate(changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    fixed = sorted(name for name in clean if cfg.locked(name))
    if fixed:
        raise HTTPException(status_code=409, detail=f"Set in .env, change it there: {', '.join(fixed)}")
    await cfg.save(db, clean)
    if BACKUP_FIELDS & clean.keys():
        await reschedule_backup(db)
    return cfg.describe()


@router.post("/test/{what}")
async def try_it(what: str, admin: User = Depends(require_role("admin"))):
    """Check a connection with what's saved now: Home Assistant answers, or a
    test message reaches the admin's own ntfy topic or email address."""
    if what == "home-assistant":
        if not ha.configured():
            return {"ok": False, "message": "Home Assistant isn't set up: add its address and token first."}
        try:
            await ha.check()
        except ha.Unavailable as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": "Connected."}
    payload = {"title": "OpenFamHub test", "body": "This is a test from Admin › Settings.", "url": "/admin/settings"}
    prefs = notify.notification_prefs(admin)
    if what == "ntfy":
        if not notify.ntfy_server():
            return {"ok": False, "message": "ntfy isn't set up: add the server first."}
        if not prefs.ntfy_topic:
            return {"ok": False, "message": "Add your own ntfy topic in My settings › Notifications first."}
        ok = await notify.send_ntfy(prefs.ntfy_topic, payload)
        return {"ok": ok, "message": f"Sent to your topic {prefs.ntfy_topic}." if ok else "The ntfy server didn't take it; check its address and token."}
    if what == "email":
        if not notify.email_ready():
            return {"ok": False, "message": "Email is not set up: add the server and the From address first."}
        if not prefs.email_to:
            return {"ok": False, "message": "Add your email address in My settings › Notifications first."}
        ok = await notify.send_email(prefs.email_to, payload)
        return {"ok": ok, "message": f"Sent to {prefs.email_to}." if ok else "The email server didn't take it; check the server, port, security, user and password."}
    raise HTTPException(status_code=404, detail="Nothing to test by that name")
