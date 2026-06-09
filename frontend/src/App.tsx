import { Routes, Route } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import DashboardHome from './pages/DashboardHome'
import CalendarPage from './pages/CalendarPage'
import WallDisplay from './pages/WallDisplay'
import ManageUsers from './pages/ManageUsers'
import AnnouncementsPage from './pages/AnnouncementsPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />}>
        <Route index element={<DashboardHome />} />
        <Route path="manage-users" element={<ManageUsers />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
      </Route>
      <Route path="/calendar" element={<CalendarPage />} />
      <Route path="/wall" element={<WallDisplay />} />
      <Route path="*" element={<DashboardHome />} />
    </Routes>
  )
}

export default App
