import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { choreAPI } from '../api/client'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useNavigate } from 'react-router-dom'
import { FaArrowLeft } from 'react-icons/fa'
import { enqueueOperation } from '../lib/idb'
import { useOfflineStore } from '../lib/offline-state'

type Tab = 'my' | 'available' | 'history' | 'templates' | 'admin'

interface ChoreTemplate {
  id: string
  title: string
  description?: string
  assignment_mode: string
  recurrence_rule: string
  point_value: number
  is_active: boolean
  created_by_id: string
  created_at: string
  updated_at: string
}

interface ChoreInstance {
  id: string
  chore_template_id: string
  assigned_to_id?: string
  due_date: string
  status: string
  claimed_by_id?: string
  claimed_at?: string
  completed_by_id?: string
  completed_at?: string
  created_at: string
}

interface CompletionLog {
  id: string
  instance_id: string
  completed_by_id: string
  completed_at: string
  points_earned: number
}



export default function ChoresPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('my')
  const [showTemplateForm, setShowTemplateForm] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    assignment_mode: 'claimable' as 'assigned' | 'claimable',
    recurrence_rule: 'daily',
    point_value: 10,
  })

  const { data: templates } = useQuery({
    queryKey: ['chores-templates'],
    queryFn: choreAPI.getTemplates,
  })

  const templateMap: Record<string, string> = {}
  templates?.forEach((t: ChoreTemplate) => {
    templateMap[t.id] = t.title
  })

  const { data: instances, refetch: _refetchInstances } = useQuery({
    queryKey: ['chores-instances'],
    queryFn: () => choreAPI.getInstances(),
    refetchInterval: 30000,
  })

  const { data: completionLog } = useQuery({
    queryKey: ['chores-completion-log'],
    queryFn: () => choreAPI.getCompletionLog(50),
  })

  const { data: stats } = useQuery({
    queryKey: ['chores-stats'],
    queryFn: choreAPI.getStats,
  })

  const [statusFilter, setStatusFilter] = useState<string>("")
  const [startDate, setStartDate] = useState<string>("")
  const [endDate, setEndDate] = useState<string>("")
  const [sortColumn, setSortColumn] = useState<string>("due_date")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")

  interface AdminChoreItem {
    id: string
    title: string
    assigned_to_name: string
    assigned_to_id: string
    status: string
    due_date: string
    completed_at?: string
    points_awarded: number
  }

  interface AdminChoreResponse {
    items: AdminChoreItem[]
    total: number
    page: number
    page_size: number
  }

  const { data: adminData, isLoading: adminLoading } = useQuery<AdminChoreResponse>({
    queryKey: ['admin-chores', statusFilter, startDate, endDate],
    queryFn: () => choreAPI.getAdminInstances({
      status_filter: statusFilter || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    }),
  })

  const createMutation = useMutation({
    mutationFn: choreAPI.createTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-templates'] })
      setShowTemplateForm(false)
      setFormData({ title: '', description: '', assignment_mode: 'claimable', recurrence_rule: 'daily', point_value: 10 })
    },
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => {
      if (!navigator.onLine) {
        enqueueOperation({
          type: 'update',
          entity: 'chore-instance',
          data: { id },
          endpoint: '/chores/instances',
        })
        useOfflineStore.getState().incrementPending()
      }
      return choreAPI.completeInstance(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
      queryClient.invalidateQueries({ queryKey: ['chores-completion-log'] })
      queryClient.invalidateQueries({ queryKey: ['chores-stats'] })
    },
  })

  const claimMutation = useMutation({
    mutationFn: (id: string) => {
      if (!navigator.onLine) {
        enqueueOperation({
          type: 'update',
          entity: 'chore-instance',
          data: { id },
          endpoint: '/chores/instances',
        })
        useOfflineStore.getState().incrementPending()
      }
      return choreAPI.claimInstance(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
    },
  })

  const [showQuickAddModal, setShowQuickAddModal] = useState(false)
  const [quickAddForm, setQuickAddForm] = useState({
    title: '',
    description: '',
    point_value: 10,
    assigned_to_id: '',
    recurrence_rule: 'none',
  })
  const [quickAddError, setQuickAddError] = useState('')

  const { data: profiles } = useQuery({
    queryKey: ['users-profiles'],
    queryFn: () => api.get('/users/profiles').then((r: any) => r.data),
  })

  const quickAddMutation = useMutation({
    mutationFn: choreAPI.quickAdd,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
      queryClient.invalidateQueries({ queryKey: ['chores-stats'] })
      setShowQuickAddModal(false)
      setQuickAddForm({ title: '', description: '', point_value: 10, assigned_to_id: '', recurrence_rule: 'none' })
      setQuickAddError('')
    },
    onError: (err: any) => {
      const message = err.response?.data?.detail || 'Failed to add chore'
      setQuickAddError(message)
    },
  })

  const handleQuickAdd = (e: React.FormEvent) => {
    e.preventDefault()
    setQuickAddError('')
    if (!quickAddForm.title.trim()) {
      setQuickAddError('Title is required')
      return
    }
    if (!quickAddForm.assigned_to_id) {
      setQuickAddError('Please select a user')
      return
    }
    quickAddMutation.mutate(quickAddForm)
  }

  const isAdmin = user?.role === 'admin'

  const myInstances = instances?.filter((i: ChoreInstance) =>
    i.assigned_to_id === user?.id || i.claimed_by_id === user?.id
  ) || []

  const availableInstances = instances?.filter((i: ChoreInstance) => i.status === 'pending') || []

  const handleComplete = (id: string) => {
    completeMutation.mutate(id)
  }

  const handleClaim = (id: string) => {
    claimMutation.mutate(id)
  }

  const handleCreateTemplate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const tabs: { key: Tab; label: string; adminOnly?: boolean }[] = [
    { key: 'my', label: 'My Chores' },
    { key: 'available', label: 'Available' },
    { key: 'history', label: 'History' },
    { key: 'templates', label: 'Templates', adminOnly: true },
    { key: 'admin', label: 'Admin', adminOnly: true },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition"
          >
            <FaArrowLeft />
            <span>Dashboard</span>
          </button>
          <div className="flex-1" />
          <h1 className="text-2xl font-bold">Chores</h1>
          <button
            onClick={() => setShowQuickAddModal(true)}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
          >
            Quick Add
          </button>
        </div>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.total_completed}</div>
              <div className="text-gray-400 text-sm">Completed</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.current_streak}</div>
              <div className="text-gray-400 text-sm">Day Streak</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.points_earned}</div>
              <div className="text-gray-400 text-sm">Points</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold">{stats.longest_streak}</div>
              <div className="text-gray-400 text-sm">Longest Streak</div>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-gray-700">
          {tabs.filter(t => !t.adminOnly).map(tab => (
            <button
              key={tab.key}
              className={`px-4 py-2 ${activeTab === tab.key ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
          {isAdmin && (
            <button
              className={`px-4 py-2 ${activeTab === 'templates' ? 'bg-blue-600 rounded-t-lg' : 'text-gray-400 hover:text-white'}`}
              onClick={() => setActiveTab('templates')}
            >
              Templates
            </button>
          )}
        </div>

        {activeTab === 'my' && (
          <div className="space-y-3">
            {myInstances.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No chores assigned to you</p>
            ) : (
              myInstances.map((instance: ChoreInstance) => (
                <div key={instance.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                  <div>
                    <div className="font-medium">{templateMap[instance.chore_template_id] || 'Unknown Chore'}</div>
                    <div className="text-sm text-gray-400">Due: {instance.due_date}</div>
                    <div className="text-xs text-gray-500">
                      {instance.status === 'claimed' ? 'Claimed by you' : 'Assigned to you'}
                    </div>
                  </div>
                  {instance.status === 'claimed' && (
                    <button
                      onClick={() => handleComplete(instance.id)}
                      className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg"
                    >
                      Complete
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'available' && (
          <div className="space-y-3">
            {availableInstances.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No available chores</p>
            ) : (
              availableInstances.map((instance: ChoreInstance) => (
                <div key={instance.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
                  <div>
                    <div className="font-medium">{templateMap[instance.chore_template_id] || 'Unknown Chore'}</div>
                    <div className="text-sm text-gray-400">Due: {instance.due_date}</div>
                    <div className="text-xs text-gray-500">Click to claim</div>
                  </div>
                  <button
                    onClick={() => handleClaim(instance.id)}
                    className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
                  >
                    Claim
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-2">
            {completionLog?.map((log: CompletionLog) => (
              <div key={log.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                <div>
                  <span className="text-gray-400">{new Date(log.completed_at).toLocaleDateString()}</span>
                  <span className="ml-4 text-sm">+{log.points_earned} points</span>
                </div>
              </div>
            )) || <p className="text-gray-400 text-center py-8">No completion history</p>}
          </div>
        )}

        {activeTab === 'templates' && isAdmin && (
          <div className="space-y-4">
            <button
              onClick={() => setShowTemplateForm(!showTemplateForm)}
              className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
            >
              {showTemplateForm ? 'Cancel' : 'Add Template'}
            </button>

            {showTemplateForm && (
              <form onSubmit={handleCreateTemplate} className="bg-gray-800 rounded-lg p-4 space-y-3">
                <input
                  type="text"
                  placeholder="Title"
                  value={formData.title}
                  onChange={e => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  required
                />
                <textarea
                  placeholder="Description"
                  value={formData.description || ''}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                />
                <select
                  value={formData.assignment_mode}
                  onChange={e => setFormData({ ...formData, assignment_mode: e.target.value as 'assigned' | 'claimable' })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                >
                  <option value="assigned">Assigned (admin assigns)</option>
                  <option value="claimable">Claimable (self-assign)</option>
                </select>
                <select
                  value={formData.recurrence_rule}
                  onChange={e => setFormData({ ...formData, recurrence_rule: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly_mon">Weekly - Monday</option>
                  <option value="weekly_tue">Weekly - Tuesday</option>
                  <option value="weekly_wed">Weekly - Wednesday</option>
                  <option value="weekly_thu">Weekly - Thursday</option>
                  <option value="weekly_fri">Weekly - Friday</option>
                  <option value="weekly_sat">Weekly - Saturday</option>
                  <option value="weekly_sun">Weekly - Sunday</option>
                  <option value="monthly_1st">Monthly - 1st</option>
                  <option value="monthly_15th">Monthly - 15th</option>
                  <option value="every_3_days_3">Every 3 Days</option>
                  <option value="every_7_days_7">Every 7 Days</option>
                </select>
                <input
                  type="number"
                  placeholder="Point value"
                  value={formData.point_value}
                  onChange={e => setFormData({ ...formData, point_value: parseInt(e.target.value) || 10 })}
                  className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600"
                  min="1"
                  max="1000"
                />
                <button type="submit" className="w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                  Create Template
                </button>
              </form>
            )}

            <div className="space-y-2">
              {templates?.map((template: ChoreTemplate) => (
                <div key={template.id} className="bg-gray-800 rounded-lg p-3 flex justify-between items-center">
                  <div>
                    <div className="font-medium">{template.title}</div>
                    <div className="text-sm text-gray-400">
                      {template.assignment_mode} · {template.recurrence_rule} · {template.point_value} pts
                    </div>
                  </div>
                  <div className="text-sm text-gray-500">{template.is_active ? 'Active' : 'Inactive'}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'admin' && isAdmin && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3 items-end bg-gray-800 rounded-lg p-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Status</label>
                <select
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="">All</option>
                  <option value="pending">Pending</option>
                  <option value="claimed">Claimed</option>
                  <option value="completed">Completed</option>
                  <option value="expired">Expired</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">From</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">To</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={e => setEndDate(e.target.value)}
                  className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
            </div>

            {adminLoading ? (
              <p className="text-gray-400 text-center py-8">Loading...</p>
            ) : !adminData?.items || adminData.items.length === 0 ? (
              <p className="text-gray-400 text-center py-8">No chores found</p>
            ) : (
              <div className="bg-gray-800 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th
                        className="px-4 py-2 text-left cursor-pointer hover:text-gray-300"
                        onClick={() => {
                          if (sortColumn === 'title') setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
                          else { setSortColumn('title'); setSortDirection('asc') }
                        }}
                      >
                        Title {sortColumn === 'title' ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
                      </th>
                      <th
                        className="px-4 py-2 text-left cursor-pointer hover:text-gray-300"
                        onClick={() => {
                          if (sortColumn === 'assigned_to_name') setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
                          else { setSortColumn('assigned_to_name'); setSortDirection('asc') }
                        }}
                      >
                        Assigned To {sortColumn === 'assigned_to_name' ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
                      </th>
                      <th className="px-4 py-2 text-left">Status</th>
                      <th
                        className="px-4 py-2 text-left cursor-pointer hover:text-gray-300"
                        onClick={() => {
                          if (sortColumn === 'due_date') setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
                          else { setSortColumn('due_date'); setSortDirection('asc') }
                        }}
                      >
                        Due Date {sortColumn === 'due_date' ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
                      </th>
                      <th className="px-4 py-2 text-left">Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...(adminData.items)]
                      .sort((a, b) => {
                        let aVal: string, bVal: string
                        if (sortColumn === 'title') { aVal = a.title; bVal = b.title }
                        else if (sortColumn === 'assigned_to_name') { aVal = a.assigned_to_name; bVal = b.assigned_to_name }
                        else { aVal = a.due_date; bVal = b.due_date }
                        if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
                        if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
                        return 0
                      })
                      .map((item: any) => {
                        const statusColors: Record<string, string> = {
                          pending: 'bg-blue-100 text-blue-800',
                          claimed: 'bg-yellow-100 text-yellow-800',
                          completed: 'bg-green-100 text-green-800',
                          expired: 'bg-red-100 text-red-800',
                        }
                        return (
                          <tr key={item.id} className="border-b border-gray-700">
                            <td className="px-4 py-2 font-medium">{item.title}</td>
                            <td className="px-4 py-2 text-gray-400">{item.assigned_to_name}</td>
                            <td className="px-4 py-2">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${statusColors[item.status] || 'bg-gray-100 text-gray-800'}`}>
                                {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-gray-400">{new Date(item.due_date).toLocaleDateString()}</td>
                            <td className="px-4 py-2 text-gray-400">{item.completed_at ? new Date(item.completed_at).toLocaleDateString() : '-'}</td>
                          </tr>
                        )
                      })
                    }
                  </tbody>
                </table>
              </div>
            )}

            {adminData && adminData.total > 0 && (
              <p className="text-xs text-gray-500 text-right">
                Showing {adminData.items?.length || 0} of {adminData.total} total
              </p>
            )}
          </div>
        )}

        {showQuickAddModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowQuickAddModal(false)}>
            <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
              <h2 className="text-xl font-bold mb-4">Add Chore</h2>
              {quickAddError && (
                <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded-lg mb-4">
                  {quickAddError}
                </div>
              )}
              <form onSubmit={handleQuickAdd} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Title *</label>
                  <input
                    type="text"
                    value={quickAddForm.title}
                    onChange={e => setQuickAddForm(f => ({ ...f, title: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    placeholder="e.g., Take out trash"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    value={quickAddForm.description}
                    onChange={e => setQuickAddForm(f => ({ ...f, description: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    placeholder="Optional description"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Assign to *</label>
                  <select
                    value={quickAddForm.assigned_to_id}
                    onChange={e => setQuickAddForm(f => ({ ...f, assigned_to_id: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">Select a user</option>
                    {profiles?.map((p: { id: string; name: string; avatar_emoji: string }) => (
                      <option key={p.id} value={p.id}>
                        {p.avatar_emoji} {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Point Value</label>
                  <input
                    type="number"
                    value={quickAddForm.point_value}
                    onChange={e => setQuickAddForm(f => ({ ...f, point_value: parseInt(e.target.value) || 10 }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    min={1}
                    max={1000}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Recurrence (optional)</label>
                  <select
                    value={quickAddForm.recurrence_rule}
                    onChange={e => setQuickAddForm(f => ({ ...f, recurrence_rule: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="none">None (one-time)</option>
                    <option value="daily">Daily</option>
                    <option value="weekly_mon">Weekly - Monday</option>
                    <option value="weekly_tue">Weekly - Tuesday</option>
                    <option value="weekly_wed">Weekly - Wednesday</option>
                    <option value="weekly_thu">Weekly - Thursday</option>
                    <option value="weekly_fri">Weekly - Friday</option>
                    <option value="weekly_sat">Weekly - Saturday</option>
                    <option value="weekly_sun">Weekly - Sunday</option>
                    <option value="every_2_days">Every 2 Days</option>
                    <option value="every_3_days">Every 3 Days</option>
                    <option value="every_5_days">Every 5 Days</option>
                    <option value="monthly_1">Monthly - 1st</option>
                    <option value="monthly_15">Monthly - 15th</option>
                    <option value="monthly_28">Monthly - 28th</option>
                  </select>
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    type="submit"
                    disabled={quickAddMutation.isPending}
                    className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded-lg"
                  >
                    {quickAddMutation.isPending ? 'Adding...' : 'Add Chore'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowQuickAddModal(false); setQuickAddError('') }}
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
