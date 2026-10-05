import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { apiClient } from './api/client'
import { useAuthStore } from './stores/auth'
import SetupWizard from './pages/SetupWizard'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ManageUsers from './pages/ManageUsers'
import CalendarPage from './pages/CalendarPage'
import CalendarSettings from './pages/admin/CalendarSettings'
import WallDisplays from './pages/admin/WallDisplays'
import NavShell from './components/NavShell'
import WallLayout from './wall/WallLayout'

// Paths an authenticated user should be moved off of after boot.
const ENTRY_PATHS = new Set(['/', '/login', '/setup'])

function AppRoutes() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setUser } = useAuthStore()
  // The wall display authenticates with its own device cookie (see WallLayout).
  const [booting, setBooting] = useState(() => !window.location.pathname.startsWith('/wall'))

  useEffect(() => {
    // Read the path at mount time only; later navigation is the user's.
    const path = window.location.pathname
    let cancelled = false

    if (path.startsWith('/wall')) return

    async function boot() {
      try {
        const status = await apiClient.get('/auth/setup/status')
        if (!status.data.setup_complete) {
          navigate('/setup', { replace: true })
          return
        }
        try {
          const me = await apiClient.get('/auth/me')
          if (cancelled) return
          setUser(me.data)
          if (ENTRY_PATHS.has(path)) navigate('/dashboard', { replace: true })
        } catch {
          if (!cancelled && path !== '/login') navigate('/login', { replace: true })
        }
      } catch {
        if (!cancelled && path !== '/login') navigate('/login', { replace: true })
      } finally {
        if (!cancelled) setBooting(false)
      }
    }

    boot()
    return () => {
      cancelled = true
    }
  }, [navigate, setUser])

  if (booting && !ENTRY_PATHS.has(location.pathname)) {
    return <div className="min-h-screen bg-gray-950" />
  }

  return (
    <Routes>
      <Route path="/setup" element={<SetupWizard />} />
      <Route path="/login" element={<Login />} />
      <Route path="/wall" element={<WallLayout />} />
      <Route element={<NavShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/admin/users" element={<ManageUsers />} />
        <Route path="/admin/calendars" element={<CalendarSettings />} />
        <Route path="/admin/wall" element={<WallDisplays />} />
        <Route path="/admin/settings" element={<Dashboard />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
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
