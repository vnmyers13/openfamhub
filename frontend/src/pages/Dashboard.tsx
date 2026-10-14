import { useDashboardSummary, type DashboardSummary } from '../api/home'
import { WIDGETS, type WidgetKey } from '../lib/dashboard'
import { useAuthStore } from '../stores/auth'
import {
  Announcements, Birthdays, FamilyStars, MealsToday, MyDay, SyncStatus, TodaysEvents, WeatherCard,
} from './dashboard/widgets'

const RENDER: Record<WidgetKey, (s?: DashboardSummary) => React.ReactNode> = {
  events: (s) => <TodaysEvents summary={s} />,
  weather: () => <WeatherCard />,
  'my-day': (s) => <MyDay summary={s} />,
  meals: (s) => <MealsToday summary={s} />,
  stars: () => <FamilyStars />,
  announcements: (s) => <Announcements summary={s} />,
  birthdays: (s) => <Birthdays summary={s} />,
  sync: () => <SyncStatus />,
}

function Greeting() {
  const user = useAuthStore((s) => s.user)
  const hour = new Date().getHours()
  let period = 'evening'
  if (hour < 12) period = 'morning'
  else if (hour < 17) period = 'afternoon'
  return (
    <h1 className="text-3xl font-bold text-white">
      Good {period}, {user?.display_name ?? 'there'}!
    </h1>
  )
}

/** Home: one summary call feeds most cards; weather and stars load on their own. */
export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const { data: summary } = useDashboardSummary()
  const widgets = WIDGETS.filter((w) => !('adminOnly' in w && w.adminOnly) || user?.role === 'admin')
  return (
    <div className="flex flex-col gap-6 p-6">
      <Greeting />
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {widgets.map((w) => <div key={w.key}>{RENDER[w.key](summary)}</div>)}
      </div>
    </div>
  )
}
