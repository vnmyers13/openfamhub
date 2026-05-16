import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from './api/client'
import { useAuthStore } from './stores/auth'
import SetupWizard from './pages/SetupWizard'
import Login from './pages/Login'
import ManageUsers from './pages/ManageUsers'

function AppRoutes() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()

  useEffect(() => {
    apiClient.get('/auth/setup/status').then((res) => {
      if (!res.data.setup_complete) {
        navigate('/setup', { replace: true })
        return
      }
      apiClient.get('/auth/me').then((res) => {
        setUser(res.data)
        navigate('/dashboard', { replace: true })
      }).catch(() => {
        navigate('/login', { replace: true })
      })
    }).catch(() => {
      navigate('/login', { replace: true })
    })
  }, [])

  return (
    <Routes>
      <Route path="/setup" element={<SetupWizard />} />
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Dashboard</div>} />
      <Route path="/calendar" element={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Calendar</div>} />
      <Route path="/wall" element={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Wall Display</div>} />
      <Route path="/admin/users" element={<ManageUsers />} />
      <Route path="/admin/calendars" element={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Calendar Settings</div>} />
      <Route path="/admin/settings" element={<div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Admin Settings</div>} />
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
