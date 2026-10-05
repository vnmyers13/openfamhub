import { useState } from 'react'
import { useCreateWallDevice, useRevokeWallDevice, useWallDevices } from '../../api/wall'

export default function WallDisplays() {
  const { data: devices = [], isLoading } = useWallDevices()
  const { mutateAsync: createDevice, isPending: creating } = useCreateWallDevice()
  const { mutateAsync: revokeDevice } = useRevokeWallDevice()
  const [name, setName] = useState('')
  const [pairUrl, setPairUrl] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setCopied(false)
    try {
      const device = await createDevice(name.trim())
      setPairUrl(`${window.location.origin}/wall?token=${encodeURIComponent(device.token)}`)
      setName('')
    } catch {
      setError('Could not create the display')
    }
  }

  const handleCopy = async () => {
    if (!pairUrl) return
    try {
      await navigator.clipboard.writeText(pairUrl)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const handleRevoke = async (id: string, deviceName: string) => {
    if (!confirm(`Unpair "${deviceName}"? It will stop showing the calendar until paired again.`)) return
    await revokeDevice(id)
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-2 text-2xl font-bold text-white">Wall displays</h1>
        <p className="mb-6 text-sm text-gray-400">
          A paired display shows the calendar and family members read-only, and stays signed in until you unpair it.
        </p>

        <form onSubmit={handleCreate} className="mb-6 flex gap-2 rounded-xl border border-gray-800 bg-gray-900 p-4">
          <input
            className="flex-1 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white"
            placeholder="Display name, e.g. Kitchen"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={64}
            required
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-primary px-4 py-2 font-medium text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {creating ? 'Creating...' : 'Create pairing link'}
          </button>
        </form>
        {error && <div className="mb-4 rounded bg-red-900/50 px-4 py-2 text-sm text-red-300">{error}</div>}

        {pairUrl && (
          <div className="mb-6 rounded-xl border border-primary/40 bg-gray-900 p-4">
            <p className="mb-2 text-sm text-gray-300">
              Open this link once on the display. It's shown only now. Anyone with it can view the calendar, so don't share it.
            </p>
            <div className="flex gap-2">
              <code className="flex-1 truncate rounded bg-gray-800 px-3 py-2 text-xs text-gray-200">{pairUrl}</code>
              <button onClick={handleCopy} className="rounded bg-gray-700 px-3 py-1 text-sm text-white hover:bg-gray-600">
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
        )}

        <h2 className="mb-3 text-lg font-semibold text-white">Paired displays</h2>
        {isLoading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : devices.length === 0 ? (
          <p className="text-sm text-gray-400">No displays paired yet.</p>
        ) : (
          <div className="space-y-2">
            {devices.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-3">
                <div>
                  <div className="font-medium text-white">{d.name}</div>
                  <div className="text-xs text-gray-500">
                    {d.last_seen_at ? `Last seen ${new Date(d.last_seen_at).toLocaleString()}` : 'Not opened yet'}
                  </div>
                </div>
                <button onClick={() => handleRevoke(d.id, d.name)} className="text-sm text-red-400 hover:text-red-300">
                  Unpair
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
