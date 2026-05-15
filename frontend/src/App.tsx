import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from './api/client'
import { useAuthStore } from './stores/auth'

function AppRoutes() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()

  useEffect(() => {
    apiClient.get('/auth/setup/status').then((res) => {
      if (!res.data.setup_complete) {
        navigate('/setup')
        return
      }
      apiClient.get('/auth/me').then((res) => {
        setUser(res.data.user)
        navigate('/dashboard')
      }).catch(() => {
        navigate('/login')
      })
    }).catch(() => {
      navigate('/login')
    })
  }, [])

  return (
    <Routes>
      <Route path="/setup" element={<div>Setup Wizard</div>} />
      <Route path="/login" element={<div>Login</div>} />
      <Route path="/dashboard" element={<div>Dashboard</div>} />
      <Route path="/calendar" element={<div>Calendar</div>} />
      <Route path="/wall" element={<div>Wall Display</div>} />
      <Route path="/admin/users" element={<div>Manage Users</div>} />
      <Route path="/admin/calendars" element={<div>Calendar Settings</div>} />
      <Route path="/admin/settings" element={<div>Admin Settings</div>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
