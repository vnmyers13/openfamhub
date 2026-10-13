import { useEffect, useState } from 'react'
import { addDays, isSameDay, startOfDay } from 'date-fns'

/**
 * Local midnight today, updated when the day changes. Wall displays run for
 * days without a reload, so a value computed once at mount goes stale at
 * midnight. A timer fires just after the next local midnight; returning to the
 * page (a tablet waking up) also re-checks, in case the timer was missed.
 */
export function useToday(): Date {
  const [today, setToday] = useState(() => startOfDay(new Date()))

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined

    const refresh = () => {
      const now = new Date()
      setToday((prev) => (isSameDay(prev, now) ? prev : startOfDay(now)))
      clearTimeout(timer)
      // A second past midnight, so the timer can't fire a hair early.
      timer = setTimeout(refresh, addDays(startOfDay(now), 1).getTime() - now.getTime() + 1000)
    }

    refresh()
    document.addEventListener('visibilitychange', refresh)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [])

  return today
}
