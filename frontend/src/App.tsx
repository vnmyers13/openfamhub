import { Routes, Route } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import CalendarPage from './pages/CalendarPage'
import WallDisplay from './pages/WallDisplay'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/calendar" element={<CalendarPage />} />
      <Route path="/wall" element={<WallDisplay />} />
      <Route path="*" element={<Dashboard />} />
    </Routes>
  )
}

export default App
