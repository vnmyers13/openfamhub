import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

export default function SetupWizard() {
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

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
      navigate('/dashboard')
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

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#1a1a2e] text-white px-4">
      <div className="w-full max-w-md">
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
    </div>
  )
}
