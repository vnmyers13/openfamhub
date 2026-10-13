import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from './client'
import { onWallUnauthorized } from './wall'

function failWith(status: number): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig) => {
    throw new AxiosError('fail', 'ERR', config, null, {
      status, statusText: '', headers: {}, config, data: { detail: 'Display not paired' },
    })
  }
}

async function request(url: string, status: number) {
  await apiClient.get(url, { adapter: failWith(status) }).catch(() => undefined)
}

describe('onWallUnauthorized (#10)', () => {
  const offs: Array<() => void> = []
  afterEach(() => offs.splice(0).forEach((off) => off()))

  it('fires when a display request is rejected as unpaired', async () => {
    const listener = vi.fn()
    offs.push(onWallUnauthorized(listener))
    await request('/wall/events', 401)
    await request('/wall/members', 401)
    expect(listener).toHaveBeenCalledTimes(2)
  })

  it('ignores other statuses, other APIs, and pairing attempts', async () => {
    const listener = vi.fn()
    offs.push(onWallUnauthorized(listener))
    await request('/wall/events', 500)
    await request('/calendar/events', 403)
    await request('/wall/pair', 401) // a bad pairing link is handled by the pairing flow
    expect(listener).not.toHaveBeenCalled()
  })

  it('stops firing once unsubscribed', async () => {
    const listener = vi.fn()
    onWallUnauthorized(listener)()
    await request('/wall/events', 401)
    expect(listener).not.toHaveBeenCalled()
  })
})
