"""Phase 12: talking to the family's Home Assistant over its REST API.

The server's HA_URL and HA_TOKEN (a long-lived access token made in Home
Assistant under Profile › Security) come from the environment, like
SECRET_KEY, so the token never lives in the database or the UI. Home
Assistant is the operator's own, usually on the LAN, so its URL isn't
SSRF-checked. Every call has a short timeout and failures raise
`Unavailable` with a sentence a person can read.
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.services import server_config as cfg

log = logging.getLogger(__name__)

TIMEOUT = 6  # seconds

# What OpenFamHub can show, and what each kind can be told to do.
CONTROLS: dict[str, set[str]] = {
    "light": {"toggle", "turn_on", "turn_off", "set_brightness"},
    "switch": {"toggle", "turn_on", "turn_off"},
    "fan": {"toggle", "turn_on", "turn_off"},
    "input_boolean": {"toggle", "turn_on", "turn_off"},
    "scene": {"turn_on"},
    "script": {"turn_on"},
    "climate": {"set_temperature", "set_hvac_mode"},
    "sensor": set(),
    "binary_sensor": set(),
}
SUPPORTED = frozenset(CONTROLS)
RUNNABLE = frozenset({"scene", "script"})  # what a routine can start


class Unavailable(Exception):
    """Home Assistant didn't answer usefully; str() is for people."""


def configured() -> bool:
    return bool((cfg.get("ha_url") or "").strip() and (cfg.get("ha_token") or "").strip())


def _base() -> str:
    return cfg.get("ha_url").strip().rstrip("/")


def _transport() -> Optional[httpx.AsyncBaseTransport]:
    return None  # tests swap in a fake Home Assistant


async def _request(method: str, path: str, body: Optional[dict] = None) -> Any:
    if not configured():
        raise Unavailable("Home Assistant isn't set up on this server.")
    headers = {"Authorization": f"Bearer {cfg.get("ha_token").strip()}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=_transport()) as client:
            res = await client.request(method, _base() + path, headers=headers, json=body)
    except httpx.HTTPError as exc:
        log.warning("home assistant: %s", type(exc).__name__)
        raise Unavailable("Home Assistant isn't reachable right now.") from exc
    if res.status_code in (401, 403):
        raise Unavailable("Home Assistant refused the access token; check the token.")
    if res.status_code == 404:
        return None
    if res.status_code >= 300:
        log.warning("home assistant: HTTP %s on %s", res.status_code, path)
        raise Unavailable(f"Home Assistant answered with an error (HTTP {res.status_code}).")
    try:
        return res.json()
    except ValueError as exc:
        raise Unavailable("Home Assistant sent something unexpected.") from exc


async def check() -> None:
    await _request("GET", "/api/")


def domain_of(entity_id: str) -> str:
    return entity_id.split(".", 1)[0]


def brief(raw: dict) -> dict:
    """For the admin's picker."""
    return {"entity_id": raw["entity_id"], "name": (raw.get("attributes") or {}).get("friendly_name") or raw["entity_id"],
            "domain": domain_of(raw["entity_id"]), "state": raw.get("state")}


def view(raw: dict) -> dict:
    """For the cards: the state plus what each kind needs to show."""
    attrs = raw.get("attributes") or {}
    out = brief(raw)
    domain = out["domain"]
    if attrs.get("unit_of_measurement"):
        out["unit"] = attrs["unit_of_measurement"]
    if attrs.get("device_class"):
        out["device_class"] = attrs["device_class"]
    if domain == "light":
        modes = attrs.get("supported_color_modes")
        out["dimmable"] = any(m != "onoff" for m in modes) if isinstance(modes, list) and modes else "brightness" in attrs
        if isinstance(attrs.get("brightness"), (int, float)):
            out["brightness"] = round(attrs["brightness"] / 255 * 100)
    if domain == "climate":
        for key, name in (("current_temperature", "current_temperature"), ("temperature", "target_temperature"),
                          ("min_temp", "min_temp"), ("max_temp", "max_temp")):
            if attrs.get(key) is not None:
                out[name] = attrs[key]
        if isinstance(attrs.get("hvac_modes"), list):
            out["hvac_modes"] = [str(m) for m in attrs["hvac_modes"]]
        out["unit"] = attrs.get("temperature_unit") or out.get("unit")
        if out["unit"] is None:
            del out["unit"]
    return out


def missing(entity_id: str) -> dict:
    return {"entity_id": entity_id, "name": entity_id, "domain": domain_of(entity_id), "state": "unavailable"}


async def all_states() -> list[dict]:
    return [s for s in (await _request("GET", "/api/states") or []) if isinstance(s, dict) and "entity_id" in s]


async def states_for(entity_ids: list[str]) -> list[dict]:
    by_id = {s["entity_id"]: s for s in await all_states()}
    return [view(by_id[e]) if e in by_id else missing(e) for e in entity_ids]


async def state_of(entity_id: str) -> dict:
    raw = await _request("GET", f"/api/states/{entity_id}")
    return view(raw) if raw else missing(entity_id)


async def call(entity_id: str, service: str, **data: Any) -> None:
    await _request("POST", f"/api/services/{domain_of(entity_id)}/{service}", {"entity_id": entity_id, **data})


HISTORY_POINTS = 48


async def history(entity_id: str, hours: int = 24) -> dict:
    """A numeric sensor's last `hours`, thinned to at most HISTORY_POINTS [time, value] pairs."""
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    params = f"?filter_entity_id={entity_id}&minimal_response&no_attributes"
    rows = await _request("GET", f"/api/history/period/{start}{params}") or []
    series = rows[0] if rows and isinstance(rows[0], list) else []
    points: list[list] = []
    for row in series:
        try:
            value = float(row.get("state"))
        except (TypeError, ValueError):
            continue  # "unavailable", "unknown"
        if math.isfinite(value):
            points.append([row.get("last_changed") or row.get("last_updated"), value])
    values = [v for _, v in points]
    step = max(1, math.ceil(len(points) / HISTORY_POINTS))
    return {"entity_id": entity_id, "points": points[::step][:HISTORY_POINTS],
            "low": min(values) if values else None, "high": max(values) if values else None}
