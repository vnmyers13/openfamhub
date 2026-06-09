import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

export default function Login() {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [profiles, setProfiles] = useState([])
  const [selectedProfile, setSelectedProfile] = useState(null)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  useState(() => {
    fetch('/api/auth/profiles')
      .then((r) => r.json())
      .then((data) => {
        setProfiles(data)
        if (data.length === 1) {
          setSelectedProfile(data[0])
        }
      })
  })

  const handlePinSubmit = async (e) => {
    e.preventDefault()
    if (!selectedProfile) {
      setError('Please select a profile')
      return
    }
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Login failed')
      }
      const data = await res.json()
      login(data.access_token, data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
      setPin('')
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#1a1a2e] text-white">
      {!selectedProfile ? (
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-8">Welcome to OpenFamHub</h1>
          <p className="text-xl mb-8">Select your profile</p>
          <div className="flex gap-8 justify-center flex-wrap">
            {profiles.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedProfile(p)}
                className="flex flex-col items-center gap-2 p-6 rounded-xl bg-white/5 hover:bg-white/10 transition"
              >
                <span className="text-5xl">{p.avatar_emoji}</span>
                <span className="text-lg">{p.name}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-8">
            <span className="text-5xl">{selectedProfile.avatar_emoji}</span>
            <h2 className="text-3xl font-bold">{selectedProfile.name}</h2>
          </div>
          <form onSubmit={handlePinSubmit} className="flex flex-col items-center gap-4">
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              placeholder="Enter PIN"
              autoFocus
              className="text-center text-3xl tracking-[0.5em] w-48 p-4 rounded-xl bg-white/10 border border-white/20 focus:border-white/50 focus:outline-none"
            />
            {error && <p className="text-red-400">{error}</p>}
            <button
              type="submit"
              className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-lg font-semibold transition"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setSelectedProfile(null)}
              className="text-gray-400 hover:text-white"
            >
              Back to profiles
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
