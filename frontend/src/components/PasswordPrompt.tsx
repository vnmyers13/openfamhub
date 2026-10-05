import { useEffect, useRef, useState } from 'react'
import { apiClient, errorDetail, onPasswordPrompt } from '../api/client'
import { useAuthStore } from '../stores/auth'

type Pending = { resolve: () => void; reject: () => void }

/**
 * Shown when an admin who signed in with a PIN does something admin-only.
 * Confirming the password unlocks admin actions for 15 minutes, then the
 * original request is retried.
 */
export default function PasswordPrompt() {
  const setUser = useAuthStore((s) => s.setUser)
  const [pending, setPending] = useState<Pending | null>(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => onPasswordPrompt((req) => setPending(req)), [])

  useEffect(() => {
    if (pending) inputRef.current?.focus()
  }, [pending])

  if (!pending) return null

  const close = (ok: boolean) => {
    if (ok) pending.resolve()
    else pending.reject()
    setPending(null)
    setPassword('')
    setError('')
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await apiClient.post('/auth/elevate', { password })
      setUser(res.data)
      close(true)
    } catch (err) {
      setError(errorDetail(err, 'Could not confirm your password'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div>
          <h2 className="text-lg font-semibold text-white">Confirm your password</h2>
          <p className="mt-1 text-sm text-gray-400">
            You signed in with a PIN. Admin changes need your password; this unlocks them for 15 minutes.
          </p>
        </div>
        {error && <div className="rounded bg-red-900/50 px-3 py-2 text-sm text-red-300">{error}</div>}
        <input
          ref={inputRef}
          type="password"
          autoComplete="current-password"
          className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-primary focus:outline-none"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => close(false)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-white">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || !password}
            className="rounded bg-primary px-4 py-1.5 text-sm text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {busy ? 'Checking...' : 'Unlock'}
          </button>
        </div>
      </form>
    </div>
  )
}
