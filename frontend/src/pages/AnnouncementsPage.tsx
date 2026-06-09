import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

interface Announcement {
  id: string;
  author_id: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export default function AnnouncementsPage() {
  const [content, setContent] = useState("");
  const [showForm, setShowForm] = useState(false);
  const queryClient = useQueryClient();

  const { data: announcements = [], isLoading } = useQuery({
    queryKey: ["announcements"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/announcements`);
      return res.data as Announcement[];
    },
  });

  const createAnnouncement = useMutation({
    mutationFn: async (content: string) => {
      const res = await axios.post(`${API_BASE}/announcements`, { content });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
      setContent("");
      setShowForm(false);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (content.trim()) {
      createAnnouncement.mutate(content.trim());
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Announcements</h2>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          + New Announcement
        </button>
      </div>

      {showForm && (
        <div className="mb-6 bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700">
          <form onSubmit={handleSubmit} className="space-y-3">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={3}
              placeholder="Write an announcement..."
              autoFocus
            />
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setContent("");
                }}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!content.trim() || createAnnouncement.isPending}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                {createAnnouncement.isPending ? "Posting..." : "Post"}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="text-center text-slate-400 py-8">Loading...</div>
      ) : announcements.length === 0 ? (
        <div className="text-center text-slate-400 py-8 bg-slate-800/30 rounded-xl">
          No announcements yet
        </div>
      ) : (
        <div className="space-y-4">
          {announcements.map((announcement) => (
            <div
              key={announcement.id}
              className={`bg-slate-800/50 backdrop-blur rounded-xl p-4 border transition-colors ${
                announcement.is_pinned
                  ? "border-yellow-500/30 bg-yellow-500/5"
                  : "border-slate-700"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {announcement.is_pinned && (
                      <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-300 text-xs rounded-full">
                        Pinned
                      </span>
                    )}
                    <span className="text-slate-500 text-sm">
                      {formatDate(announcement.created_at)}
                    </span>
                  </div>
                  <p className="text-white whitespace-pre-wrap">{announcement.content}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
