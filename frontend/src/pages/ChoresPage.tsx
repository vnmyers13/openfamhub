import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { choreAPI } from '../api/client'
import { useAuthStore } from '../stores/auth'

type Tab = 'my' | 'available' | 'history' | 'templates'

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

  const createMutation = useMutation({
    mutationFn: choreAPI.createTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-templates'] })
      setShowTemplateForm(false)
      setFormData({ title: '', description: '', assignment_mode: 'claimable', recurrence_rule: 'daily', point_value: 10 })
    },
  })

  const completeMutation = useMutation({
    mutationFn: choreAPI.completeInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
      queryClient.invalidateQueries({ queryKey: ['chores-completion-log'] })
      queryClient.invalidateQueries({ queryKey: ['chores-stats'] })
    },
  })

  const claimMutation = useMutation({
    mutationFn: choreAPI.claimInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
    },
  })

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
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Chores</h1>

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
                    <div className="font-medium">{instance.due_date}</div>
                    <div className="text-sm text-gray-400">
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
                    <div className="font-medium">Due: {instance.due_date}</div>
                    <div className="text-sm text-gray-400">Click to claim</div>
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
      </div>
    </div>
  )
}
