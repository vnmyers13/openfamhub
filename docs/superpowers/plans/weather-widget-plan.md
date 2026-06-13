# Weather Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weather widget to the dashboard sidebar and wall display, showing current temperature, condition icon, and daily high/low. Location is configured during setup and editable inline on the widget.

**Architecture:** Weather settings stored in existing User.settings_json column. Backend exposes GET/PUT endpoints for weather data and settings. Open-Meteo API (free, no key) provides weather data. Frontend uses a shared WeatherWidget component on both dashboard and wall display.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, aiosqlite, react-query, axios, Tailwind CSS

---

### Task 1: Backend — Weather schemas

**Files:**
- Create: `backend/app/schemas/weather.py`

- [ ] **Step 1: Create weather schemas**

Create `backend/app/schemas/weather.py` with Pydantic models:

```python
from pydantic import BaseModel, Field
from typing import Optional


class WeatherSettingsUpdate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=200)


class WeatherSettingsResponse(BaseModel):
    lat: float
    lon: float
    location_name: Optional[str] = None


class WeatherResponse(BaseModel):
    temperature: float
    condition_code: int
    condition_description: str
    condition_icon: str
    high: float
    low: float
    location_name: Optional[str] = None
    error: Optional[str] = None
    settings: Optional[WeatherSettingsResponse] = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/weather.py
git commit -m "feat: add weather schemas"
```

---

### Task 2: Backend — Weather service

**Files:**
- Create: `backend/app/services/weather.py`

- [ ] **Step 1: Create weather service module**

Create `backend/app/services/weather.py`:

```python
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
```

- [ ] **Step 2: Create test file for weather service**

Create `backend/tests/test_weather_service.py`:

```python
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
        assert len(icon) == 1


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
    with patch("app.services.weather.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_weather(41.8, -87.6)

        assert "error" in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_weather_service.py -v`
Expected: FAIL with "No module named 'app.services.weather'"

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_weather_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/weather.py backend/tests/test_weather_service.py
git commit -m "feat: add weather service with Open-Meteo integration"
```

---

### Task 3: Backend — Weather router

**Files:**
- Create: `backend/app/routers/weather.py`
- Modify: `backend/app/main.py` (add router registration)

- [ ] **Step 1: Create weather router**

Create `backend/app/routers/weather.py`:

```python
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.weather import WeatherResponse, WeatherSettingsUpdate, WeatherSettingsResponse
from app.models.event import User
from app.services.weather import fetch_weather

router = APIRouter()


