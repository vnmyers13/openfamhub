import { useEffect, useState } from 'react'
import { cn } from '../lib/utils'

interface WallClockProps {
  className?: string
}

export default function WallClock({ className }: WallClockProps) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const timeStr = now.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const dateStr = now.toLocaleDateString([], {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })

  return (
    <div className={cn('flex flex-col', className)}>
      <span className="font-mono text-8xl font-bold tracking-tight text-white">
        {timeStr}
      </span>
      <span className="text-2xl text-slate-400">{dateStr}</span>
    </div>
  )
}
