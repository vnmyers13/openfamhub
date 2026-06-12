import pytest
from unittest.mock import patch, AsyncMock
import httpx
from app.services.weather import (
    fetch_weather,
    celsius_to_fahrenheit,
    _get_weather_description,
    WMO_CODES,
)


def test_celsius_to_fahrenheit():
    assert celsius_to_fahrenheit(0) == 32.0
    assert celsius_to_fahrenheit(100) == 212.0
    assert celsius_to_fahrenheit(20) == 68.0


def test_wmo_codes_coverage():
    """All defined WMO codes should have descriptions."""
    for code in WMO_CODES:
        desc, icon = _get_weather_description(code)
        assert desc != "Unknown"
        assert len(icon) >= 1


def test_unknown_wmo_code():
    desc, icon = _get_weather_description(999)
    assert desc == "Unknown"
    assert icon == "🌡️"


@pytest.mark.asyncio
async def test_fetch_weather_success():
    mock_response = {
        "current": {
            "temperature_2m": 22.5,
            "weather_code": 2,
            "relative_humidity_2m": 55,
        },
        "daily": {
            "temperature_2m_max": [28.0],
            "temperature_2m_min": [18.0],
        },
    }
    with patch("app.services.weather.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = AsyncMock(json=lambda: mock_response, raise_for_status=AsyncMock())
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_weather(41.8, -87.6)

        assert result["temperature"] == 72.5
        assert result["high"] == 82.4
        assert result["low"] == 64.4
        assert result["condition_icon"] == "⛅"


@pytest.mark.asyncio
async def test_fetch_weather_api_failure():
    from app.services.weather import _weather_cache
    _weather_cache.clear()
    with patch("app.services.weather.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get.side_effect = httpx.ConnectError("Connection refused")

        result = await fetch_weather(41.8, -87.6)

        assert "error" in result
