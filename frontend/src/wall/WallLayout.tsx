import { useEffect, useRef, useState } from 'react'
import WallClock from './WallClock'
import WallSevenDayStrip from './WallSevenDayStrip'
import WallMemberList from './WallMemberList'
import WallPhotoPlaceholder from './WallPhotoPlaceholder'

const IDLE_MS = 300_000

export default function WallLayout() {
  const [isIdle, setIsIdle] = useState(false)
  const idleRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const resetIdle = () => {
    setIsIdle(false)
    if (idleRef.current) clearTimeout(idleRef.current)
    idleRef.current = setTimeout(() => setIsIdle(true), IDLE_MS)
  }

  useEffect(() => {
    const handlers = ['touchstart', 'mousemove'] as const
    for (const ev of handlers) {
      window.addEventListener(ev, resetIdle)
    }
    resetIdle()
    return () => {
      for (const ev of handlers) {
        window.removeEventListener(ev, resetIdle)
      }
      if (idleRef.current) clearTimeout(idleRef.current)
    }
  }, [])

  if (isIdle) {
    return (
      <div
        className="fixed inset-0 z-50 cursor-pointer"
        onClick={resetIdle}
      >
        <WallPhotoPlaceholder fullscreen />
        <div className="absolute bottom-8 right-8">
          <WallClock />
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 grid overflow-hidden bg-slate-900"
      style={{
        gridTemplateColumns: '380px 1fr',
      }}
    >
      {/* Left panel */}
      <div className="flex flex-col gap-8 border-r border-slate-700 p-8">
        <WallClock />
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Family
          </h2>
          <WallMemberList />
        </div>
      </div>

      {/* Right panel */}
      <WallSevenDayStrip />
    </div>
  )
}
