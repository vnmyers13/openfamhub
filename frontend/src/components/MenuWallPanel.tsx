import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

interface WallMeal {
  id: string;
  meal_type: string;
  date: string;
  title: string;
  notes?: string | null;
  recipe?: { id: string; title: string } | null;
}

const MEAL_ORDER = ['breakfast', 'lunch', 'dinner', 'snack'];

export default function MenuWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-menu'],
    queryFn: async () => {
      const res = await api.get('/meals/plans');
      const meals = res.data as { meals: WallMeal[] };
      const today = new Date().toISOString().split('T')[0];
      return meals.meals.filter((m) => m.date === today).sort((a, b) => {
        return MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type);
      });
    },
    refetchInterval: 60000,
  });

  const meals = data as WallMeal[] | undefined;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading menu...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load menu</div>
      </div>
    );
  }

  if (!meals || meals.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No meals planned for today</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {meals.map((meal) => (
        <div key={meal.id} className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-1">
            {meal.meal_type}
          </div>
          <div className="text-2xl font-semibold text-white">
            {meal.recipe?.title || meal.title}
          </div>
          {meal.notes && (
            <div className="text-slate-400 text-lg mt-1">{meal.notes}</div>
          )}
        </div>
      ))}
    </div>
  );
}
