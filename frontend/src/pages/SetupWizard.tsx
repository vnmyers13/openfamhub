import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuthStore } from '../stores/auth'
import BuildInfoBadge from '../components/BuildInfoBadge'

// The family timezone decides how calendar feeds' floating times (no zone
// given) are read, so default to this device's zone rather than UTC, and offer
// every zone the browser knows.
function deviceZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

function allZones(first: string): string[] {
  let zones: string[]
  try {
    zones = (Intl as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? []
  } catch {
    zones = []
  }
  const common = ['UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles']
  return Array.from(new Set([first, ...common, ...zones]))
}

export default function SetupWizard() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const [familyName, setFamilyName] = useState('')
  const [timezone, setTimezone] = useState(deviceZone)
  const [zones] = useState(() => allZones(deviceZone()))
  const [adminName, setAdminName] = useState('')
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (pin && !/^\d{4,8}$/.test(pin)) {
      setError('PIN must be 4-8 digits')
      return
    }
    setLoading(true)
    try {
      const res = await apiClient.post('/auth/setup', {
        family_name: familyName,
        timezone,
        admin_display_name: adminName,
        admin_password: password,
        admin_pin: pin || undefined,
      })
      setUser(res.data)
      navigate('/dashboard')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Setup failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold text-white text-center mb-2">OpenFamHub</h1>
        <p className="text-gray-400 text-center mb-8">Set up your family hub</p>
        <form onSubmit={handleSubmit} className="bg-gray-900 rounded-xl p-6 space-y-4 border border-gray-800">
          {error && <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded text-sm">{error}</div>}
          <div>
            <label className="block text-sm text-gray-300 mb-1">Family Name</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
              value={familyName}
              onChange={(e) => setFamilyName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Timezone</label>
            <select
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {zones.map((z) => (
                <option key={z} value={z}>
                  {z === zones[0] ? `${z.replace(/_/g, ' ')} (this device)` : z.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Admin Name</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Admin Password</label>
            <input
              type="password"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Your PIN (optional, 4-8 digits)</label>
            <input
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">For quick sign-in from the family picker. Admin changes still ask for the password.</p>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary hover:bg-primary-dark text-white rounded py-2 font-medium disabled:opacity-50"
          >
            {loading ? 'Setting up...' : 'Create Family Hub'}
          </button>
        </form>
        <BuildInfoBadge className="mx-auto mt-6 max-w-xs text-center" />
      </div>
    </div>
  )
}
