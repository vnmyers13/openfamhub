import { useEffect, useState } from 'react'
import type { WorldClock } from '../api/family'
import { cn } from '../lib/utils'

interface WallClockProps {
  className?: string
  /** The family timezone (Admin › Settings). Without it (an unpaired screen), the display's own zone. */
  timeZone?: string
  /** Extra clocks under the main one (Admin › Settings). */
  clocks?: WorldClock[]
}

function validZone(timeZone: string | undefined): string | undefined {
  if (!timeZone) return undefined
  try {
    new Intl.DateTimeFormat([], { timeZone })
    return timeZone
  } catch {
    return undefined  // an unknown zone shouldn't blank the clock
  }
}

export default function WallClock({ className, timeZone, clocks = [] }: WallClockProps) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const zone = validZone(timeZone)
  const timeStr = now.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: zone,
  })
  const dateStr = now.toLocaleDateString([], {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    timeZone: zone,
  })

  return (
    <div className={cn('flex flex-col', className)}>
      <span className="font-mono text-8xl font-bold tracking-tight text-white" data-testid="wall-time">
        {timeStr}
      </span>
      <span className="text-2xl text-slate-400" data-testid="wall-date">{dateStr}</span>
      {clocks.length > 0 && (
        <ul className="mt-3 space-y-1">
          {clocks.map((c) => <ExtraClock key={`${c.label}-${c.timezone}`} clock={c} now={now} homeZone={zone} />)}
        </ul>
      )}
    </div>
  )
}

const dayIn = (now: Date, timeZone: string | undefined) =>
  now.toLocaleDateString('en-CA', { timeZone })  // YYYY-MM-DD, for comparing days

/** "Grandma  04:30 Wed": the weekday only when it isn't the family's day. */
function ExtraClock({ clock, now, homeZone }: { clock: WorldClock; now: Date; homeZone: string | undefined }) {
  const zone = validZone(clock.timezone)
  if (!zone) return null
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: zone })
  const otherDay = dayIn(now, zone) !== dayIn(now, homeZone)
  return (
    <li className="flex items-baseline justify-between gap-4 text-lg" data-testid="wall-extra-clock">
      <span className="truncate text-slate-400">{clock.label}</span>
      <span className="font-mono text-slate-200">
        {time}{otherDay && <span className="text-sm text-slate-500"> {now.toLocaleDateString([], { weekday: 'short', timeZone: zone })}</span>}
      </span>
    </li>
  )
}
