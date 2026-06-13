import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { weatherAPI } from '../api/client'
import { useAuthStore } from '../stores/auth'

export default function SetupWizard() {
  const [step, setStep] = useState<'account' | 'weather'>('account')
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [weatherLat, setWeatherLat] = useState('')
  const [weatherLon, setWeatherLon] = useState('')
  const [weatherLocation, setWeatherLocation] = useState('')
  const [geolocating, setGeolocating] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleUseMyLocation = () => {
    setGeolocating(true)
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser')
      setGeolocating(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setWeatherLat(position.coords.latitude.toFixed(4))
        setWeatherLon(position.coords.longitude.toFixed(4))
        setGeolocating(false)
      },
      () => {
        alert('Unable to retrieve your location')
        setGeolocating(false)
      }
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (pin !== confirmPin) {
      setError('PINs do not match')
      return
    }

    if (pin.length < 4) {
      setError('PIN must be at least 4 digits')
      return
    }

    setLoading(true)
    try {
      const res = await fetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, pin }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Setup failed')
      }

      const data = await res.json()
      login(data.access_token, data.user)
      setStep('weather')
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Setup failed')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleWeatherSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const lat = parseFloat(weatherLat)
    const lon = parseFloat(weatherLon)
    if (isNaN(lat) || isNaN(lon)) {
      setError('Please enter valid coordinates')
      return
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setError('Coordinates out of range')
      return
    }

    setLoading(true)
    try {
      await weatherAPI.updateSettings({ lat, lon, location_name: weatherLocation || undefined })
      navigate('/dashboard')
    } catch {
      setError('Failed to save location')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#1a1a2e] text-white px-4">
      <div className="w-full max-w-md">
        {step === 'account' ? (
          <div>
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold mb-2">Welcome to OpenFamHub</h1>
              <p className="text-gray-400">Set up your admin account to get started</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Your Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="Enter your name"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">PIN (4-6 digits)</label>
                <input
                  type="password"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={pin}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-center text-3xl tracking-[0.5em]"
                  placeholder="****"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Confirm PIN</label>
                <input
                  type="password"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={confirmPin}
                  onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ''))}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-center text-3xl tracking-[0.5em]"
                  placeholder="****"
                  required
                />
              </div>

              {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-center">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-lg font-semibold transition"
              >
                {loading ? 'Creating Account...' : 'Create Admin Account'}
              </button>
            </form>

            <div className="mt-8 text-center">
              <button
                onClick={async () => {
                  if (!confirm('This will remove all existing accounts. Continue?')) return
                  try {
                    await fetch('/api/auth/reset-setup', { method: 'POST' })
                    setError('Setup reset. You can now create a new admin account.')
                  } catch {
                    setError('Failed to reset setup')
                  }
                }}
                className="text-sm text-gray-500 hover:text-white transition"
              >
                Reset setup
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold mb-2">Set Your Location</h1>
              <p className="text-gray-400">This helps us show local weather on your dashboard</p>
            </div>

            <form onSubmit={handleWeatherSubmit} className="space-y-6">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={weatherLat}
                  onChange={(e) => setWeatherLat(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. 41.8781"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={weatherLon}
                  onChange={(e) => setWeatherLon(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. -87.6298"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Location Name (optional)</label>
                <input
                  type="text"
                  value={weatherLocation}
                  onChange={(e) => setWeatherLocation(e.target.value)}
                  className="w-full p-4 rounded-xl bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-lg"
                  placeholder="e.g. Chicago"
                />
              </div>

              <button
                type="button"
                onClick={handleUseMyLocation}
                disabled={geolocating}
                className="w-full py-3 rounded-xl bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-50 transition"
              >
                {geolocating ? 'Getting location...' : 'Use my location'}
              </button>

              {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-center">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-lg font-semibold transition"
              >
                {loading ? 'Saving...' : 'Continue to Dashboard'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
