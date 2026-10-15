"""Phase 12: talking to the family's Home Assistant over its REST API.

The server's HA_URL and HA_TOKEN (a long-lived access token made in Home
Assistant under Profile › Security) come from the environment, like
SECRET_KEY, so the token never lives in the database or the UI. Home
Assistant is the operator's own, usually on the LAN, so its URL isn't
SSRF-checked. Every call has a short timeout and failures raise
`Unavailable` with a sentence a person can read.
"""
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

TIMEOUT = 6  # seconds

# What OpenFamHub can show, and what each kind can be told to do.
CONTROLS: dict[str, set[str]] = {
    "light": {"toggle", "turn_on", "turn_off"},
    "switch": {"toggle", "turn_on", "turn_off"},
    "fan": {"toggle", "turn_on", "turn_off"},
    "input_boolean": {"toggle", "turn_on", "turn_off"},
    "scene": {"turn_on"},
    "script": {"turn_on"},
    "climate": {"set_temperature"},
    "sensor": set(),
    "binary_sensor": set(),
}
SUPPORTED = frozenset(CONTROLS)
RUNNABLE = frozenset({"scene", "script"})  # what a routine can start


class Unavailable(Exception):
    """Home Assistant didn't answer usefully; str() is for people."""


def configured() -> bool:
    return bool((settings.ha_url or "").strip() and (settings.ha_token or "").strip())


def _base() -> str:
    return settings.ha_url.strip().rstrip("/")


def _transport() -> Optional[httpx.AsyncBaseTransport]:
    return None  # tests swap in a fake Home Assistant


async def _request(method: str, path: str, body: Optional[dict] = None) -> Any:
    if not configured():
        raise Unavailable("Home Assistant isn't set up on this server.")
    headers = {"Authorization": f"Bearer {settings.ha_token.strip()}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=_transport()) as client:
            res = await client.request(method, _base() + path, headers=headers, json=body)
    except httpx.HTTPError as exc:
        log.warning("home assistant: %s", type(exc).__name__)
        raise Unavailable("Home Assistant isn't reachable right now.") from exc
    if res.status_code in (401, 403):
        raise Unavailable("Home Assistant refused the access token (check HA_TOKEN).")
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
    if domain == "light" and isinstance(attrs.get("brightness"), (int, float)):
        out["brightness"] = round(attrs["brightness"] / 255 * 100)
    if domain == "climate":
        for key, name in (("current_temperature", "current_temperature"), ("temperature", "target_temperature"),
                          ("min_temp", "min_temp"), ("max_temp", "max_temp")):
            if attrs.get(key) is not None:
                out[name] = attrs[key]
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
