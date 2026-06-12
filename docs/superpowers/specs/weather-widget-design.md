# Weather Widget - Design Spec

## Overview

Add a weather widget to the dashboard sidebar and wall display, showing current temperature, condition icon, and daily high/low. Location is configured during setup and editable inline on the widget.

## Architecture

### Backend Changes

**`backend/app/models/event.py`** — Extend User model with weather columns:
- `weather_lat` (Float, nullable)
- `weather_lon` (Float, nullable)
- `weather_location_name` (Text, nullable)

**`backend/app/routers/weather.py`** — New router:
- `GET /api/weather` — Fetch current weather from Open-Meteo
- `GET /api/weather/settings` — Return stored weather location
- `PUT /api/weather/settings` — Update weather location (admin only)

**`backend/app/services/weather.py`** — New service module:
- `fetch_weather(lat, lon)` — Calls Open-Meteo API, parses response
- `WMO_CODE_DESCRIPTIONS` — Mapping of WMO weather codes to icons/descriptions

**`backend/app/main.py`** — Register weather router at `/api/weather`

### Frontend Changes

**`frontend/src/api/client.ts`** — Add `weatherAPI` object:
- `getWeather()` → GET /api/weather
- `getSettings()` → GET /api/weather/settings
- `updateSettings(data)` → PUT /api/weather/settings

**`frontend/src/components/WeatherWidget.tsx`** — New shared component:
- Dashboard mode: clickable, opens edit modal
- Wall mode: larger text, no click handler

**`frontend/src/pages/SetupWizard.tsx`** — Add weather location step:
- Latitude, Longitude fields
- "Use my location" button (browser geolocation)
- Proceeds to account creation after completion

**`frontend/src/pages/DashboardHome.tsx`** — Add WeatherWidget to sidebar (top-right)

**`frontend/src/pages/WallDisplay.tsx`** — Add WeatherWidget at top of display

## Data Flow

### Weather Data Fetch (Dashboard)
1. DashboardHome loads → `useQuery` calls `weatherAPI.getWeather()`
2. Backend `GET /api/weather` → calls `weather_service.fetch_weather()` with stored lat/lon
3. If no location set → returns `{"error": "location_not_set", "settings": {...}}`
4. Response cached by react-query for 30 minutes (`staleTime: 30 * 60 * 1000`)

### Weather Settings Update (Inline Edit)
1. User clicks weather widget → modal appears with lat/lon fields + "Use my location" button
2. "Use my location" → browser geolocation API → fills lat/lon
3. User saves → `weatherAPI.updateSettings({ lat, lon, location_name })`
4. Backend stores in User model, returns updated settings
5. Dashboard refetches weather data

### Wall Display
- Same WeatherWidget component, larger font, no click-to-edit
- Fetches weather in the existing `fetchData` interval (60s)

## Open-Meteo API Integration

**Endpoint:**
```
https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min&timezone=auto
```

**Response fields used:**
- `current.temperature_2m` — Current temperature in Celsius
- `current.weather_code` — WMO weather condition code
- `daily.temperature_2m_max[0]` — Today's high
- `daily.temperature_2m_min[0]` — Today's low

**Temperature conversion:** Backend converts Celsius to Fahrenheit for US users.

## Error Handling

- **No location set:** Widget shows "Set location" prompt, clickable to open settings modal
- **API failure:** Shows last known data with "Refresh failed" banner, retries after 5 min
- **Invalid lat/lon:** Rejects values outside (-90, 90) for lat and (-180, 180) for lon
- **Browser geolocation denied:** Falls back to manual input in the modal
- **Open-Meteo rate limits:** Backend caches response in memory for 10 min to avoid excessive calls

## Testing

- **Backend:** Test weather service mock, weather router endpoints (get weather, get/update settings, validation)
- **Frontend:** No unit tests (widget is UI-only), visual verification on dashboard + wall

## UI Details

### Widget (Dashboard)
- Card style: `bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700`
- Shows: icon + current temp (large) + "H: X° L: X°" + location name
- Clickable → opens edit modal

### Widget (Wall Display)
- Same design, larger text, no click handler
- Positioned at top of wall display above events

### Edit Modal
- Simple form: Latitude, Longitude, Location name (optional)
- "Use my location" button (browser geolocation)
- "Save" / "Cancel" buttons

## Files Modified/Created

### New Files
- `backend/app/routers/weather.py`
- `backend/app/services/weather.py`
- `frontend/src/components/WeatherWidget.tsx`

### Modified Files
- `backend/app/models/event.py` (User model)
- `backend/app/main.py` (router registration)
- `frontend/src/api/client.ts` (weatherAPI)
- `frontend/src/pages/SetupWizard.tsx` (weather step)
- `frontend/src/pages/DashboardHome.tsx` (widget placement)
- `frontend/src/pages/WallDisplay.tsx` (widget placement)
