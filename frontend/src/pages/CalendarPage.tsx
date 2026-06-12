import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar as BigCalendar, dateFnsLocalizer, Views } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { enUS } from "date-fns/locale";
import api from "../api/client";
import "react-big-calendar/lib/css/react-big-calendar.css";

const locales = {
  "en-US": enUS,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  location?: string;
  start_time: string;
  end_time: string;
  all_day: boolean;
  color_hex?: string;
  source_id?: string;
}

interface CalendarSource {
  id: string;
  name: string;
  url: string;
  color_hex: string;
  sync_interval_hours: number;
  last_synced_at?: string;
  is_active: boolean;
}

interface CreateSourcePayload {
  name: string;
  url: string;
  color_hex: string;
  sync_interval_hours: number;
}

interface SyncResult {
  events_imported: number;
  events_deleted: number;
  status: string;
  errors: string;
}

export default function CalendarPage() {
  const navigate = useNavigate();
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [editingSource, setEditingSource] = useState<CalendarSource | null>(null);
  const [sourceForm, setSourceForm] = useState<CreateSourcePayload>({
    name: "",
    url: "",
    color_hex: "#3B82F6",
    sync_interval_hours: 24,
  });
  const [syncingSource, setSyncingSource] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [sourceError, setSourceError] = useState("");
  const queryClient = useQueryClient();

  const { data: events = [] } = useQuery({
    queryKey: ["events"],
    queryFn: async () => {
      const res = await api.get(`/calendar/events`);
      return res.data as CalendarEvent[];
    },
  });

  const { data: sources = [] } = useQuery({
    queryKey: ["calendar-sources"],
    queryFn: async () => {
      const res = await api.get(`/calendar/sources`);
      return res.data as CalendarSource[];
    },
  });

  const createSourceMutation = useMutation({
    mutationFn: async (data: CreateSourcePayload) => {
      const res = await api.post(`/calendar/sources`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-sources"] });
      setShowSourceModal(false);
      setSourceForm({ name: "", url: "", color_hex: "#3B82F6", sync_interval_hours: 24 });
      setSourceError("");
    },
    onError: (err: any) => {
      setSourceError(err.response?.data?.detail || "Failed to add calendar source");
    },
  });

  const updateSourceMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: CreateSourcePayload }) => {
      const res = await api.patch(`/calendar/sources/${id}`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-sources"] });
      setShowSourceModal(false);
      setEditingSource(null);
      setSourceError("");
    },
    onError: (err: any) => {
      setSourceError(err.response?.data?.detail || "Failed to update calendar source");
    },
  });

  const deleteSourceMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/calendar/sources/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-sources"] });
    },
  });

  const syncSourceMutation = useMutation({
    mutationFn: async (sourceId: string) => {
      const res = await api.post(`/calendar/sources/${sourceId}/sync`);
      return res.data as SyncResult;
    },
    onSuccess: (data) => {
      setSyncResult(data);
      queryClient.invalidateQueries({ queryKey: ["calendar-sources"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setTimeout(() => setSyncResult(null), 5000);
    },
  });

  const calendarEvents = useMemo(() => {
    return events.map((event: CalendarEvent) => {
      const start = event.all_day
        ? new Date(event.start_time.split("T")[0])
        : new Date(event.start_time);
      const end = event.all_day
        ? new Date(event.end_time.split("T")[0])
        : new Date(event.end_time);

      return {
        id: event.id,
        title: event.title,
        start,
        end,
        allDay: event.all_day,
        resource: event,
        style: {
          backgroundColor: event.color_hex || "#3B82F6",
          borderColor: event.color_hex || "#3B82F6",
        },
      };
    });
  }, [events]);

  const eventTitleAccessor = (event: any) => {
    return (
      <div>
        <div style={{ fontWeight: "bold" }}>{event.title}</div>
        {event.resource?.location && (
          <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>{event.resource.location}</div>
        )}
      </div>
    );
  };

  const handleSync = (sourceId: string) => {
    setSyncingSource(sourceId);
    syncSourceMutation.mutate(sourceId);
    setSyncingSource(null);
  };

  const openEditModal = (source: CalendarSource) => {
    setEditingSource(source);
    setSourceForm({
      name: source.name,
      url: source.url,
      color_hex: source.color_hex,
      sync_interval_hours: source.sync_interval_hours,
    });
    setShowSourceModal(true);
  };

  const openAddModal = () => {
    setEditingSource(null);
    setSourceForm({ name: "", url: "", color_hex: "#3B82F6", sync_interval_hours: 24 });
    setShowSourceModal(true);
  };

  const handleSubmitSource = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingSource) {
      updateSourceMutation.mutate({ id: editingSource.id, data: sourceForm });
    } else {
      createSourceMutation.mutate(sourceForm);
    }
  };

  const formatSyncDate = (dateStr?: string) => {
    if (!dateStr) return "Never";
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/dashboard")}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <h1 className="text-3xl font-bold text-white">Family Calendar</h1>
          </div>
          <div className="flex gap-3">
            <button
              onClick={openAddModal}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Calendar Source
            </button>
          </div>
        </div>

        {syncResult && (
          <div className="mb-4 p-4 bg-green-900/50 border border-green-700 rounded-lg">
            <p className="text-green-300">
              Sync complete: {syncResult.events_imported} events imported, {syncResult.events_deleted}{" "}
              events deleted
            </p>
            {syncResult.errors && syncResult.errors !== "[]" && (
              <p className="text-red-300 mt-1">Errors: {syncResult.errors}</p>
            )}
          </div>
        )}

        <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700">
          <BigCalendar
            localizer={localizer}
            events={calendarEvents}
            startAccessor="start"
            endAccessor="end"
            style={{ height: 600 }}
            eventPropGetter={(event) => ({
              className: "custom-event",
              style: event.style,
            })}
            messages={{
              next: "Next >",
              previous: "< Prev",
              today: "Today",
              month: "Month",
              week: "Week",
              day: "Day",
              agenda: "Agenda",
              date: "Date",
              time: "Time",
              event: "Event",
              noEventsInRange: "No events",
              allDay: "All Day",
            }}
            views={["month", "week", "day", "agenda"]}
            defaultView={Views.MONTH}
            min={new Date(2026, 0, 1, 8, 0)}
            max={new Date(2026, 11, 31, 20, 0)}
            popup
            onView={() => {}}
            components={{
              event: eventTitleAccessor as any,
            }}
          />
        </div>

        {sources.length > 0 && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold text-white mb-4">Calendar Sources</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sources.map((source) => (
                <div
                  key={source.id}
                  className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: source.color_hex }}
                    />
                    <h3 className="text-white font-medium">{source.name}</h3>
                  </div>
                  <p className="text-slate-400 text-sm mb-2">
                    Sync every {source.sync_interval_hours}h
                  </p>
                  <p className="text-slate-500 text-xs mb-3">
                    Last synced: {formatSyncDate(source.last_synced_at)}
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSync(source.id)}
                      disabled={syncingSource === source.id}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm transition-colors"
                    >
                      {syncingSource === source.id ? "Syncing..." : "Sync Now"}
                    </button>
                    <button
                      onClick={() => openEditModal(source)}
                      className="px-3 py-1.5 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete "${source.name}"?`)) {
                          deleteSourceMutation.mutate(source.id);
                        }
                      }}
                      className="px-3 py-1.5 bg-red-600/50 hover:bg-red-600 text-white rounded-lg text-sm transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {showSourceModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
              <h2 className="text-xl font-bold text-white mb-4">
                {editingSource ? "Edit Calendar Source" : "Add Calendar Source"}
              </h2>
              <form onSubmit={handleSubmitSource} className="space-y-4">
                {sourceError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                    {sourceError}
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Name</label>
                  <input
                    type="text"
                    value={sourceForm.name}
                    onChange={(e) => setSourceForm({ ...sourceForm, name: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., School Calendar"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">
                    ICS URL
                  </label>
                  <input
                    type="text"
                    value={sourceForm.url}
                    onChange={(e) => setSourceForm({ ...sourceForm, url: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://example.com/calendar.ics"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Color
                    </label>
                    <input
                      type="color"
                      value={sourceForm.color_hex}
                      onChange={(e) => setSourceForm({ ...sourceForm, color_hex: e.target.value })}
                      className="w-full h-10 rounded-lg cursor-pointer"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Sync Interval (hours)
                    </label>
                    <input
                      type="number"
                      value={sourceForm.sync_interval_hours}
                      onChange={(e) =>
                        setSourceForm({
                          ...sourceForm,
                          sync_interval_hours: parseInt(e.target.value) || 24,
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      min={1}
                      max={168}
                    />
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <button
                    type="button"
                    onClick={() => setShowSourceModal(false)}
                    className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createSourceMutation.isPending || updateSourceMutation.isPending}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
                  >
                    {editingSource ? "Update" : "Add Source"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
