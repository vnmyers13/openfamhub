import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import { useAuthStore } from '../stores/auth'

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

export default function ManageUsers() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<User[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchUsers = useCallback(async () => {
    const res = await apiClient.get('/users/')
    setUsers(res.data)
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this user?')) return
    await apiClient.delete(`/users/${id}`)
    fetchUsers()
  }

  if (currentUser?.role !== 'admin') {
    return <div className="text-gray-400 p-8 text-center">Access denied</div>
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Manage Users</h1>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded font-medium"
          >
            Add User
          </button>
        </div>

        {showCreate && (
          <CreateUserForm
            onDone={() => {
              setShowCreate(false)
              fetchUsers()
            }}
          />
        )}

        {editId && (
          <EditUserForm
            userId={editId}
            onDone={() => {
              setEditId(null)
              fetchUsers()
            }}
          />
        )}

        {loading ? (
          <div className="text-gray-400 text-center py-8">Loading...</div>
        ) : (
          <div className="space-y-3">
            {users.map((u) => (
              <div
                key={u.id}
                className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
                    style={{ backgroundColor: u.color_hex }}
                  >
                    {u.display_name[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-white font-medium">{u.display_name}</div>
                    <div className="text-gray-400 text-sm">
                      {u.role}{u.email ? ` · ${u.email}` : ''}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {u.id !== currentUser?.id && (
                    <button
                      onClick={() => handleDelete(u.id)}
                      className="text-red-400 hover:text-red-300 text-sm"
                    >
                      Delete
                    </button>
                  )}
                  <button
                    onClick={() => setEditId(u.id)}
                    className="text-gray-400 hover:text-white text-sm ml-2"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [color, setColor] = useState('#4F46E5')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await apiClient.post('/users/', {
        display_name: displayName,
        email: email || undefined,
        password: password || undefined,
        color_hex: color,
      })
      onDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create user'
      setError(msg)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4 space-y-3">
      {error && <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded text-sm">{error}</div>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm text-gray-300 mb-1">Display Name</label>
          <input
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Email</label>
          <input
            type="email"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Password</label>
          <input
            type="password"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Color</label>
          <input
            type="color"
            className="w-full h-9 bg-gray-800 border border-gray-700 rounded cursor-pointer"
            value={color}
            onChange={(e) => setColor(e.target.value)}
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onDone} className="text-gray-400 hover:text-white text-sm px-3 py-1">
          Cancel
        </button>
        <button type="submit" className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-1 rounded">
          Create
        </button>
      </div>
    </form>
  )
}

function EditUserForm({ userId, onDone }: { userId: string; onDone: () => void }) {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('')
  const [color, setColor] = useState('#4F46E5')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    apiClient.get(`/users/${userId}`).then((res) => {
      setDisplayName(res.data.display_name || '')
      setEmail(res.data.email || '')
      setRole(res.data.role || 'member')
      setColor(res.data.color_hex || '#4F46E5')
      setLoaded(true)
    })
  }, [userId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await apiClient.patch(`/users/${userId}`, {
        display_name: displayName || undefined,
        email: email || undefined,
        password: password || undefined,
        role: role || undefined,
        color_hex: color || undefined,
      })
      onDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update user'
      setError(msg)
    }
  }

  if (!loaded) return null

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4 space-y-3">
      {error && <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded text-sm">{error}</div>}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm text-gray-300 mb-1">Display Name</label>
          <input
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Email</label>
          <input
            type="email"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">New Password</label>
          <input
            type="password"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Role</label>
          <select
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="admin">Admin</option>
            <option value="member">Member</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-300 mb-1">Color</label>
          <input
            type="color"
            className="w-full h-9 bg-gray-800 border border-gray-700 rounded cursor-pointer"
            value={color}
            onChange={(e) => setColor(e.target.value)}
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onDone} className="text-gray-400 hover:text-white text-sm px-3 py-1">
          Cancel
        </button>
        <button type="submit" className="bg-primary hover:bg-primary-dark text-white text-sm px-4 py-1 rounded">
          Save
        </button>
      </div>
    </form>
  )
}
