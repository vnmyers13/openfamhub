import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient, onPasswordPrompt, PASSWORD_REQUIRED, requestPasswordPrompt } from './client'

type Req = { resolve: () => void; reject: () => void }

function mountPrompt() {
  const shown: Req[] = []
  const off = onPasswordPrompt((req) => shown.push(req))
  return { shown, off }
}

describe('password prompt coalescing (#12)', () => {
  let off: () => void = () => {}
  afterEach(() => off())

  it('shows one prompt for simultaneous requests and settles them all', async () => {
    const prompt = mountPrompt()
    off = prompt.off
    const a = requestPasswordPrompt()
    const b = requestPasswordPrompt()
    expect(prompt.shown).toHaveLength(1)
    prompt.shown[0].resolve()
    await expect(Promise.all([a, b])).resolves.toEqual([undefined, undefined])
  })

  it('rejects every waiter when the prompt is cancelled', async () => {
    const prompt = mountPrompt()
    off = prompt.off
    const a = requestPasswordPrompt()
    const b = requestPasswordPrompt()
    prompt.shown[0].reject()
    await expect(a).rejects.toBeDefined()
    await expect(b).rejects.toBeDefined()
  })

  it('asks again for a later request once the first prompt is settled', async () => {
    const prompt = mountPrompt()
    off = prompt.off
    const first = requestPasswordPrompt()
    prompt.shown[0].resolve()
    await first
    void requestPasswordPrompt().catch(() => undefined)
    expect(prompt.shown).toHaveLength(2)
    prompt.shown[1].reject()
  })

  it('retries both admin requests after a single unlock', async () => {
    const prompt = mountPrompt()
    off = prompt.off
    const seen: string[] = []
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig & { _elevated?: boolean }) => {
      seen.push(`${config.url}${config._elevated ? ' (retry)' : ''}`)
      if (!config._elevated) {
        throw new AxiosError('forbidden', 'ERR', config, null, {
          status: 403, statusText: '', headers: {}, config, data: { detail: PASSWORD_REQUIRED },
        })
      }
      return { status: 200, statusText: 'OK', headers: {}, config, data: { ok: config.url } }
    })

    const one = apiClient.delete('/users/1', { adapter })
    const two = apiClient.patch('/calendar/sources/2', {}, { adapter })
    await vi.waitFor(() => expect(seen).toHaveLength(2))
    await vi.waitFor(() => expect(prompt.shown.length).toBeGreaterThan(0))
    await new Promise((r) => setTimeout(r, 20)) // give a second prompt time to appear
    expect(prompt.shown).toHaveLength(1)

    prompt.shown[0].resolve()
    const [r1, r2] = await Promise.all([one, two])
    expect(r1.data).toEqual({ ok: '/users/1' })
    expect(r2.data).toEqual({ ok: '/calendar/sources/2' })
  })
})
