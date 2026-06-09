import { useState, useEffect } from 'react'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

interface User {
  id: string
  name: string
  avatar_emoji: string
  role: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export default function ManageUsers() {
  const [users, setUsers] = useState<User[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    avatar_emoji: '👤',
    pin: '',
    role: 'member',
  })
  const [error, setError] = useState('')
  const currentUser = useAuthStore((s) => s.user)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const res = await api.get('/users/profiles')
      setUsers(res.data)
    } catch (err) {
      setError('Failed to load users')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (editingUser) {
        const updateData: any = { ...formData }
        if (!updateData.pin) delete updateData.pin
        await api.patch(`/users/profiles/${editingUser.id}`, updateData)
      } else {
        await api.post('/users/profiles', formData)
      }
      setShowForm(false)
      setEditingUser(null)
      setFormData({ name: '', avatar_emoji: '👤', pin: '', role: 'member' })
      fetchUsers()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save user')
    }
  }

  const handleEdit = (user: User) => {
    setEditingUser(user)
    setFormData({
      name: user.name,
      avatar_emoji: user.avatar_emoji,
      pin: '',
      role: user.role,
    })
    setShowForm(true)
  }

  const handleDeactivate = async (userId: string) => {
    if (!confirm('Deactivate this profile?')) return
    try {
      await api.delete(`/users/profiles/${userId}`)
      fetchUsers()
    } catch (err) {
      setError('Failed to deactivate user')
    }
  }

  const handleCancel = () => {
    setShowForm(false)
    setEditingUser(null)
    setFormData({ name: '', avatar_emoji: '👤', pin: '', role: 'member' })
  }

  if (currentUser?.role !== 'admin') {
    return <div className="text-center py-8">Admin access required</div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Manage Profiles</h2>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white"
        >
          Add Profile
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
          {error}
        </div>
      )}

      {showForm && (
        <div className="mb-6 p-6 rounded-xl bg-[#16213e] border border-white/10">
          <h3 className="text-xl font-bold mb-4">
            {editingUser ? 'Edit Profile' : 'New Profile'}
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Avatar Emoji</label>
              <input
                type="text"
                value={formData.avatar_emoji}
                onChange={(e) => setFormData({ ...formData, avatar_emoji: e.target.value })}
                className="w-20 p-3 rounded-lg bg-white/5 border border-white/20 text-center text-2xl focus:border-white/50 focus:outline-none"
                maxLength={2}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                PIN {editingUser ? '(leave blank to keep current)' : ''}
              </label>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                value={formData.pin}
                onChange={(e) => setFormData({ ...formData, pin: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                className="w-32 p-3 rounded-lg bg-white/5 border border-white/20 text-center tracking-[0.5em] focus:border-white/50 focus:outline-none"
                placeholder="****"
                required={!editingUser}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Role</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none"
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-500">
                {editingUser ? 'Update' : 'Create'}
              </button>
              <button type="button" onClick={handleCancel} className="px-6 py-2 rounded-lg bg-white/5 hover:bg-white/10">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="space-y-3">
        {users.map((user) => (
          <div
            key={user.id}
            className={`flex items-center justify-between p-4 rounded-xl border ${
              user.is_active ? 'bg-[#16213e] border-white/10' : 'bg-white/5 border-white/5 opacity-50'
            }`}
          >
            <div className="flex items-center gap-4">
              <span className="text-3xl">{user.avatar_emoji}</span>
              <div>
                <p className="font-semibold text-lg">{user.name}</p>
                <p className="text-sm text-gray-400">
                  {user.role} {user.last_login_at && `· Last: ${new Date(user.last_login_at).toLocaleDateString()}`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleEdit(user)}
                className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-sm"
              >
                Edit
              </button>
              {user.is_active && (
                <button
                  onClick={() => handleDeactivate(user.id)}
                  className="px-3 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm"
                >
                  Deactivate
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
