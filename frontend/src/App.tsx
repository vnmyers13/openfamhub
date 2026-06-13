import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import SetupWizard from './pages/SetupWizard'
import Dashboard from './pages/Dashboard'
import DashboardHome from './pages/DashboardHome'
import CalendarPage from './pages/CalendarPage'
import WallDisplay from './pages/WallDisplay'
import ManageUsers from './pages/ManageUsers'
import AnnouncementsPage from './pages/AnnouncementsPage'
import RewardsPage from './pages/RewardsPage'
import ChoresPage from './pages/ChoresPage'
import MealsPage from './pages/MealsPage'
import BooksPage from './pages/BooksPage'
import { useAuthStore } from './stores/auth'
import { useSyncOnVisible } from './hooks/useSyncOnVisible'
import { OfflineBanner } from './components/OfflineBanner'
import { ConflictModal } from './components/ConflictModal'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  const token = useAuthStore((s) => s.token)
  useSyncOnVisible()

  return (
    <>
      <OfflineBanner />
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/setup" element={<SetupWizard />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardHome />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="chores" element={<ChoresPage />} />
        <Route path="meals" element={<MealsPage />} />
        <Route path="rewards" element={<RewardsPage />} />
        <Route path="books" element={<BooksPage />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
        <Route path="manage-users" element={<ManageUsers />} />
      </Route>
      <Route
        path="/wall"
        element={
          <ProtectedRoute>
            <WallDisplay />
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={
          token ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />
        }
      />
    </Routes>
      <ConflictModal />
    </>
  )
}

export default App
