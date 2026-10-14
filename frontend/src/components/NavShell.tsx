import { Suspense, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { apiClient, requestPasswordPrompt } from '../api/client'
import { DEFAULT_PREFS, usePreferences } from '../api/prefs'
import Avatar from './Avatar'
import { cn } from '../lib/utils'
import BuildInfoBadge from './BuildInfoBadge'

const navItems = [
  { to: '/dashboard', label: 'Home', icon: '🏠' },
  { to: '/calendar', label: 'Calendar', icon: '📅' },
  { to: '/chores', label: 'Chores', icon: '✅' },
  { to: '/rewards', label: 'Rewards', icon: '⭐' },
  { to: '/meals', label: 'Meals', icon: '🍽️' },
  { to: '/books', label: 'Books', icon: '📚' },
  { to: '/photos', label: 'Photos', icon: '🖼️' },
]

const adminItems = [
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/calendars', label: 'Calendars' },
  { to: '/admin/wall', label: 'Wall displays' },
  { to: '/admin/settings', label: 'Settings' },
]

// Phones show this many items in the bottom bar; the rest go under "More".
const MOBILE_ITEMS = 4

/**
 * The app frame. On wider screens the menu runs down the side or across the
 * top, as each person chooses in My settings (saved on the server, so it
 * follows them). Phones always get the bottom bar.
 */
export default function NavShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { clearUser } = useAuthStore()
  const { data: prefs = DEFAULT_PREFS } = usePreferences()
  const [moreOpen, setMoreOpen] = useState(false)
  const isActive = (path: string) => location.pathname === path
  const isAdmin = user?.role === 'admin'
  const top = prefs.nav === 'top'

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // ignore logout errors
    }
    clearUser()
    navigate('/login', { replace: true })
  }

  const linkClass = (to: string, extra = '') => cn(
    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive(to) ? 'bg-primary/10 text-primary' : 'text-slate-400 hover:bg-slate-800 hover:text-white', extra,
  )

  const unlock = isAdmin && !user?.admin_unlocked ? (
    <button onClick={() => requestPasswordPrompt().catch(() => {})} className="text-xs text-amber-400 hover:text-amber-300"
      title="Signed in with a PIN: confirm your password to change settings">🔒 Unlock admin</button>
  ) : null

  const userBox = user && (
    <div className="flex items-center gap-3">
      <Link to="/me" title="My settings" aria-label="My settings">
        <Avatar name={user.display_name} color={user.color_hex} emoji={user.avatar_value} className="h-8 w-8 text-base" />
      </Link>
      <div className={cn('truncate', top ? '' : 'flex-1')}>
        <p className="text-sm font-medium text-white">{user.display_name}</p>
        {unlock ?? <p className="text-xs text-slate-500">{user.role}</p>}
      </div>
      <button onClick={handleLogout} className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-white">Logout</button>
    </div>
  )

  return (
    <div className={cn('flex h-screen bg-gray-950', top ? 'flex-col' : '')}>
      {top ? (
        <header className="hidden items-center gap-2 border-b border-slate-800 bg-slate-900/50 px-4 py-2 md:flex">
          <span className="mr-3 text-lg font-bold text-white">OpenFamHub</span>
          <nav className="flex flex-1 flex-wrap gap-1" aria-label="Main">
            {navItems.map((item) => (
              <Link key={item.to} to={item.to} className={linkClass(item.to, 'py-1.5')}><span>{item.icon}</span>{item.label}</Link>
            ))}
            {isAdmin && (
              <details className="relative">
                <summary className="flex cursor-pointer list-none items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-white">
                  Admin ▾
                </summary>
                <div className="absolute z-50 mt-1 w-44 rounded-lg border border-slate-700 bg-slate-900 p-1 shadow-lg">
                  {adminItems.map((item) => <Link key={item.to} to={item.to} className={linkClass(item.to)}>{item.label}</Link>)}
                </div>
              </details>
            )}
          </nav>
          {userBox}
        </header>
      ) : (
        <aside className="hidden w-60 flex-col border-r border-slate-800 bg-slate-900/50 md:flex">
          <div className="flex items-center gap-2 border-b border-slate-800 px-5 py-4">
            <span className="text-xl font-bold text-white">OpenFamHub</span>
          </div>
          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Main">
            {navItems.map((item) => (
              <Link key={item.to} to={item.to} className={linkClass(item.to)}><span>{item.icon}</span>{item.label}</Link>
            ))}
            {isAdmin && (
              <>
                <div className="my-3 border-t border-slate-800" />
                <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-slate-600">Admin</p>
                {adminItems.map((item) => <Link key={item.to} to={item.to} className={linkClass(item.to)}>{item.label}</Link>)}
              </>
            )}
          </nav>
          <div className="border-t border-slate-800 px-4 py-3">
            {userBox}
            <BuildInfoBadge className="mt-3" />
          </div>
        </aside>
      )}

      {/* Main content area */}
      <main className="flex-1 overflow-y-auto">
        {/* Pages are lazy-loaded; keep the nav visible while one loads. */}
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
        {top && <BuildInfoBadge className="hidden px-6 py-3 md:block" />}
      </main>

      {/* Mobile: the first few items, then "More". */}
      {moreOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 md:hidden" onClick={() => setMoreOpen(false)}>
          <div className="absolute bottom-16 left-2 right-2 rounded-xl border border-slate-700 bg-slate-900 p-2" role="menu" aria-label="More">
            {[...navItems.slice(MOBILE_ITEMS), { to: '/me', label: 'My settings', icon: '👤' },
              ...(isAdmin ? adminItems.map((a) => ({ ...a, icon: '⚙️' })) : [])].map((item) => (
              <Link key={item.to} to={item.to} role="menuitem" className={linkClass(item.to)} onClick={() => setMoreOpen(false)}>
                <span>{item.icon}</span>{item.label}
              </Link>
            ))}
            <button onClick={handleLogout} className="w-full rounded-lg px-3 py-2 text-left text-sm text-slate-400 hover:bg-slate-800">Logout</button>
          </div>
        </div>
      )}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-slate-800 bg-slate-900 px-2 py-2 md:hidden"
        aria-label="Mobile">
        {navItems.slice(0, MOBILE_ITEMS).map((item) => (
          <Link key={item.to} to={item.to}
            className={cn('flex flex-col items-center gap-0.5 rounded-lg px-3 py-1 text-xs transition-colors',
              isActive(item.to) ? 'text-primary' : 'text-slate-500 hover:text-slate-300')}>
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </Link>
        ))}
        <button onClick={() => setMoreOpen((o) => !o)} aria-expanded={moreOpen}
          className="flex flex-col items-center gap-0.5 rounded-lg px-3 py-1 text-xs text-slate-500 hover:text-slate-300">
          <span className="text-lg">☰</span>
          More
        </button>
      </nav>

      {/* Bottom padding for mobile nav */}
      <div className="h-16 md:hidden" />
    </div>
  )
}
