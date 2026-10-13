import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

/**
 * Layout route for /admin/*. Non-admins are sent to the dashboard instead of
 * seeing admin pages whose API calls all fail with 403 (which looked like
 * empty lists). The API still enforces the role; this only fixes the UI.
 */
export default function RequireAdmin() {
  const user = useAuthStore((s) => s.user)
  if (!user) return null // boot is still loading /auth/me, or redirecting to login
  if (user.role !== 'admin') return <Navigate to="/dashboard" replace />
  return <Outlet />
}
