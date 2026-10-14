"""Edits made offline carry `base`: the item as the person last saw it. If
the item has changed on the server since (anyone changed any of those
fields), the edit gets 409 with the current item instead of overwriting it,
and the app asks: keep mine, keep theirs, or merge (Phase 9). An edit
without `base` (online, or "keep mine") applies as before."""
from datetime import date, datetime
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder


def _norm(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def check_base(base: Optional[dict], current: Any) -> None:
    """Raise 409 when any field in `base` differs from `current` (a response model)."""
    if not base:
        return
    now = jsonable_encoder(current)
    changed = sorted(k for k, v in base.items() if k in now and _norm(now[k]) != _norm(v))
    if changed:
        raise HTTPException(status_code=409, detail={
            "message": "Someone else changed this while you were offline",
            "fields": changed,
            "current": now,
        })
