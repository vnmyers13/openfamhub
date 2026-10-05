import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Auth endpoints report their own 401s (bad password, bad PIN, not logged in yet);
// the boot logic in App.tsx decides where to send the user for those.
// Wall requests use their own device cookie; the wall shows a pairing screen
// instead of the login page.
function isAuthRequest(url: string | undefined): boolean {
  const path = (url ?? '').replace(/^\/+/, '')
  return path.startsWith('auth/') || path.startsWith('wall/')
}

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (
      err.response?.status === 401 &&
      !isAuthRequest(err.config?.url) &&
      window.location.pathname !== '/login' &&
      !window.location.pathname.startsWith('/wall')
    ) {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)
