import { useState } from 'react';

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

type CalendarView = 'agenda' | 'daily' | 'weekly' | 'monthly';

interface CalendarWallViewProps {
  events: WallEvent[];
}

const formatTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
};

export default function CalendarWallView({ events }: CalendarWallViewProps) {
  const [view, setView] = useState<CalendarView>('daily');

  const now = new Date();
  const today = now.toDateString();
  const todayStr = now.toISOString().split('T')[0];

  const todayEvents = events
    .filter((e) => new Date(e.start_time).toDateString() === today)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  // Weekly: get all events this week
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  const weeklyEvents = events.filter((e) => {
    const d = new Date(e.start_time);
    return d >= weekStart && d <= weekEnd;
  });

  // Monthly: get all events this month
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const monthlyEvents = events.filter((e) => {
    const d = new Date(e.start_time);
    return d >= monthStart && d <= monthEnd;
  });

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const viewButtons: { key: CalendarView; label: string }[] = [
    { key: 'agenda', label: 'Agenda' },
    { key: 'daily', label: 'Daily' },
    { key: 'weekly', label: 'Weekly' },
    { key: 'monthly', label: 'Monthly' },
  ];

  const renderAgenda = () => {
    if (todayEvents.length === 0) {
      return <p className="text-slate-400 text-xl text-center mt-8">No events today</p>;
    }
    return (
      <div className="space-y-3">
        {todayEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-4 p-3 rounded-xl bg-white/5">
            <div className="w-2 h-12 rounded-full flex-shrink-0" style={{ backgroundColor: event.color_hex || '#3B82F6' }} />
            <div className="flex-1 min-w-0">
              <p className="text-xl font-semibold text-white truncate">{event.title}</p>
              <p className="text-slate-400 text-lg">{formatTime(event.start_time)} - {formatTime(event.end_time)}</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderDaily = () => {
    if (todayEvents.length === 0) {
      return <p className="text-slate-400 text-xl text-center mt-8">No events today</p>;
    }
    return (
      <div className="space-y-2">
        {todayEvents.map((event) => (
          <div key={event.id} className="flex gap-4 p-3 rounded-xl bg-white/5">
            <div className="text-lg text-slate-400 w-24 flex-shrink-0 text-right">
              {formatTime(event.start_time)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xl font-semibold text-white truncate">{event.title}</p>
              <p className="text-slate-400 text-lg">{formatTime(event.end_time)}</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderWeekly = () => {
    const weekDays = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + i);
      const dayStr = d.toISOString().split('T')[0];
      const dayEvents = weeklyEvents.filter((e) => new Date(e.start_time).toISOString().split('T')[0] === dayStr);
      weekDays.push({ date: d, label: days[d.getDay()], dayStr, events: dayEvents });
    }

    return (
      <div className="grid grid-cols-7 gap-2 h-full">
        {weekDays.map((day) => (
          <div key={day.dayStr} className={`rounded-xl p-2 ${day.dayStr === todayStr ? 'bg-blue-600/20 border border-blue-500/30' : 'bg-white/5'}`}>
            <div className="text-center text-sm font-semibold text-slate-400 mb-2">{day.label}</div>
            <div className="space-y-1">
              {day.events.slice(0, 3).map((event) => (
                <div key={event.id} className="text-xs text-white truncate bg-white/10 rounded px-1 py-0.5" title={event.title}>
                  {event.title}
                </div>
              ))}
              {day.events.length > 3 && (
                <div className="text-xs text-slate-500 text-center">+{day.events.length - 3} more</div>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderMonthly = () => {
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const startPadding = firstDay.getDay();
    const daysInMonth = lastDay.getDate();

    const cells: { day: number; isCurrentMonth: boolean; dateStr: string; events: WallEvent[] }[] = [];

    // Previous month padding
    for (let i = 0; i < startPadding; i++) {
      cells.push({ day: 0, isCurrentMonth: false, dateStr: '', events: [] });
    }

    // Current month
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const dayEvents = monthlyEvents.filter((e) => new Date(e.start_time).toISOString().split('T')[0] === dateStr);
      cells.push({ day: d, isCurrentMonth: true, dateStr, events: dayEvents });
    }

    return (
      <div className="grid grid-cols-7 gap-1 h-full">
        {days.map((d) => (
          <div key={d} className="text-center text-sm font-semibold text-slate-500">{d}</div>
        ))}
        {cells.map((cell, i) => (
          <div
            key={i}
            className={`rounded-lg p-1 min-h-[60px] ${
              !cell.isCurrentMonth ? 'bg-transparent' :
              cell.dateStr === todayStr ? 'bg-blue-600/20 border border-blue-500/30' : 'bg-white/5'
            }`}
          >
            {cell.isCurrentMonth && (
              <>
                <div className="text-sm text-white">{cell.day}</div>
                <div className="space-y-0.5 mt-1">
                  {cell.events.slice(0, 2).map((event) => (
                    <div key={event.id} className="text-[10px] text-white truncate bg-white/10 rounded px-0.5" title={event.title}>
                      {event.title}
                    </div>
                  ))}
                  {cell.events.length > 2 && (
                    <div className="text-[10px] text-slate-500">+{cell.events.length - 2}</div>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderContent = () => {
    switch (view) {
      case 'agenda': return renderAgenda();
      case 'daily': return renderDaily();
      case 'weekly': return renderWeekly();
      case 'monthly': return renderMonthly();
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-2xl font-bold text-white">Schedule</h2>
        <div className="flex gap-1">
          {viewButtons.map((btn) => (
            <button
              key={btn.key}
              onClick={() => setView(btn.key)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition ${
                view === btn.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-white/10 text-slate-300 hover:bg-white/20'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">{renderContent()}</div>
    </div>
  );
}
