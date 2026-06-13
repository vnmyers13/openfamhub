import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { weatherAPI } from "../api/client";

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

interface WeatherWidgetProps {
  mode?: "dashboard" | "wall";
}

export default function WeatherWidget({ mode = "dashboard" }: WeatherWidgetProps) {
  const queryClient = useQueryClient();
  const [showEditModal, setShowEditModal] = useState(false);
  const [editLat, setEditLat] = useState("");
  const [editLon, setEditLon] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [saving, setSaving] = useState(false);
  const [geolocating, setGeolocating] = useState(false);

  const { data } = useQuery({
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
