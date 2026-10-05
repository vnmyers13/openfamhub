import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorDetail } from '../api/client'
import { useAuthStore } from '../stores/auth'
import Avatar from '../components/Avatar'

interface User {
  id: string
  display_name: string
  email: string | null
  role: string
  color_hex: string
  ui_mode: string
  has_password: boolean
  has_pin: boolean
  avatar_type: string | null
  avatar_value: string | null
  family_id: string
  last_login_at: string | null
  created_at: string | null
}

const AVATARS = ['🦊', '🐻', '🐼', '🐯', '🦁', '🐸', '🐵', '🦄', '🐙', '🐢', '🦖', '🐝', '🌟', '🚀', '⚽', '🎸']
const ROLES = [
  { value: 'admin', label: 'Admin (parents)' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer (read-only)' },
]

interface FormValues {
  display_name: string
  role: string
  color_hex: string
  avatar: string
  pin: string
  password: string
}

export default function ManageUsers() {
  const { user: currentUser } = useAuthStore()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: async () => (await apiClient.get('/users/')).data as User[],
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['users'] })
    qc.invalidateQueries({ queryKey: ['auth-profiles'] })
  }
  const remove = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/users/${id}`),
    onSuccess: refresh,
  })

  if (currentUser?.role !== 'admin') {
    return <div className="p-8 text-center text-gray-400">Access denied</div>
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">Family members</h1>
          <button
            onClick={() => {
              setEditing(null)
              setShowCreate(true)
            }}
            className="rounded bg-primary px-4 py-2 font-medium text-white hover:bg-primary-dark"
          >
            Add member
          </button>
        </div>

        {(showCreate || editing) && (
          <UserForm
            key={editing?.id ?? 'new'}
            user={editing}
            onDone={() => {
              setShowCreate(false)
              setEditing(null)
              refresh()
            }}
            onCancel={() => {
              setShowCreate(false)
              setEditing(null)
            }}
          />
        )}

        {isLoading ? (
          <div className="py-8 text-center text-gray-400">Loading...</div>
        ) : (
          <div className="space-y-3">
            {users.map((u) => (
              <div key={u.id} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-4">
                <div className="flex items-center gap-3">
                  <Avatar name={u.display_name} color={u.color_hex} emoji={u.avatar_value} className="h-10 w-10 text-xl" />
                  <div>
                    <div className="font-medium text-white">{u.display_name}</div>
                    <div className="text-sm text-gray-400">
                      {u.role}
                      {u.has_pin ? ' · PIN' : ''}
                      {u.has_password ? ' · password' : ''}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => setEditing(u)} className="text-sm text-gray-400 hover:text-white">
                    Edit
                  </button>
                  {u.id !== currentUser?.id && (
                    <button
                      onClick={() => {
                        if (confirm(`Remove ${u.display_name}? They will be signed out everywhere.`)) remove.mutate(u.id)
                      }}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function UserForm({ user, onDone, onCancel }: { user: User | null; onDone: () => void; onCancel: () => void }) {
  const isNew = user === null
  const [values, setValues] = useState<FormValues>({
    display_name: user?.display_name ?? '',
    role: user?.role ?? 'member',
    color_hex: user?.color_hex ?? '#4F46E5',
    avatar: user?.avatar_value ?? AVATARS[0],
    pin: '',
    password: '',
  })
  const [error, setError] = useState('')
  const set = (k: keyof FormValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setValues((v) => ({ ...v, [k]: e.target.value }))

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        display_name: values.display_name,
        role: values.role,
        color_hex: values.color_hex,
        avatar: values.avatar,
        pin: values.pin || undefined,
        password: values.password || undefined,
      }
      return isNew ? apiClient.post('/users/', body) : apiClient.patch(`/users/${user!.id}`, body)
    },
    onSuccess: onDone,
    onError: (err) => setError(errorDetail(err, 'Could not save')),
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (values.pin && !/^\d{4,8}$/.test(values.pin)) return setError('PIN must be 4-8 digits')
    if (values.password && values.password.length < 8) return setError('Password must be at least 8 characters')
    if (isNew && !values.pin && !values.password) return setError('Give them a PIN, a password, or both')
    if (values.role === 'admin' && isNew && !values.password) return setError('Admins need a password for admin changes')
    save.mutate()
  }

  const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white'
  return (
    <form onSubmit={submit} className="mb-4 space-y-4 rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h2 className="font-semibold text-white">{isNew ? 'Add a family member' : `Edit ${user!.display_name}`}</h2>
      {error && <div className="rounded bg-red-900/50 px-4 py-2 text-sm text-red-300">{error}</div>}
      <div>
        <span className="mb-1 block text-sm text-gray-300">Avatar</span>
        <div className="flex flex-wrap gap-2">
          {AVATARS.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setValues((v) => ({ ...v, avatar: a }))}
              className={`flex h-10 w-10 items-center justify-center rounded-full text-xl ${values.avatar === a ? 'ring-2 ring-white' : ''}`}
              style={{ backgroundColor: values.color_hex }}
              aria-label={`Avatar ${a}`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm text-gray-300">
          Name
          <input className={input} value={values.display_name} onChange={set('display_name')} required maxLength={100} />
        </label>
        <label className="text-sm text-gray-300">
          Role
          <select className={input} value={values.role} onChange={set('role')}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-300">
          {isNew ? 'PIN (4-8 digits)' : 'New PIN (leave blank to keep)'}
          <input className={input} value={values.pin} onChange={set('pin')} inputMode="numeric" autoComplete="off" maxLength={8} />
        </label>
        <label className="text-sm text-gray-300">
          {isNew ? 'Password (optional for kids)' : 'New password (leave blank to keep)'}
          <input className={input} type="password" value={values.password} onChange={set('password')} autoComplete="new-password" />
        </label>
        <label className="text-sm text-gray-300">
          Color
          <input type="color" className="h-9 w-full cursor-pointer rounded border border-gray-700 bg-gray-800" value={values.color_hex} onChange={set('color_hex')} />
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="px-3 py-1 text-sm text-gray-400 hover:text-white">
          Cancel
        </button>
        <button type="submit" disabled={save.isPending} className="rounded bg-primary px-4 py-1 text-sm text-white hover:bg-primary-dark disabled:opacity-50">
          {save.isPending ? 'Saving...' : 'Save'}
        </button>
      </div>
    </form>
  )
}
