import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { apiClient } from './api/client'
import { useAuthStore } from './stores/auth'
import Login from './pages/Login'
import NavShell from './components/NavShell'
import RequireAdmin from './components/RequireAdmin'
import PasswordPrompt from './components/PasswordPrompt'

// Route-level code splitting: each page (and react-big-calendar with the
// calendar) loads on first visit, so the sign-in screen and the wall don't
// download everything. Login stays in the main bundle; it's the first screen.
const SetupWizard = lazy(() => import('./pages/SetupWizard'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ManageUsers = lazy(() => import('./pages/ManageUsers'))
const CalendarPage = lazy(() => import('./pages/CalendarPage'))
const CalendarSettings = lazy(() => import('./pages/admin/CalendarSettings'))
const WallDisplays = lazy(() => import('./pages/admin/WallDisplays'))
const WallLayout = lazy(() => import('./wall/WallLayout'))
const PhotosPage = lazy(() => import('./pages/PhotosPage'))
const ChoresPage = lazy(() => import('./pages/chores/ChoresPage'))
const RewardsPage = lazy(() => import('./pages/rewards/RewardsPage'))
const FamilySettings = lazy(() => import('./pages/admin/FamilySettings'))

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
    <Suspense fallback={<div className="min-h-screen bg-gray-950" />}>
      <Routes>
        <Route path="/setup" element={<SetupWizard />} />
        <Route path="/login" element={<Login />} />
        <Route path="/wall" element={<WallLayout />} />
        <Route element={<NavShell />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/chores" element={<ChoresPage />} />
          <Route path="/rewards" element={<RewardsPage />} />
          <Route path="/photos" element={<PhotosPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="/admin/users" element={<ManageUsers />} />
            <Route path="/admin/calendars" element={<CalendarSettings />} />
            <Route path="/admin/wall" element={<WallDisplays />} />
            <Route path="/admin/settings" element={<FamilySettings />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
      <PasswordPrompt />
    </BrowserRouter>
  )
}
