import { useEffect, useState } from 'react'
import { cn } from '../lib/utils'

interface WallClockProps {
  className?: string
  /** The family timezone (Admin › Settings). Without it (an unpaired screen), the display's own zone. */
  timeZone?: string
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

export default function WallClock({ className, timeZone }: WallClockProps) {
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
    </div>
  )
}
