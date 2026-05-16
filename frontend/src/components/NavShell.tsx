import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { apiClient } from '../api/client'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/dashboard', label: 'Home', icon: '🏠' },
  { to: '/calendar', label: 'Calendar', icon: '📅' },
  { to: '/lists', label: 'Lists', icon: '📋' },
]

export default function NavShell() {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const { clearUser } = useAuthStore()

  const isActive = (path: string) => location.pathname === path

  const adminItems = [
    { to: '/admin/users', label: 'Users' },
    { to: '/admin/calendars', label: 'Calendars' },
    { to: '/admin/settings', label: 'Settings' },
  ]

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // ignore logout errors
    }
    clearUser()
  }

  return (
    <div className="flex h-screen bg-gray-950">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 flex-col border-r border-slate-800 bg-slate-900/50 md:flex">
        <div className="flex items-center gap-2 border-b border-slate-800 px-5 py-4">
          <span className="text-xl font-bold text-white">OpenFamHub</span>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive(item.to)
                  ? 'bg-primary/10 text-primary'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white',
              )}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}

          {(user?.role === 'admin' || user?.role === 'co_admin') && (
            <>
              <div className="my-3 border-t border-slate-800" />
              <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-slate-600">
                Admin
              </p>
              {adminItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive(item.to)
                      ? 'bg-primary/10 text-primary'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-white',
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </>
          )}
        </nav>

        <div className="border-t border-slate-800 px-4 py-3">
          {user && (
            <div className="flex items-center gap-3">
              <span
                className="inline-block h-8 w-8 rounded-full"
                style={{ backgroundColor: user.color_hex || '#6366f1' }}
              />
              <div className="flex-1 truncate">
                <p className="text-sm font-medium text-white">{user.display_name}</p>
                <p className="text-xs text-slate-500">{user.role}</p>
              </div>
              <button
                onClick={handleLogout}
                className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-slate-800 bg-slate-900 px-2 py-2 md:hidden">
        {navItems.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              'flex flex-col items-center gap-0.5 rounded-lg px-3 py-1 text-xs transition-colors',
              isActive(item.to)
                ? 'text-primary'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </Link>
        ))}
        {(user?.role === 'admin' || user?.role === 'co_admin') && (
          <Link
            to="/admin/settings"
            className={cn(
              'flex flex-col items-center gap-0.5 rounded-lg px-3 py-1 text-xs transition-colors',
              isActive('/admin/settings')
                ? 'text-primary'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            <span className="text-lg">⚙️</span>
            Settings
          </Link>
        )}
      </nav>

      {/* Bottom padding for mobile nav */}
      <div className="h-16 md:hidden" />
    </div>
  )
}
