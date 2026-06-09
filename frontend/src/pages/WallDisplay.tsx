import { useState, useEffect } from 'react'

export default function WallDisplay() {
  const [events, setEvents] = useState([])
  const [announcements, setAnnouncements] = useState([])

  useEffect(() => {
    Promise.all([
      fetch('/api/events').then((r) => r.json()),
      fetch('/api/announcements').then((r) => r.json()),
    ]).then(([evts, anns]) => {
      setEvents(evts)
      setAnnouncements(anns)
    })
  }, [])

  const now = new Date()
  const today = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })

  const todayEvents = events.filter((e) => {
    const start = new Date(e.start_time)
    return start.toDateString() === now.toDateString()
  }).sort((a, b) => new Date(a.start_time) - new Date(b.start_time))

  return (
    <div className="h-screen w-screen bg-[#1a1a2e] flex flex-col overflow-hidden">
      <header className="bg-[#16213e] px-8 py-4 flex justify-between items-center">
        <h1 className="text-3xl font-bold">OpenFamHub</h1>
        <div className="text-right">
          <p className="text-2xl">{today}</p>
          <p className="text-xl text-gray-400">{time}</p>
        </div>
      </header>
      <div className="flex-1 p-8 grid grid-cols-3 gap-8">
        <div className="col-span-2 bg-[#16213e] rounded-2xl p-6">
          <h2 className="text-2xl font-bold mb-4">Today's Schedule</h2>
          {todayEvents.length === 0 ? (
            <p className="text-gray-400 text-xl">No events today</p>
          ) : (
            <div className="space-y-3">
              {todayEvents.map((event) => (
                <div key={event.id} className="flex items-center gap-4 p-4 rounded-xl bg-white/5">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: event.color_hex || '#3b82f6' }} />
                  <div>
                    <p className="text-xl font-semibold">{event.title}</p>
                    <p className="text-gray-400">
                      {new Date(event.start_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })}
                      {' - '}
                      {new Date(event.end_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="bg-[#16213e] rounded-2xl p-6 overflow-y-auto">
          <h2 className="text-2xl font-bold mb-4">Announcements</h2>
          {announcements.length === 0 ? (
            <p className="text-gray-400 text-xl">No announcements</p>
          ) : (
            <div className="space-y-4">
              {announcements.map((a) => (
                <div key={a.id} className={`p-4 rounded-xl ${a.is_pinned ? 'bg-yellow-500/10 border border-yellow-500/30' : 'bg-white/5'}`}>
                  <p className="text-lg">{a.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
