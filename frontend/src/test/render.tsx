import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/**
 * Render inside a fresh QueryClient and a router. `routes` adds stand-in
 * pages (e.g. { '/dashboard': 'dashboard' }) so navigation can be asserted.
 */
export function renderApp(
  ui: ReactElement,
  { path = '/', routes = {} as Record<string, string> } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={ui} />
          {Object.entries(routes).map(([to, text]) => (
            <Route key={to} path={to} element={<div>{text}</div>} />
          ))}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { client, ...result }
}
