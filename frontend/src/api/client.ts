import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default api

export const rewardAPI = {
  getPointsBalance: () => api.get('/rewards/points/balance').then(r => r.data),
  getPointsLedger: (limit = 50) => api.get('/rewards/points/ledger', { params: { limit } }).then(r => r.data),

  getAllowanceBalance: () => api.get('/rewards/allowance/balance').then(r => r.data),
  getAllowanceLedger: (limit = 50) => api.get('/rewards/allowance/ledger', { params: { limit } }).then(r => r.data),

  getCatalog: () => api.get('/rewards/catalog').then(r => r.data),
  getRewardDetail: (id: string) => api.get(`/rewards/catalog/${id}`).then(r => r.data),
  createReward: (data: { name: string; description?: string; point_cost: number; is_auto_fulfill: boolean }) =>
    api.post('/rewards/catalog', data).then(r => r.data),
  updateReward: (id: string, data: Partial<{ name: string; description?: string; point_cost: number; is_auto_fulfill: boolean; is_active: boolean }>) =>
    api.patch(`/rewards/catalog/${id}`, data).then(r => r.data),
  deactivateReward: (id: string) =>
    api.delete(`/rewards/catalog/${id}`).then(r => r.data),

  purchaseReward: (id: string) => api.post(`/rewards/purchase/${id}`).then(r => r.data),
  requestReward: (id: string) => api.post(`/rewards/request/${id}`).then(r => r.data),
  getMyRequests: () => api.get('/rewards/my-requests').then(r => r.data),
  getAllRequests: (statusFilter?: string) =>
    api.get('/rewards/admin/requests', { params: { status_filter: statusFilter } }).then(r => r.data),
  approveRequest: (id: string) => api.put(`/rewards/requests/${id}/approve`).then(r => r.data),
  rejectRequest: (id: string, reason?: string) =>
    api.put(`/rewards/requests/${id}/reject`, { reason }).then(r => r.data),

  getStreak: () => api.get('/rewards/streak').then(r => r.data),
  updateStreak: () => api.post('/rewards/streak/update').then(r => r.data),
  getBadges: () => api.get('/rewards/badges').then(r => r.data),

  getBadgeDefinitions: () => api.get('/rewards/badge-definitions').then(r => r.data),
  createBadgeDefinition: (data: { name: string; description?: string; icon?: string; trigger_type: string; trigger_value: number; points_reward: number }) =>
    api.post('/rewards/badge-definitions', data).then(r => r.data),
  updateBadgeDefinition: (id: string, data: Partial<{ name: string; description?: string; icon?: string; trigger_type: string; trigger_value: number; points_reward: number }>) =>
    api.patch(`/rewards/badge-definitions/${id}`, data).then(r => r.data),
  deleteBadgeDefinition: (id: string) =>
    api.delete(`/rewards/badge-definitions/${id}`).then(r => r.data),
}

export const choreAPI = {
  getTemplates: () => api.get('/chores/templates').then(r => r.data),
  createTemplate: (data: { title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number }) =>
    api.post('/chores/templates', data).then(r => r.data),
  updateTemplate: (id: string, data: Partial<{ title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number; is_active: boolean }>) =>
    api.patch(`/chores/templates/${id}`, data).then(r => r.data),
  deactivateTemplate: (id: string) =>
    api.delete(`/chores/templates/${id}`).then(r => r.data),

  getInstances: (statusFilter?: string, dueDate?: string) =>
    api.get('/chores/instances', { params: { status_filter: statusFilter, due_date: dueDate } }).then(r => r.data),
  claimInstance: (id: string) =>
    api.post(`/chores/instances/${id}/claim`).then(r => r.data),
  completeInstance: (id: string) =>
    api.post(`/chores/instances/${id}/complete`).then(r => r.data),

  getCompletionLog: (limit = 50) =>
    api.get('/chores/completion-log', { params: { limit } }).then(r => r.data),

  getStats: () =>
    api.get('/chores/stats').then(r => r.data),

  quickAdd: (data: { title: string; description?: string; point_value: number; assigned_to_id: string; recurrence_rule: string }) =>
    api.post('/chores/quick-add', data).then(r => r.data),
};
