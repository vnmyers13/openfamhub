import { useState } from 'react'
import { useCalendarSources, useAddIcalSource, useSyncSource, useDeleteCalendarSource, useSourceLogs } from '../../api/calendar'

const COLOR_SWATCHES = ['#4F46E5', '#059669', '#DC2626', '#D97706', '#7C3AED', '#DB2777', '#0891B2', '#65A30D']

export default function CalendarSettings() {
  const { data: sources = [] } = useCalendarSources()
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [color, setColor] = useState(COLOR_SWATCHES[0])
  const [interval, setInterval] = useState(6)
  const [logSourceId, setLogSourceId] = useState<string | null>(null)

  const { mutateAsync: addIcal, isPending: adding } = useAddIcalSource()
  const { mutateAsync: syncSource, isPending: syncing } = useSyncSource()
  const { mutateAsync: deleteSource } = useDeleteCalendarSource()
  const { data: logs } = useSourceLogs(logSourceId)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url || !name) return
    await addIcal({ ics_url: url, display_name: name, color_hex: color, sync_interval_hours: interval })
    setUrl('')
    setName('')
    setColor(COLOR_SWATCHES[0])
    setInterval(6)
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Calendar Settings</h1>

        {/* Connected sources */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-3">Connected Sources</h2>
          {sources.length === 0 && <p className="text-gray-400 text-sm">No sources configured yet.</p>}
          <div className="space-y-3">
            {sources.map((s) => (
              <div key={s.id} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: s.color_hex }} />
                    <span className="text-white font-medium">{s.display_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${s.provider === 'internal' ? 'bg-gray-700 text-gray-300' : 'bg-blue-900 text-blue-300'}`}>
                      {s.provider}
                    </span>
                    {!s.enabled && <span className="text-xs text-red-400">Disabled</span>}
                  </div>
                  <div className="flex gap-2">
                    {s.provider === 'ical' && (
                      <button
                        onClick={() => syncSource(s.id)}
                        disabled={syncing}
                        className="bg-primary hover:bg-primary-dark text-white px-3 py-1 rounded text-sm disabled:opacity-50"
                      >
                        {syncing ? 'Syncing...' : 'Sync Now'}
                      </button>
                    )}
                    <button
                      onClick={() => setLogSourceId(logSourceId === s.id ? null : s.id)}
                      className="text-gray-400 hover:text-white text-sm px-2 py-1"
                    >
                      {logSourceId === s.id ? 'Hide Log' : 'Log'}
                    </button>
                    <button
                      onClick={() => deleteSource(s.id)}
                      className="text-red-400 hover:text-red-300 text-sm px-2 py-1"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="text-xs text-gray-500 space-y-0.5">
                  {s.last_synced_at && <p>Last synced: {new Date(s.last_synced_at).toLocaleString()}</p>}
                  {s.sync_error && <p className="text-red-400">Error: {s.sync_error}</p>}
                  <p>Sync interval: {s.sync_interval_hours}h</p>
                  {s.ics_url && <p className="truncate">URL: {s.ics_url}</p>}
                </div>

                {/* Sync log drawer */}
                {logSourceId === s.id && (
                  <div className="mt-3 border-t border-gray-800 pt-3">
                    <h4 className="text-sm font-medium text-gray-300 mb-2">Sync Log</h4>
                    {logs && logs.length === 0 && <p className="text-xs text-gray-500">No sync entries yet.</p>}
                    <div className="space-y-1 max-h-48 overflow-y-auto">
                      {logs?.map((log) => (
                        <div key={log.id} className="text-xs bg-gray-800 rounded p-2 flex justify-between">
                          <span className="text-gray-300">
                            {new Date(log.synced_at).toLocaleString()} &mdash; +{log.events_upserted} / -{log.events_deleted} ({log.duration_ms}ms)
                          </span>
                          {log.error && <span className="text-red-400 ml-2">{log.error}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Add ICS Feed */}
        <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <h2 className="text-lg font-semibold text-white mb-4">Add ICS Feed</h2>
          <form onSubmit={handleAdd} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">ICS URL</label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
                placeholder="https://example.com/calendar.ics"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Display Name</label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
                placeholder="Holidays"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Color</label>
              <div className="flex gap-2">
                {COLOR_SWATCHES.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    className={`w-8 h-8 rounded-full border-2 ${color === c ? 'border-white' : 'border-transparent'}`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Sync Interval</label>
              <select
                className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
                value={interval}
                onChange={(e) => setInterval(Number(e.target.value))}
              >
                <option value={1}>Every hour</option>
                <option value={3}>Every 3 hours</option>
                <option value={6}>Every 6 hours</option>
                <option value={12}>Every 12 hours</option>
                <option value={24}>Every 24 hours</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={adding}
              className="bg-primary hover:bg-primary-dark text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50"
            >
              {adding ? 'Adding...' : 'Add ICS Feed'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
