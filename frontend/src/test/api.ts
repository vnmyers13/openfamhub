import { vi } from 'vitest'
import { apiClient } from '../api/client'

type Reply = unknown | ((body: unknown) => unknown)
export type ApiCall = { method: string; url: string; body: unknown }

/** An error shaped like an axios failure, as the app's errorDetail() reads it. */
export function apiError(status: number, detail: string) {
  return Object.assign(new Error(detail), { response: { status, data: { detail } } })
}

/**
 * Replace apiClient's verbs with canned replies keyed "METHOD /path".
 * A reply may be a value or a function of the request body or, for GET, the
 * query params (throw apiError to
 * fail). Unmocked calls fail with 404. Spies are restored after each test
 * (restoreMocks in vitest.config.ts). Returns the list of calls made.
 */
export function mockApi(routes: Record<string, Reply>): ApiCall[] {
  const all: Record<string, Reply> = { 'GET /health': { build: '0.99' }, ...routes }
  const calls: ApiCall[] = []
  for (const method of ['get', 'post', 'patch', 'delete'] as const) {
    vi.spyOn(apiClient, method).mockImplementation((async (url: string, bodyOrConfig?: unknown) => {
      // POST/PATCH: the request body. GET/DELETE: the query params, so replies can vary by them.
      const body = method === 'post' || method === 'patch' ? bodyOrConfig : (bodyOrConfig as { params?: unknown } | undefined)?.params
      const key = `${method.toUpperCase()} ${url}`
      calls.push({ method: method.toUpperCase(), url, body })
      if (!(key in all)) throw apiError(404, `unmocked ${key}`)
      const reply = all[key]
      return { data: typeof reply === 'function' ? await (reply as (b: unknown) => unknown)(body) : reply }
    }) as never)
  }
  return calls
}
