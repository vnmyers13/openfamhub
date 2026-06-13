import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

interface Announcement {
  id: string;
  title: string;
  message: string;
  created_at: string;
}

export default function AnnouncementsWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-announcements'],
    queryFn: async () => {
      const res = await api.get('/announcements');
      return res.data as Announcement[];
    },
    refetchInterval: 120000,
  });

  const announcements = data as Announcement[] | undefined;

  const recentAnnouncements = announcements
    ?.filter((a) => {
      const daysSince = (Date.now() - new Date(a.created_at).getTime()) / (1000 * 60 * 60 * 24);
      return daysSince <= 7;
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading announcements...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load announcements</div>
      </div>
    );
  }

  if (!recentAnnouncements || recentAnnouncements.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No announcements</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-3">
      {recentAnnouncements.map((announcement) => (
        <div key={announcement.id} className="bg-white/5 rounded-xl p-3 border border-white/10">
          <div className="text-lg font-semibold text-white">{announcement.title}</div>
          <div className="text-slate-400 text-lg mt-1 line-clamp-3">{announcement.message}</div>
          <div className="text-slate-500 text-sm mt-1">
            {new Date(announcement.created_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
