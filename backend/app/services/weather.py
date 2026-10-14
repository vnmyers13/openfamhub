"""Weather from Open-Meteo (no API key), cached ~10 minutes in-process.

The location is a family setting (settings_json["weather"]): a place name
plus latitude/longitude from Open-Meteo's geocoder, and the units. Requests
go only to Open-Meteo's fixed hosts, never to a user-supplied URL.
"""
import time
from typing import Any, Optional

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
CACHE_SECONDS = 600
transport: Optional[httpx.AsyncBaseTransport] = None  # tests swap in a mock

# WMO weather interpretation codes (Open-Meteo docs) → (emoji, words).
WMO: dict[int, tuple[str, str]] = {
    0: ("☀️", "Clear"), 1: ("🌤️", "Mostly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Cloudy"),
    45: ("🌫️", "Fog"), 48: ("🌫️", "Freezing fog"),
    51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Drizzle"), 55: ("🌧️", "Heavy drizzle"),
    56: ("🌧️", "Freezing drizzle"), 57: ("🌧️", "Heavy freezing drizzle"),
    61: ("🌦️", "Light rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Freezing rain"), 67: ("🌧️", "Heavy freezing rain"),
    71: ("🌨️", "Light snow"), 73: ("🌨️", "Snow"), 75: ("❄️", "Heavy snow"), 77: ("🌨️", "Snow grains"),
    80: ("🌦️", "Showers"), 81: ("🌧️", "Heavy showers"), 82: ("⛈️", "Violent showers"),
    85: ("🌨️", "Snow showers"), 86: ("❄️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm with hail"), 99: ("⛈️", "Severe thunderstorm with hail"),
}


def describe(code: Any) -> tuple[str, str]:
    try:
        return WMO.get(int(code), ("🌡️", "Weather"))
    except (TypeError, ValueError):
        return ("🌡️", "Weather")


_cache: dict[tuple, tuple[float, dict]] = {}


def clear_cache() -> None:
    _cache.clear()


async def _get_json(url: str, params: dict) -> Any:
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def forecast(latitude: float, longitude: float, units: str, tz: str) -> dict:
    """Current conditions and a 4-day outlook; cached per place and units."""
    key = (round(latitude, 3), round(longitude, 3), units, tz)
    hit = _cache.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    data = await _get_json(FORECAST_URL, {
        "latitude": latitude, "longitude": longitude, "timezone": tz, "forecast_days": 4,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit" if units == "fahrenheit" else "celsius",
        "wind_speed_unit": "mph" if units == "fahrenheit" else "kmh",
    })
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    emoji, label = describe(cur.get("weather_code"))
    days = []
    for i, day in enumerate(daily.get("time") or []):
        d_emoji, d_label = describe((daily.get("weather_code") or [None])[i])
        days.append({
            "date": day, "emoji": d_emoji, "label": d_label,
            "high": _round((daily.get("temperature_2m_max") or [None])[i]),
            "low": _round((daily.get("temperature_2m_min") or [None])[i]),
            "precip_chance": (daily.get("precipitation_probability_max") or [None])[i],
        })
    result = {
        "temperature": _round(cur.get("temperature_2m")), "emoji": emoji, "label": label,
        "wind": _round(cur.get("wind_speed_10m")), "days": days,
    }
    _cache[key] = (now, result)
    return result


def _round(v: Any) -> Optional[int]:
    return round(v) if isinstance(v, (int, float)) else None


async def find_places(query: str) -> list[dict]:
    data = await _get_json(GEOCODE_URL, {"name": query, "count": 5, "language": "en", "format": "json"})
    out = []
    for r in data.get("results") or []:
        parts = [r.get("name"), r.get("admin1"), r.get("country")]
        out.append({"name": ", ".join(p for p in parts if p), "latitude": r["latitude"], "longitude": r["longitude"]})
    return out
