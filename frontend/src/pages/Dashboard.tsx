import { useAuthStore } from '../stores/auth'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { FaCalendarAlt, FaHome, FaSignOutAlt, FaUsers, FaBullhorn, FaTasks, FaGift, FaUtensils, FaBook } from 'react-icons/fa'

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/dashboard', label: 'Home', icon: <FaHome /> },
    { path: '/dashboard/calendar', label: 'Calendar', icon: <FaCalendarAlt /> },
    { path: '/dashboard/chores', label: 'Chores', icon: <FaTasks /> },
    { path: '/dashboard/meals', label: 'Meals', icon: <FaUtensils /> },
    { path: '/dashboard/rewards', label: 'Rewards', icon: <FaGift /> },
    { path: '/dashboard/books', label: 'Books', icon: <FaBook /> },
    { path: '/dashboard/announcements', label: 'Announcements', icon: <FaBullhorn /> },
    ...(user?.role === 'admin' ? [{ path: '/dashboard/manage-users', label: 'Manage Users', icon: <FaUsers /> }] : []),
  ]

  return (
    <div className="min-h-screen bg-[#1a1a2e]">
      <nav className="bg-[#16213e] border-b border-white/10 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="text-xl font-bold">OpenFamHub</h1>
          <div className="flex gap-2">
            {navItems.map((item) => (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                  location.pathname === item.path
                    ? 'bg-white/10 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                {item.icon}
                <span className="hidden sm:inline">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{user?.avatar_emoji || ''}</span>
            <span className="hidden sm:inline">{user?.name || 'User'}</span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-white/5 transition"
          >
            <FaSignOutAlt />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </nav>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}
