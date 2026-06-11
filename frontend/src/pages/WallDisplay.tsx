import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";

interface WallEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_hex?: string;
}

interface WallAnnouncement {
  id: string;
  content: string;
  is_pinned: boolean;
  created_at?: string;
}

type DisplayMode = "grid" | "cycling";

export default function WallDisplay() {
  const [events, setEvents] = useState<WallEvent[]>([]);
  const [announcements, setAnnouncements] = useState<WallAnnouncement[]>([]);
  const [mode, setMode] = useState<DisplayMode>("grid");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const timerRef = useRef<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [eventsRes, announcementsRes] = await Promise.all([
        api.get('/events'),
        api.get('/announcements'),
      ]);
      setEvents(eventsRes.data as WallEvent[]);
      setAnnouncements(announcementsRes.data as WallAnnouncement[]);
    } catch (err) {
      console.error("Failed to fetch wall data:", err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const now = new Date();
  const today = now.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const time = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });

  const todayEvents = events
    .filter((e) => new Date(e.start_time).toDateString() === now.toDateString())
    .sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );

  const pinnedAnnouncements = announcements
    .filter((a) => a.is_pinned)
    .slice(0, 5);

  const recentAnnouncements = announcements
    .filter((a) => !a.is_pinned)
    .slice(0, 10);

  const cyclingPanels = [
    {
      type: "events" as const,
      title: "Today's Schedule",
      data: todayEvents,
      color: "blue",
    },
    ...(pinnedAnnouncements.length > 0
      ? [
          {
            type: "pinned" as const,
            title: "Pinned Announcements",
            data: pinnedAnnouncements,
            color: "yellow",
          },
        ]
      : []),
    ...(recentAnnouncements.length > 0
      ? [
          {
            type: "recent" as const,
            title: "Recent Announcements",
            data: recentAnnouncements,
            color: "green",
          },
        ]
      : []),
  ];

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const startCycling = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % cyclingPanels.length);
    }, 8000);
  }, [cyclingPanels.length]);

  const stopCycling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (mode === "cycling" && cyclingPanels.length > 1 && !isHovered) {
      startCycling();
    } else {
      stopCycling();
    }
    return stopCycling;
  }, [mode, cyclingPanels.length, isHovered, startCycling, stopCycling]);

  const renderEventCard = (event: WallEvent) => (
    <div
      key={event.id}
      className="flex items-center gap-4 p-4 rounded-xl bg-white/5 hover:bg-white/10 transition"
    >
      <div
        className="w-2 h-16 rounded-full flex-shrink-0"
        style={{ backgroundColor: event.color_hex || "#3B82F6" }}
      />
      <div className="flex-1 min-w-0">
        <p className="text-2xl font-semibold text-white truncate">
          {event.title}
        </p>
        <p className="text-slate-400 text-lg mt-1">
          {formatTime(event.start_time)} - {formatTime(event.end_time)}
        </p>
      </div>
    </div>
  );

  const renderAnnouncementCard = (
    announcement: WallAnnouncement
  ) => (
    <div
      key={announcement.id}
      className={`p-5 rounded-xl ${
        announcement.is_pinned
          ? "bg-yellow-500/10 border-2 border-yellow-500/30"
          : "bg-white/5"
      }`}
    >
      <p className="text-xl text-white whitespace-pre-wrap">
        {announcement.content}
      </p>
      {announcement.created_at && (
        <p className="text-slate-500 text-sm mt-2">
          {formatDate(announcement.created_at)}
        </p>
      )}
    </div>
  );

  const renderGridMode = () => (
    <div className="flex-1 p-8 grid grid-cols-3 gap-8">
      <div className="col-span-2 bg-[#16213e] rounded-2xl p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4 text-white">
          Today's Schedule
        </h2>
        {todayEvents.length === 0 ? (
          <p className="text-slate-400 text-xl">No events today</p>
        ) : (
          <div className="space-y-3">{todayEvents.map(renderEventCard)}</div>
        )}
      </div>
      <div className="bg-[#16213e] rounded-2xl p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4 text-white">Announcements</h2>
        {announcements.length === 0 ? (
          <p className="text-slate-400 text-xl">No announcements</p>
        ) : (
          <div className="space-y-4">
            {announcements.map(renderAnnouncementCard)}
          </div>
        )}
      </div>
    </div>
  );

  const renderCyclingMode = () => {
    if (cyclingPanels.length === 0) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-slate-400 text-2xl">Nothing to display</p>
        </div>
      );
    }

    const panel = cyclingPanels[currentIndex];

    return (
      <div
        className="flex-1 p-8 flex flex-col"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-white">{panel.title}</h2>
          <div className="flex gap-2">
            {cyclingPanels.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentIndex(i)}
                className={`w-3 h-3 rounded-full transition-all ${
                  i === currentIndex ? "bg-white scale-125" : "bg-white/30"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {panel.type === "events" && panel.data.length === 0 ? (
            <p className="text-slate-400 text-xl">No events today</p>
          ) : panel.type === "events" ? (
            <div className="space-y-4">{panel.data.map(renderEventCard)}</div>
          ) : panel.type === "pinned" ? (
            <div className="space-y-4">
              {panel.data.map(renderAnnouncementCard)}
            </div>
          ) : (
            <div className="space-y-4">
              {panel.data.map(renderAnnouncementCard)}
            </div>
          )}
        </div>

        {!isHovered && panel.data.length > 1 && (
          <div className="text-center mt-4">
            <p className="text-slate-500 text-sm">
              Auto-advancing in{" "}
              {Math.ceil((8000 - (Date.now() % 8000)) / 1000)}s...
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className="h-screen w-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <header className="bg-[#16213e]/80 backdrop-blur px-8 py-4 flex justify-between items-center">
        <h1 className="text-3xl font-bold text-white">OpenFamHub</h1>
        <div className="text-right">
          <p className="text-2xl text-white">{today}</p>
          <p className="text-xl text-slate-400">{time}</p>
        </div>
      </header>

      <div className="flex-1 flex flex-col">
        {mode === "grid" ? renderGridMode() : renderCyclingMode()}

        <div
          className={`px-8 py-3 bg-[#16213e]/60 backdrop-blur flex items-center justify-between transition-opacity duration-300 ${
            isHovered ? "opacity-100" : "opacity-0 hover:opacity-100"
          }`}
        >
          <div className="flex gap-3">
            <button
              onClick={() => setMode("grid")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === "grid"
                  ? "bg-blue-600 text-white"
                  : "bg-white/10 text-slate-300 hover:bg-white/20"
              }`}
            >
              Grid View
            </button>
            <button
              onClick={() => setMode("cycling")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === "cycling"
                  ? "bg-blue-600 text-white"
                  : "bg-white/10 text-slate-300 hover:bg-white/20"
              }`}
            >
              Cycling Panels
            </button>
          </div>
          <button
            onClick={() => window.location.href = "/"}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-slate-300 rounded-lg text-sm transition"
          >
            Exit Display
          </button>
        </div>
      </div>
    </div>
  );
}
