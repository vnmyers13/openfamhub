import { useWallBirthdays } from '../api/wall'
import Avatar from '../components/Avatar'

/** "Kid turns 9 · Friday" (or "Oct 24" when more than a week away) for birthdays in the next two weeks; nothing otherwise. */
export default function WallBirthdays() {
  const { data } = useWallBirthdays()
  if (!data || data.length === 0) return null
  return (
    <section aria-label="Birthdays">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Birthdays</h2>
      <ul className="flex flex-col gap-2">
        {data.map((b) => (
          <li key={b.user_id} className="flex items-center gap-3 text-lg text-slate-200">
            <Avatar name={b.display_name} color={b.color_hex} emoji={b.avatar_value} className="h-8 w-8 text-base" />
            <span className="flex-1">{b.display_name} turns {b.turns}</span>
            <span className="text-slate-400">{b.days_away === 0 ? '🎂 Today!' : b.days_away === 1 ? 'Tomorrow'
              : new Date(`${b.date}T00:00:00`).toLocaleDateString([], b.days_away < 7 ? { weekday: 'long' } : { month: 'short', day: 'numeric' })}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
