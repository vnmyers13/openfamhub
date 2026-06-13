import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';
import WeatherWidget from '../components/WeatherWidget';
import MenuWallPanel from '../components/MenuWallPanel';
import CalendarWallView from '../components/CalendarWallView';
import ChoresWallPanel from '../components/ChoresWallPanel';
import AnnouncementsWallPanel from '../components/AnnouncementsWallPanel';

interface WallEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_hex?: string;
  is_all_day?: boolean;
  description?: string;
  location?: string;
}

export default function WallDisplay() {
  const { data: events } = useQuery({
    queryKey: ['wall-events'],
    queryFn: async () => {
      const res = await api.get('/calendar/events');
      return res.data as WallEvent[];
    },
    refetchInterval: 60000,
  });

  const wallEvents = events as WallEvent[] | undefined;

  useEffect(() => {
    const timer = setTimeout(() => {
      window.location.href = '/';
    }, 30 * 60 * 1000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="h-screen w-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
      <div className="h-[25vh] grid grid-cols-3 gap-2 p-2">
        <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
          <AnnouncementsWallPanel />
        </div>
        <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
          <WeatherWidget mode="wall" />
        </div>
        <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
          <MenuWallPanel />
        </div>
      </div>

      <div className="h-[75vh] grid grid-cols-10 gap-2 p-2">
        <div className="col-span-7 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
          <CalendarWallView events={wallEvents || []} />
        </div>
        <div className="col-span-3 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
          <ChoresWallPanel />
        </div>
      </div>
    </div>
  );
}