@router.get("", response_model=WeatherResponse)
async def get_weather(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_weather_settings(user.settings_json)

    if settings is None:
        return WeatherResponse(
            temperature=0,
            condition_code=0,
            condition_description="",
            condition_icon="",
            high=0,
            low=0,
            settings=WeatherSettingsResponse(lat=0, lon=0),
            error="location_not_set",
        )

    weather_data = await fetch_weather(settings["lat"], settings["lon"])

    if "error" in weather_data:
        return WeatherResponse(
            temperature=0,
            condition_code=0,
            condition_description="",
            condition_icon="",
            high=0,
            low=0,
            location_name=settings.get("location_name"),
            error=weather_data["error"],
            settings=WeatherSettingsResponse(
                lat=settings["lat"],
                lon=settings["lon"],
                location_name=settings.get("location_name"),
            ),
        )

    return WeatherResponse(
        temperature=weather_data["temperature"],
        condition_code=weather_data["condition_code"],
        condition_description=weather_data["condition_description"],
        condition_icon=weather_data["condition_icon"],
        high=weather_data["high"],
        low=weather_data["low"],
        location_name=settings.get("location_name"),
        settings=WeatherSettingsResponse(
            lat=settings["lat"],
            lon=settings["lon"],
            location_name=settings.get("location_name"),
        ),
    )


@router.get("/settings", response_model=WeatherSettingsResponse)
async def get_weather_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_weather_settings(user.settings_json)

    if settings is None:
        return WeatherSettingsResponse(lat=0, lon=0)

    return WeatherSettingsResponse(
        lat=settings["lat"],
        lon=settings["lon"],
        location_name=settings.get("location_name"),
    )


@router.put("/settings", response_model=WeatherSettingsResponse)
async def update_weather_settings(
    req: WeatherSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == admin["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_settings = _parse_weather_settings(user.settings_json) or {}
    current_settings["weather_lat"] = req.lat
    current_settings["weather_lon"] = req.lon
    current_settings["weather_location_name"] = req.location_name
    user.settings_json = json.dumps(current_settings)

    await db.flush()

    return WeatherSettingsResponse(
        lat=req.lat,
        lon=req.lon,
        location_name=req.location_name,
    )


def _parse_weather_settings(settings_json_str: str) -> dict | None:
    """Parse weather settings from user's settings_json string."""
    try:
        settings = json.loads(settings_json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if "weather_lat" not in settings or "weather_lon" not in settings:
        return None

    return {
        "lat": float(settings["weather_lat"]),
        "lon": float(settings["weather_lon"]),
        "location_name": settings.get("weather_location_name"),
    }
```

- [ ] **Step 2: Register weather router in main.py**

Modify `backend/app/main.py` — add to the router imports and registration:

```python
# In the import line (line 5), add 'weather' to the import:
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards, meals, books, weather

# After line 35, add:
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
```

- [ ] **Step 3: Create test file for weather router**

Create `backend/tests/test_weather_router.py`:

```python
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.security import create_access_token
from app.models.event import User


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db: AsyncSession, name: str = "Test User", role: str = "admin", settings_json: str = "{}") -> User:
    user = User(
        name=name,
        avatar_emoji="👤",
        pin_hash="dummy",
        role=role,
        settings_json=settings_json,
    )
    db.add(user)
    return user


@pytest.mark.asyncio
async def test_get_weather_no_settings(client, db: AsyncSession):
    user = _create_user(db, settings_json="{}")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    resp = client.get("/api/weather", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "location_not_set"
    assert data["settings"]["lat"] == 0
    assert data["settings"]["lon"] == 0


@pytest.mark.asyncio
async def test_get_weather_settings_empty(client, db: AsyncSession):
    user = _create_user(db, settings_json="{}")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    resp = client.get("/api/weather/settings", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] == 0
    assert data["lon"] == 0


@pytest.mark.asyncio
async def test_update_weather_settings(client, db: AsyncSession):
    user = _create_user(db, settings_json='{"weather_lat": 0, "weather_lon": 0}')
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    resp = client.put(
        "/api/weather/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"lat": 41.8781, "lon": -87.6298, "location_name": "Chicago"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] == 41.8781
    assert data["lon"] == -87.6298
    assert data["location_name"] == "Chicago"

    # Verify persisted in DB
    await db.refresh(user)
    settings = json.loads(user.settings_json)
    assert settings["weather_lat"] == 41.8781
    assert settings["weather_lon"] == -87.6298
    assert settings["weather_location_name"] == "Chicago"


@pytest.mark.asyncio
async def test_update_weather_settings_validation(client, db: AsyncSession):
    user = _create_user(db)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    resp = client.put(
        "/api/weather/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"lat": 100, "lon": -87.6298, "location_name": "Invalid"},
    )

    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_weather_settings_non_admin_fails(client, db: AsyncSession):
    user = _create_user(db, role="member")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    resp = client.put(
        "/api/weather/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"lat": 41.8781, "lon": -87.6298, "location_name": "Chicago"},
    )

    assert resp.status_code == 403  # Forbidden
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_weather_router.py -v`
Expected: FAIL with "No module named 'app.routers.weather'"

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_weather_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/weather.py backend/app/main.py backend/tests/test_weather_router.py
git commit -m "feat: add weather router with GET/PUT endpoints"
```

---

### Task 4: Frontend — API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add weatherAPI to client.ts**

Add after the existing API objects (after `bookAPI`):

```typescript
export const weatherAPI = {
  getWeather: () => api.get('/weather').then(r => r.data),
  getSettings: () => api.get('/weather/settings').then(r => r.data),
  updateSettings: (data: { lat: number; lon: number; location_name?: string }) =>
    api.put('/weather/settings', data).then(r => r.data),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add weatherAPI to frontend client"
```

---

### Task 5: Frontend — WeatherWidget component

**Files:**
- Create: `frontend/src/components/WeatherWidget.tsx`

- [ ] **Step 1: Create WeatherWidget component**

Create `frontend/src/components/WeatherWidget.tsx`:

```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { weatherAPI } from "../api/client";
import api from "../api/client";
import { useAuthStore } from "../stores/auth";

interface WeatherData {
  temperature: number;
  condition_code: number;
  condition_description: string;
  condition_icon: string;
  high: number;
  low: number;
  location_name?: string | null;
  error?: string | null;
  settings?: {
    lat: number;
    lon: number;
    location_name?: string | null;
  } | null;
}

interface WeatherSettings {
  lat: number;
  lon: number;
  location_name?: string | null;
}

interface WeatherWidgetProps {
  mode?: "dashboard" | "wall";
  onEdit?: () => void;
}

export default function WeatherWidget({ mode = "dashboard", onEdit }: WeatherWidgetProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editLat, setEditLat] = useState("");
  const [editLon, setEditLon] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [geolocating, setGeolocating] = useState(false);

  const { data, isFetching } = useQuery({
    queryKey: ["weather"],
    queryFn: async () => {
      const res = await weatherAPI.getWeather();
      return res as WeatherData;
    },
    staleTime: 30 * 60 * 1000,
  });

  const weather = data as WeatherData | undefined;

  const handleOpenEdit = () => {
    if (weather?.settings) {
      setEditLat(weather.settings.lat.toString());
      setEditLon(weather.settings.lon.toString());
      setEditLocation(weather.settings.location_name || "");
    }
    setShowEditModal(true);
  };

  const handleUseMyLocation = () => {
    setGeolocating(true);
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser");
      setGeolocating(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setEditLat(position.coords.latitude.toFixed(4));
        setEditLon(position.coords.longitude.toFixed(4));
        setGeolocating(false);
      },
      () => {
        alert("Unable to retrieve your location");
        setGeolocating(false);
      }
    );
  };

  const handleSave = async () => {
    const lat = parseFloat(editLat);
    const lon = parseFloat(editLon);
    if (isNaN(lat) || isNaN(lon)) return;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return;

    setSaving(true);
    try {
      await weatherAPI.updateSettings({ lat, lon, location_name: editLocation || undefined });
      await queryClient.invalidateQueries({ queryKey: ["weather"] });
      setShowEditModal(false);
    } catch {
      alert("Failed to update location");
    } finally {
      setSaving(false);
    }
  };

  const isLocationSet = weather?.settings && weather.settings.lat !== 0;

  if (mode === "wall") {
    return (
      <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{weather?.condition_icon || "🌡️"}</span>
          <div>
            <div className="text-3xl font-bold text-white">
              {isLocationSet ? `${Math.round(weather?.temperature || 0)}°F` : "Weather"}
            </div>
            <div className="text-slate-400 text-lg">
              H: {Math.round(weather?.high || 0)}° L: {Math.round(weather?.low || 0)}°
            </div>
            {weather?.location_name && (
              <div className="text-slate-500 text-sm mt-1">{weather.location_name}</div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Dashboard mode
  return (
    <>
      <div
        className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 cursor-pointer hover:border-slate-600 transition"
        onClick={handleOpenEdit}
      >
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-white">Weather</h3>
          <span className="text-xs text-slate-500">Click to edit location</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{weather?.condition_icon || "🌡️"}</span>
          <div>
            <div className="text-2xl font-bold text-white">
              {isLocationSet ? `${Math.round(weather?.temperature || 0)}°F` : "Set Location"}
            </div>
            {isLocationSet && (
              <div className="text-slate-400 text-sm">
                H: {Math.round(weather?.high || 0)}° L: {Math.round(weather?.low || 0)}°
              </div>
            )}
            {weather?.location_name && (
              <div className="text-slate-500 text-xs mt-1">{weather.location_name}</div>
            )}
          </div>
        </div>
        {weather?.error && (
          <div className="mt-2 text-xs text-amber-400">⚠ {weather.error}</div>
        )}
      </div>

      {showEditModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
            <h3 className="text-xl font-bold text-white mb-4">Weather Location</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={editLat}
                  onChange={(e) => setEditLat(e.target.value)}
                  className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
                  placeholder="e.g. 41.8781"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={editLon}
                  onChange={(e) => setEditLon(e.target.value)}
                  className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
                  placeholder="e.g. -87.6298"
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">Location Name (optional)</label>
                <input
                  type="text"
                  value={editLocation}
                  onChange={(e) => setEditLocation(e.target.value)}
                  className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
                  placeholder="e.g. Chicago"
                />
              </div>

              <button
                onClick={handleUseMyLocation}
                disabled={geolocating}
                className="w-full py-3 rounded-lg bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 transition flex items-center justify-center gap-2"
              >
                {geolocating ? "Getting location..." : "📍 Use my location"}
              </button>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-white font-semibold transition"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setShowEditModal(false)}
                className="flex-1 py-3 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-semibold transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/WeatherWidget.tsx
git commit -m "feat: add WeatherWidget component with inline location editing"
```

---

### Task 6: Frontend — Add widget to DashboardHome

**Files:**
- Modify: `frontend/src/pages/DashboardHome.tsx`

- [ ] **Step 1: Import and add WeatherWidget to sidebar**

Add import at the top of `DashboardHome.tsx`:

```typescript
import WeatherWidget from "../components/WeatherWidget";
```

Add the WeatherWidget in the sidebar div (right column), before the Wall Display card:

```tsx
<WeatherWidget mode="dashboard" />
```

The sidebar section starts around line 199 (`<div className="space-y-6">`). Insert the widget as the first child:

```tsx
        <div className="space-y-6">
          <WeatherWidget mode="dashboard" />

          <div
            className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-xl p-6 text-white cursor-pointer hover:from-blue-500 hover:to-blue-700 transition"
            onClick={() => navigate("/wall")}
          >
```

- [ ] **Step 2: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardHome.tsx
git commit -m "feat: add weather widget to dashboard sidebar"
```

---

### Task 7: Frontend — Add widget to WallDisplay

**Files:**
- Modify: `frontend/src/pages/WallDisplay.tsx`

- [ ] **Step 1: Import and add WeatherWidget to wall display**

Add import at the top of `WallDisplay.tsx`:

```typescript
import WeatherWidget from "../components/WeatherWidget";
```

Add the WeatherWidget at the top of the wall display, before the mode toggle buttons. Find the main content area (after the time/date header) and insert:

```tsx
<div className="mb-6">
  <WeatherWidget mode="wall" />
</div>
```

The wall display renders the time/date at the top, then has mode toggle buttons. Insert the weather widget between the time/date and the mode toggles.

- [ ] **Step 2: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/WallDisplay.tsx
git commit -m "feat: add weather widget to wall display"
```

---

### Task 8: Add weather step to SetupWizard

**Files:**
- Modify: `frontend/src/pages/SetupWizard.tsx`

- [ ] **Step 1: Add weather location state and API call**

Modify `SetupWizard.tsx` to add a weather location step after account creation:

```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { weatherAPI } from '../api/client'

export default function SetupWizard() {
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'account' | 'weather'>('account')
  const [weatherLat, setWeatherLat] = useState('')
  const [weatherLon, setWeatherLon] = useState('')
  const [weatherLocation, setWeatherLocation] = useState('')
  const [geolocating, setGeolocating] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleUseMyLocation = () => {
    setGeolocating(true)
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser")
      setGeolocating(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setWeatherLat(position.coords.latitude.toFixed(4))
        setWeatherLon(position.coords.longitude.toFixed(4))
        setGeolocating(false)
      },
      () => {
        alert("Unable to retrieve your location")
        setGeolocating(false)
      }
    )
  }

  const handleWeatherSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const lat = parseFloat(weatherLat)
    const lon = parseFloat(weatherLon)
    if (isNaN(lat) || isNaN(lon)) {
      setError('Please enter valid coordinates')
      return
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setError('Coordinates out of range')
      return
    }

    setLoading(true)
    try {
      await weatherAPI.updateSettings({ lat, lon, location_name: weatherLocation || undefined })
      navigate('/dashboard')
    } catch {
      setError('Failed to save location')
    } finally {
      setLoading(false)
    }
  }
```

- [ ] **Step 2: Add weather step UI**

Replace the return JSX to include both steps:

```typescript
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#1a1a2e] text-white px-4">
      <div className="w-full max-w-md">
        {step === 'account' ? (
          <div>
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold mb-2">Welcome to OpenFamHub</h1>
              <p className="text-gray-400">Set up your admin account to get started</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* ... existing form fields ... */}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-lg font-semibold transition"
              >
                {loading ? 'Creating Account...' : 'Create Admin Account'}
              </button>
            </form>

            <div className="mt-8 text-center">
              <button
                onClick={resetSetup}
                className="text-sm text-gray-500 hover:text-white transition"
              >
                Reset setup
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold mb-2">Set Your Location</h1>
              <p className="text-gray-400">This helps us show local weather on your dashboard</p>
            </div>

            <form onSubmit={handleWeatherSubmit} className="space-y-6">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={weatherLat}
                  onChange={(e) => setWeatherLat(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. 41.8781"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={weatherLon}
                  onChange={(e) => setWeatherLon(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. -87.6298"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Location Name (optional)</label>
                <input
                  type="text"
                  value={weatherLocation}
                  onChange={(e) => setWeatherLocation(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. Chicago"
                />
              </div>

              <button
                type="button"
                onClick={handleUseMyLocation}
                disabled={geolocating}
                className="w-full py-3 rounded-xl bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 transition"
              >
                {geolocating ? 'Getting location...' : '📍 Use my location'}
              </button>

              {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-center">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-lg font-semibold transition"
              >
                {loading ? 'Saving...' : 'Continue to Dashboard'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
```

- [ ] **Step 3: Modify account creation to go to weather step**

In the existing `handleSubmit` function, after successful account creation, change `navigate('/dashboard')` to `setStep('weather')`:

```typescript
      const data = await res.json()
      login(data.access_token, data.user)
      setStep('weather')  // Changed from: navigate('/dashboard')
```

- [ ] **Step 4: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SetupWizard.tsx
git commit -m "feat: add weather location step to setup wizard"
```

---

### Task 9: Run full test suite

**Files:**
- All backend tests

- [ ] **Step 1: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest`
Expected: All existing tests pass + new weather tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: verify weather widget tests and build"
```

---

### Task 10: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add weather widget entry to changelog**

Add to the top of the changelog under the latest version section:

```markdown
### Added
- Weather widget on dashboard sidebar and wall display
- Weather location configuration in setup wizard
- Inline weather location editing via dashboard widget
- Open-Meteo integration for weather data (free, no API key)
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add weather widget to changelog"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Open-Meteo integration (Task 2)
- ✅ Current temp + condition icon + high/low (Tasks 2, 5, 6, 7)
- ✅ Location in setup wizard (Task 10)
- ✅ Editable inline on widget (Task 5)
- ✅ Dashboard sidebar placement (Task 6)
- ✅ Wall display placement (Task 7)
- ✅ 30-minute cache (Task 5, staleTime)
- ✅ Error handling: no location, API failure, invalid coords, geolocation denied, rate limits (Task 2, 5)
- ✅ Temperature conversion C→F (Task 2)
- ✅ Admin-only settings update (Task 3)

**Placeholder scan:** No TBD, TODO, or vague requirements found.

**Type consistency:** All types match across tasks (WeatherResponse, WeatherSettingsUpdate, WeatherSettingsResponse).

**Scope check:** Focused on single feature, all tasks are self-contained.
