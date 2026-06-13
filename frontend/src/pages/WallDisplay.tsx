import { useState, useEffect, useCallback, useRef } from 'react';
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

type DisplayMode = 'grid' | 'cycling';

export default function WallDisplay() {
  const [mode, setMode] = useState<DisplayMode>('grid');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const timerRef = useRef<number | null>(null);

  const { data: events } = useQuery({
    queryKey: ['wall-events'],
    queryFn: async () => {
      const res = await api.get('/calendar/events');
      return res.data as WallEvent[];
    },
    refetchInterval: 60000,
  });

  const wallEvents = events as WallEvent[] | undefined;

  const cyclingPanels = [
    { type: 'calendar' as const, title: "Today's Schedule" },
    { type: 'chores' as const, title: 'Family Chores' },
    { type: 'announcements' as const, title: 'Announcements' },
    { type: 'weather' as const, title: 'Weather' },
    { type: 'menu' as const, title: "Today's Menu" },
  ];

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
    if (mode === 'cycling' && cyclingPanels.length > 1 && !isHovered) {
      startCycling();
    } else {
      stopCycling();
    }
    return stopCycling;
  }, [mode, cyclingPanels.length, isHovered, startCycling, stopCycling]);

  useEffect(() => {
    const timer = setTimeout(() => {
      window.location.href = '/';
    }, 30 * 60 * 1000);
    return () => clearTimeout(timer);
  }, []);

  const renderGridMode = () => (
    <div className="h-full flex flex-col">
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

  const renderCyclingMode = () => {
    const panel = cyclingPanels[currentIndex];

    const renderPanelContent = () => {
      switch (panel.type) {
        case 'calendar':
          return <CalendarWallView events={wallEvents || []} />;
        case 'chores':
          return <ChoresWallPanel />;
        case 'announcements':
          return <AnnouncementsWallPanel />;
        case 'weather':
          return <WeatherWidget mode="wall" />;
        case 'menu':
          return <MenuWallPanel />;
        default:
          return null;
      }
    };

    return (
      <div className="h-full flex flex-col p-2">
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between mb-2 px-4">
            <h2 className="text-2xl font-bold text-white">{panel.title}</h2>
            <div className="flex gap-2">
              {cyclingPanels.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentIndex(i)}
                  className={`w-3 h-3 rounded-full transition-all ${
                    i === currentIndex ? 'bg-white scale-125' : 'bg-white/30'
                  }`}
                />
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-hidden rounded-xl bg-white/5 border border-white/10">
            {renderPanelContent()}
          </div>
        </div>

        {!isHovered && cyclingPanels.length > 1 && (
          <div className="text-center mt-2 px-4">
            <p className="text-slate-500 text-sm">
              Auto-advancing in{' '}
              {Math.ceil((8000 - (Date.now() % 8000)) / 1000)}s...
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className="h-screen w-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden flex flex-col"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex-1 flex flex-col overflow-hidden">
        {mode === 'grid' ? renderGridMode() : renderCyclingMode()}

        <div
          className={`px-4 py-3 bg-slate-900/80 backdrop-blur flex items-center justify-between transition-opacity duration-300 ${
            isHovered ? 'opacity-100' : 'opacity-0 hover:opacity-100'
          }`}
        >
          <div className="flex gap-3">
            <button
              onClick={() => setMode('grid')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === 'grid'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white/10 text-slate-300 hover:bg-white/20'
              }`}
            >
              Grid View
            </button>
            <button
              onClick={() => setMode('cycling')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                mode === 'cycling'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white/10 text-slate-300 hover:bg-white/20'
              }`}
            >
              Cycling Panels
            </button>
          </div>
          <button
            onClick={() => window.location.href = '/'}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-slate-300 rounded-lg text-sm transition"
          >
            Exit Display
          </button>
        </div>
      </div>
    </div>
  );
}
