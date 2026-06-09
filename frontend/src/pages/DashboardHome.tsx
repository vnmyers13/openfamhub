import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/auth";
import axios from "axios";
import {
  FaCalendarAlt,
  FaBullhorn,
  FaUsers,
  FaTv,
  FaClock,
  FaTasks,
  FaGift,
} from "react-icons/fa";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

interface Event {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_hex?: string;
}

interface Announcement {
  id: string;
  content: string;
  is_pinned: boolean;
  created_at?: string;
}

export default function DashboardHome() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const { data: events = [] } = useQuery({
    queryKey: ["events"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/events`);
      return res.data as Event[];
    },
  });

  const { data: announcements = [] } = useQuery({
    queryKey: ["announcements"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/announcements`);
      return res.data as Announcement[];
    },
  });

  const { data: choreStats } = useQuery({
    queryKey: ["chores", "stats"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/chores/stats`);
      return res.data;
    },
  });

  const { data: pointsBalance } = useQuery({
    queryKey: ["rewards", "points", "balance"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/rewards/points/balance`);
      return res.data;
    },
  });

  const { data: allowanceBalance } = useQuery({
    queryKey: ["rewards", "allowance", "balance"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/rewards/allowance/balance`);
      return res.data;
    },
  });

  const now = new Date();
  const todayStr = now.toDateString();

  const todayEvents = (events as Event[])
    .filter((e) => new Date(e.start_time).toDateString() === todayStr)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
    .slice(0, 5);

  const pinnedAnnouncements = announcements.filter((a) => a.is_pinned).slice(0, 3);
  const recentAnnouncements = announcements.filter((a) => !a.is_pinned).slice(0, 3);

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FaClock /> Today's Schedule
              </h2>
              <button
                onClick={() => navigate("/calendar")}
                className="text-blue-400 hover:text-blue-300 text-sm"
              >
                View Calendar →
              </button>
            </div>
            {todayEvents.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <p className="text-lg">No events today</p>
                <p className="text-sm mt-1">Enjoy your free time!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {todayEvents.map((event) => (
                  <div
                    key={event.id}
                    className="flex items-center gap-4 p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 transition"
                  >
                    <div
                      className="w-1.5 h-12 rounded-full flex-shrink-0"
                      style={{ backgroundColor: event.color_hex || "#3B82F6" }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-white font-medium truncate">{event.title}</p>
                      <p className="text-slate-400 text-sm">
                        {formatTime(event.start_time)} - {formatTime(event.end_time)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {pinnedAnnouncements.length > 0 && (
            <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-yellow-500/30">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                📌 Pinned Announcements
              </h2>
              <div className="space-y-3">
                {pinnedAnnouncements.map((announcement) => (
                  <div
                    key={announcement.id}
                    className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20"
                  >
                    <p className="text-white whitespace-pre-wrap">{announcement.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div
            className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-xl p-6 text-white cursor-pointer hover:from-blue-500 hover:to-blue-700 transition"
            onClick={() => navigate("/wall")}
          >
            <div className="flex items-center gap-3 mb-3">
              <FaTv className="text-2xl" />
              <h2 className="text-xl font-bold">Wall Display</h2>
            </div>
            <p className="text-blue-100 text-sm">
              Launch the TV wall display for your home
            </p>
          </div>

          {choreStats && (
            <div
              className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700 cursor-pointer hover:border-slate-600 transition"
              onClick={() => navigate("/chores")}
            >
              <div className="flex items-center gap-3 mb-3">
                <FaTasks className="text-xl text-orange-400" />
                <h3 className="text-lg font-semibold text-white">Chores</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-orange-500/10 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-orange-400">{choreStats.total_completed || 0}</p>
                  <p className="text-slate-400 text-xs mt-1">Completed</p>
                </div>
                <div className="bg-green-500/10 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-green-400">{choreStats.current_streak || 0}</p>
                  <p className="text-slate-400 text-xs mt-1">Day Streak</p>
                </div>
              </div>
            </div>
          )}

          {pointsBalance && allowanceBalance && (
            <div
              className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700 cursor-pointer hover:border-slate-600 transition"
              onClick={() => navigate("/rewards")}
            >
              <div className="flex items-center gap-3 mb-3">
                <FaGift className="text-xl text-pink-400" />
                <h3 className="text-lg font-semibold text-white">Rewards</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-pink-500/10 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-pink-400">{pointsBalance.balance || 0}</p>
                  <p className="text-slate-400 text-xs mt-1">Points</p>
                </div>
                <div className="bg-blue-500/10 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-blue-400">{allowanceBalance.balance || 0}</p>
                  <p className="text-slate-400 text-xs mt-1">Allowance</p>
                </div>
              </div>
            </div>
          )}

          {user?.role === "admin" && (
            <div
              className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700 cursor-pointer hover:border-slate-600 transition"
              onClick={() => navigate("/dashboard/manage-users")}
            >
              <div className="flex items-center gap-3 mb-2">
                <FaUsers />
                <h3 className="text-lg font-semibold text-white">Manage Users</h3>
              </div>
              <p className="text-slate-400 text-sm">
                Add, edit, or deactivate family members
              </p>
            </div>
          )}

          {recentAnnouncements.length > 0 && (
            <div
              className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700 cursor-pointer hover:border-slate-600 transition"
              onClick={() => navigate("/dashboard/announcements")}
            >
              <div className="flex items-center gap-3 mb-2">
                <FaBullhorn />
                <h3 className="text-lg font-semibold text-white">Announcements</h3>
              </div>
              <div className="space-y-2 mt-3">
                {recentAnnouncements.map((announcement) => (
                  <div key={announcement.id} className="text-sm">
                    <p className="text-slate-300 line-clamp-2">{announcement.content}</p>
                    <p className="text-slate-500 text-xs mt-1">{formatDate(announcement.created_at || "")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <div
            className="text-center p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 cursor-pointer hover:bg-blue-500/20 transition"
            onClick={() => navigate("/calendar")}
          >
            <FaCalendarAlt className="text-3xl text-blue-400 mx-auto mb-2" />
            <p className="text-white font-medium">Calendar</p>
            <p className="text-slate-400 text-sm mt-1">
              {events.length} events
            </p>
          </div>
          <div
            className="text-center p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20 cursor-pointer hover:bg-yellow-500/20 transition"
            onClick={() => navigate("/dashboard/announcements")}
          >
            <FaBullhorn className="text-3xl text-yellow-400 mx-auto mb-2" />
            <p className="text-white font-medium">Announcements</p>
            <p className="text-slate-400 text-sm mt-1">
              {announcements.length} total
            </p>
          </div>
          {choreStats && (
            <div
              className="text-center p-4 rounded-lg bg-orange-500/10 border border-orange-500/20 cursor-pointer hover:bg-orange-500/20 transition"
              onClick={() => navigate("/chores")}
            >
              <FaTasks className="text-3xl text-orange-400 mx-auto mb-2" />
              <p className="text-white font-medium">Chores</p>
              <p className="text-slate-400 text-sm mt-1">
                {choreStats.total_completed || 0} done
              </p>
            </div>
          )}
          {pointsBalance && allowanceBalance && (
            <div
              className="text-center p-4 rounded-lg bg-pink-500/10 border border-pink-500/20 cursor-pointer hover:bg-pink-500/20 transition"
              onClick={() => navigate("/rewards")}
            >
              <FaGift className="text-3xl text-pink-400 mx-auto mb-2" />
              <p className="text-white font-medium">Rewards</p>
              <p className="text-slate-400 text-sm mt-1">
                {pointsBalance.balance || 0} pts
              </p>
            </div>
          )}
          {user?.role === "admin" && (
            <div
              className="text-center p-4 rounded-lg bg-green-500/10 border border-green-500/20 cursor-pointer hover:bg-green-500/20 transition"
              onClick={() => navigate("/dashboard/manage-users")}
            >
              <FaUsers className="text-3xl text-green-400 mx-auto mb-2" />
              <p className="text-white font-medium">Users</p>
              <p className="text-slate-400 text-sm mt-1">Manage access</p>
            </div>
          )}
          <div
            className="text-center p-4 rounded-lg bg-purple-500/10 border border-purple-500/20 cursor-pointer hover:bg-purple-500/20 transition"
            onClick={() => navigate("/wall")}
          >
            <FaTv className="text-3xl text-purple-400 mx-auto mb-2" />
            <p className="text-white font-medium">Wall Display</p>
            <p className="text-slate-400 text-sm mt-1">TV mode</p>
          </div>
        </div>
      </div>
    </div>
  );
}
