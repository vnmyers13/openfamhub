import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { wallChoreAPI } from '../api/client';

interface WallChore {
  id: string;
  title: string;
  assigned_to_name?: string | null;
  status: string;
  due_date: string;
  completed_at?: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  claimed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  completed: 'bg-green-500/20 text-green-400 border-green-500/30',
  expired: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function ChoresWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-chores'],
    queryFn: () => wallChoreAPI.getWallChores(),
    refetchInterval: 60000,
  });

  const chores = data as WallChore[] | undefined;
  const [view, setView] = useState<'all' | 'pending'>('pending');

  const filteredChores = view === 'pending'
    ? chores?.filter((c) => c.status !== 'completed')
    : chores;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading chores...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load chores</div>
      </div>
    );
  }

  if (!filteredChores || filteredChores.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No chores to display</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-2xl font-bold text-white">Chores</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setView('pending')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition ${
              view === 'pending'
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-slate-300 hover:bg-white/20'
            }`}
          >
            Pending
          </button>
          <button
            onClick={() => setView('all')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition ${
              view === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-slate-300 hover:bg-white/20'
            }`}
          >
            All
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2">
        {filteredChores.map((chore) => (
          <div key={chore.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
            <div className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_COLORS[chore.status] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'}`}>
              {chore.status}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xl font-semibold text-white truncate">{chore.title}</p>
              {chore.assigned_to_name && (
                <p className="text-slate-400 text-lg">{chore.assigned_to_name}</p>
              )}
            </div>
            <div className="text-slate-400 text-lg flex-shrink-0">
              {chore.status === 'completed' ? '✅' : `Due: ${chore.due_date}`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
