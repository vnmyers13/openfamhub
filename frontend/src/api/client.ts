import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

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

// ---- "password required" -------------------------------------------------
// Admin actions from a PIN sign-in get 403 "password_required". The
// PasswordPrompt component registers here; the failed request is retried once
// the password is confirmed (POST /auth/elevate).
export const PASSWORD_REQUIRED = 'password_required'

type PromptRequest = { resolve: () => void; reject: () => void }
let promptListener: ((req: PromptRequest) => void) | null = null

export function onPasswordPrompt(listener: (req: PromptRequest) => void): () => void {
  promptListener = listener
  return () => {
    if (promptListener === listener) promptListener = null
  }
}

/** Ask the user for their password (e.g. an "Unlock admin" button). */
export function requestPasswordPrompt(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!promptListener) return reject(new Error('No password prompt mounted'))
    promptListener({ resolve, reject })
  })
}

type RetryConfig = InternalAxiosRequestConfig & { _elevated?: boolean }

apiClient.interceptors.response.use(
  (res) => res,
  async (err: AxiosError<{ detail?: unknown }>) => {
    const status = err.response?.status
    const config = err.config as RetryConfig | undefined

    if (status === 403 && err.response?.data?.detail === PASSWORD_REQUIRED && config && !config._elevated) {
      try {
        await requestPasswordPrompt()
      } catch {
        return Promise.reject(err)
      }
      return apiClient({ ...config, _elevated: true } as RetryConfig)
    }

    if (
      status === 401 &&
      !isAuthRequest(config?.url) &&
      window.location.pathname !== '/login' &&
      !window.location.pathname.startsWith('/wall')
    ) {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

/** The API's error message, or a fallback. */
export function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
