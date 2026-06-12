import httpx
from datetime import datetime, timezone
from typing import Optional

# WMO Weather code mapping to descriptions and icons
WMO_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌦️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow fall", "🌨️"),
    73: ("Moderate snow fall", "🌨️"),
    75: ("Heavy snow fall", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "🌧️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}

# In-memory cache: {key: (response_data, timestamp)}
_weather_cache: dict[str, tuple[dict, float]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_weather_description(code: int) -> tuple[str, str]:
    """Return (description, icon) for a WMO weather code."""
    return WMO_CODES.get(code, ("Unknown", "🌡️"))


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit, rounded to 1 decimal."""
    return round(c * 9 / 5 + 32, 1)


async def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather from Open-Meteo API."""
    cache_key = f"{lat},{lon}"
    now = datetime.now(timezone.utc).timestamp()

    # Check cache
    if cache_key in _weather_cache:
        data, ts = _weather_cache[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return data

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,relative_humidity_2m"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=auto"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"error": f"Weather fetch failed: {str(e)}"}

    current = data.get("current", {})
    daily = data.get("daily", {})

    temp_c = current.get("temperature_2m", 0)
    code = current.get("weather_code", 0)
    description, icon = _get_weather_description(code)

    high_c = daily.get("temperature_2m_max", [temp_c])[0]
    low_c = daily.get("temperature_2m_min", [temp_c])[0]

    result = {
        "temperature": celsius_to_fahrenheit(temp_c),
        "condition_code": code,
        "condition_description": description,
        "condition_icon": icon,
        "high": celsius_to_fahrenheit(high_c),
        "low": celsius_to_fahrenheit(low_c),
    }

    # Cache the result
    _weather_cache[cache_key] = (result, now)

    return result
