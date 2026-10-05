import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorDetail } from '../api/client'
import { useAuthStore } from '../stores/auth'
import Avatar from '../components/Avatar'

interface Profile {
  id: string
  display_name: string
  color_hex: string
  avatar_type: string | null
  avatar_value: string | null
  has_pin: boolean
}

type Mode = 'pick' | 'pin' | 'password'

const PIN_MAX = 8

export default function Login() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['auth-profiles'],
    queryFn: async () => (await apiClient.get('/auth/profiles')).data as Profile[],
    retry: false,
  })
  const pinProfiles = profiles.filter((p) => p.has_pin)

  const [modeChoice, setModeChoice] = useState<Mode | null>(null)
  // Until the person picks a mode, show the picker when anyone has a PIN.
  const mode: Mode = modeChoice ?? (pinProfiles.length > 0 ? 'pick' : 'password')
  const [selected, setSelected] = useState<Profile | null>(null)
  const [pin, setPin] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const signedIn = (user: unknown) => {
    setUser(user as Parameters<typeof setUser>[0])
    navigate('/dashboard')
  }

  const choose = (p: Profile) => {
    setSelected(p)
    setPin('')
    setError('')
    setModeChoice('pin')
  }

  const submitPin = async (value: string) => {
    if (!selected || value.length < 4) return
    setLoading(true)
    setError('')
    try {
      const res = await apiClient.post('/auth/login/pin', { user_id: selected.id, pin: value })
      signedIn(res.data)
    } catch (err) {
      setError(errorDetail(err, 'Sign-in failed'))
      setPin('')
    } finally {
      setLoading(false)
    }
  }

  const submitPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await apiClient.post('/auth/login', { display_name: displayName, password })
      signedIn(res.data)
    } catch (err) {
      setError(errorDetail(err, 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  // Physical keyboard support for the PIN pad.
  useEffect(() => {
    if (mode !== 'pin') return
    const onKey = (e: KeyboardEvent) => {
      if (/^\d$/.test(e.key)) setPin((p) => (p.length < PIN_MAX ? p + e.key : p))
      else if (e.key === 'Backspace') setPin((p) => p.slice(0, -1))
      else if (e.key === 'Enter') submitPin(pin)
      else if (e.key === 'Escape') setModeChoice('pick')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 p-4">
      <div className="w-full max-w-lg">
        <h1 className="mb-2 text-center text-3xl font-bold text-white">OpenFamHub</h1>
        <p className="mb-8 text-center text-gray-400">
          {mode === 'pick' ? "Who's here?" : mode === 'pin' && selected ? `Hi ${selected.display_name}! Enter your PIN` : 'Sign in with your password'}
        </p>

        {error && <div className="mb-4 rounded bg-red-900/50 px-4 py-2 text-center text-sm text-red-300">{error}</div>}

        {mode === 'pick' && (
          <>
            {isLoading ? (
              <div className="text-center text-gray-500">Loading…</div>
            ) : (
              <div className="grid grid-cols-3 gap-4 sm:grid-cols-4">
                {pinProfiles.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => choose(p)}
                    className="flex flex-col items-center gap-2 rounded-xl p-3 hover:bg-gray-900 focus:bg-gray-900 focus:outline-none"
                  >
                    <Avatar name={p.display_name} color={p.color_hex} emoji={p.avatar_value} className="h-16 w-16 text-3xl" />
                    <span className="truncate text-sm text-gray-200">{p.display_name}</span>
                  </button>
                ))}
              </div>
            )}
            <button onClick={() => setModeChoice('password')} className="mx-auto mt-8 block text-sm text-gray-400 hover:text-white">
              Sign in with a password instead
            </button>
          </>
        )}

        {mode === 'pin' && selected && (
          <div className="mx-auto max-w-xs">
            <div className="mb-6 flex justify-center">
              <Avatar name={selected.display_name} color={selected.color_hex} emoji={selected.avatar_value} className="h-20 w-20 text-4xl" />
            </div>
            <div className="mb-6 flex justify-center gap-3" aria-label={`${pin.length} digits entered`}>
              {Array.from({ length: Math.max(4, pin.length) }).map((_, i) => (
                <span key={i} className={`h-4 w-4 rounded-full ${i < pin.length ? 'bg-white' : 'bg-gray-700'}`} />
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
                <PadButton key={d} onClick={() => setPin((p) => (p.length < PIN_MAX ? p + d : p))} disabled={loading}>
                  {d}
                </PadButton>
              ))}
              <PadButton onClick={() => setPin((p) => p.slice(0, -1))} disabled={loading} aria-label="Delete">
                ⌫
              </PadButton>
              <PadButton onClick={() => setPin((p) => (p.length < PIN_MAX ? p + '0' : p))} disabled={loading}>
                0
              </PadButton>
              <PadButton onClick={() => submitPin(pin)} disabled={loading || pin.length < 4} aria-label="Sign in">
                ✓
              </PadButton>
            </div>
            <div className="mt-6 flex justify-between text-sm">
              <button onClick={() => setModeChoice('pick')} className="text-gray-400 hover:text-white">
                ← Not {selected.display_name}?
              </button>
              <button
                onClick={() => {
                  setDisplayName(selected.display_name)
                  setModeChoice('password')
                }}
                className="text-gray-400 hover:text-white"
              >
                Use password
              </button>
            </div>
          </div>
        )}

        {mode === 'password' && (
          <form onSubmit={submitPassword} className="space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-6">
            <div>
              <label className="mb-1 block text-sm text-gray-300" htmlFor="login-name">Name</label>
              <input
                id="login-name"
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-300" htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded bg-primary py-2 font-medium text-white hover:bg-primary-dark disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            {pinProfiles.length > 0 && (
              <button type="button" onClick={() => setModeChoice('pick')} className="mx-auto block text-sm text-gray-400 hover:text-white">
                ← Back to the family picker
              </button>
            )}
          </form>
        )}
      </div>
    </div>
  )
}

function PadButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="h-16 rounded-xl bg-gray-800 text-2xl font-semibold text-white hover:bg-gray-700 active:bg-gray-600 disabled:opacity-40"
    />
  )
}
