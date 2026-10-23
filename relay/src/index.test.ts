import { env, exports } from 'cloudflare:workers'
import { evictDurableObject, runInDurableObject } from 'cloudflare:test'
import { describe, expect, it, vi } from 'vitest'
import { FeedStore, type Env } from './index'

const ORIGIN = 'https://relay.example'
const ICS = 'BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n'
const NEXT = 'BEGIN:VCALENDAR\r\nX-WR-CALNAME:Replacement\r\nEND:VCALENDAR\r\n'
const AUTH = { Authorization: 'Bearer local-test-management-token', 'Content-Type': 'application/json' }
const request = (path: string, init?: RequestInit) => exports.default.fetch(ORIGIN + path, init)
const create = async (kind = 'titles') => {
  const response = await request('/v1/feeds', { method: 'POST', headers: AUTH, body: JSON.stringify({ kind, ics: ICS }) })
  expect(response.status).toBe(201)
  return response.json<{ relay_id: string; subscription_url: string }>()
}

describe('calendar relay', () => {
  it.each(['POST', 'PUT', 'DELETE', 'GET'])('rejects unauthenticated %s management requests', async (method) => {
    for (const Authorization of ['', 'Bearer wrong', 'Basic local-test-management-token', 'Bearer local-test-management-token-extra']) {
      const response = await request('/v1/feeds', { method, headers: { Authorization } })
      expect(response.status).toBe(401)
    }
    expect((await request('/v1/unknown')).status).toBe(401)
  })

  it('generates independent opaque links, stores only a token hash, and serves the document without caching', async () => {
    const first = await create()
    const second = await create('full')
    expect(first.relay_id).toMatch(/^[a-f0-9]{64}$/)
    expect(first.subscription_url).toMatch(/^https:\/\/relay\.example\/c\/[a-f0-9]{64}\.ics$/)
    expect(first.relay_id).not.toBe(second.relay_id)
    expect(first.subscription_url).not.toBe(second.subscription_url)
    const token = new URL(first.subscription_url).pathname.slice(3, -4)
    expect(first.relay_id).not.toBe(token)
    const response = await exports.default.fetch(first.subscription_url)
    expect(response.status).toBe(200)
    expect(response.headers.get('Content-Type')).toBe('text/calendar; charset=utf-8')
    expect(response.headers.get('Cache-Control')).toBe('no-store')
    expect(await response.text()).toBe(ICS)
    const stub = env.FEEDS.get(env.FEEDS.idFromName('feeds'))
    const rows = await runInDurableObject<FeedStore, Record<string, unknown>[]>(stub, (_instance, state) =>
      state.storage.sql.exec('SELECT * FROM feeds WHERE relay_id = ?', first.relay_id).toArray())
    expect(JSON.stringify(rows)).not.toContain(token)
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token)))]
      .map((n) => n.toString(16).padStart(2, '0')).join('')
    expect(rows[0].token_hash).toBe(hash)
  })

  it('replaces whole documents atomically and never exposes a partial version', async () => {
    const feed = await create()
    const results = await Promise.all([
      exports.default.fetch(feed.subscription_url).then((r) => r.text()),
      request(`/v1/feeds/${feed.relay_id}`, { method: 'PUT', headers: AUTH, body: JSON.stringify({ ics: NEXT }) }),
      exports.default.fetch(feed.subscription_url).then((r) => r.text()),
    ])
    expect([ICS, NEXT]).toContain(results[0])
    expect((results[1] as Response).status).toBe(204)
    expect([ICS, NEXT]).toContain(results[2])
    expect(await (await exports.default.fetch(feed.subscription_url)).text()).toBe(NEXT)
    const rejected = await request(`/v1/feeds/${feed.relay_id}`, { method: 'PUT', headers: AUTH, body: '{broken' })
    expect(rejected.status).toBe(400)
    expect(await (await exports.default.fetch(feed.subscription_url)).text()).toBe(NEXT)
  })

  it('keeps the old document on storage failure and never logs the failed content', async () => {
    const feed = await create()
    const stub = env.FEEDS.get(env.FEEDS.idFromName('feeds'))
    await runInDurableObject(stub, (_instance, state) => {
      state.storage.sql.exec(`CREATE TRIGGER fail_update BEFORE UPDATE ON feeds BEGIN SELECT RAISE(ABORT, 'private snapshot'); END`)
    })
    const log = vi.spyOn(console, 'error')
    try {
      const rejected = await request(`/v1/feeds/${feed.relay_id}`, { method: 'PUT', headers: AUTH, body: JSON.stringify({ ics: NEXT }) })
      expect(rejected.status).toBe(503)
      expect(await rejected.text()).toBe('')
      expect(log).not.toHaveBeenCalled()
      expect(await (await exports.default.fetch(feed.subscription_url)).text()).toBe(ICS)
    } finally {
      log.mockRestore()
      await runInDurableObject(stub, (_instance, state) => { state.storage.sql.exec('DROP TRIGGER fail_update') })
    }
  })

  it('contains public-read storage failures inside the Durable Object', async () => {
    const feed = await create()
    const stub = env.FEEDS.get(env.FEEDS.idFromName('feeds'))
    await runInDurableObject(stub, (_instance, state) => {
      state.storage.sql.exec('ALTER TABLE feeds RENAME TO unavailable_feeds')
    })
    try {
      const response = await stub.fetch(feed.subscription_url)
      expect(response.status).toBe(503)
      expect(await response.text()).toBe('')
      expect(response.headers.get('Cache-Control')).toBe('no-store')
    } finally {
      await runInDurableObject(stub, (_instance, state) => {
        state.storage.sql.exec('ALTER TABLE unavailable_feeds RENAME TO feeds')
      })
    }
  })

  it('deletes the mapping and document immediately without affecting another feed or allowing resurrection', async () => {
    const first = await create()
    const second = await create('full')
    expect((await request(`/v1/feeds/${first.relay_id}`, { method: 'DELETE', headers: AUTH })).status).toBe(204)
    const gone = await exports.default.fetch(first.subscription_url)
    expect(gone.status).toBe(404)
    expect(gone.headers.get('Cache-Control')).toBe('no-store')
    expect((await request(`/v1/feeds/${first.relay_id}`, { method: 'PUT', headers: AUTH, body: JSON.stringify({ ics: NEXT }) })).status).toBe(404)
    expect((await request(`/v1/feeds/${first.relay_id}`, { method: 'DELETE', headers: AUTH })).status).toBe(204)
    expect(await (await exports.default.fetch(second.subscription_url)).text()).toBe(ICS)
    const stub = env.FEEDS.get(env.FEEDS.idFromName('feeds'))
    const rows = await runInDurableObject<FeedStore, Record<string, unknown>[]>(stub, (_instance, state) =>
      state.storage.sql.exec('SELECT * FROM feeds WHERE relay_id = ?', first.relay_id).toArray())
    expect(rows).toEqual([])
    await evictDurableObject(stub)
    expect((await exports.default.fetch(first.subscription_url)).status).toBe(404)
    expect(await (await exports.default.fetch(second.subscription_url)).text()).toBe(ICS)
  })

  it('fails closed when the management secret is absent or empty', async () => {
    const stub = env.FEEDS.get(env.FEEDS.idFromName('feeds'))
    const status = await runInDurableObject<FeedStore, number[]>(stub, async (_instance, state) => {
      const missing = { FEEDS: env.FEEDS } as Env
      const statuses: number[] = []
      for (const config of [missing, { ...missing, RELAY_API_TOKEN: '' }]) {
        const store = new FeedStore(state, config)
        const response = await store.fetch(new Request(ORIGIN + '/v1/feeds', {
          method: 'POST', headers: { Authorization: 'Bearer ' },
        }))
        statuses.push(response.status)
      }
      return statuses
    })
    expect(status).toEqual([401, 401])
  })

  it.each([
    { kind: 'other', ics: ICS }, { kind: 'titles' }, { kind: 'titles', ics: 42 },
    { kind: 'titles', ics: ICS, subscription_url: 'https://attacker.example' },
    { kind: 'titles', ics: ICS, relay_id: 'chosen' },
  ])('rejects invalid create payloads and caller-selected links: %j', async (body) => {
    const response = await request('/v1/feeds', { method: 'POST', headers: AUTH, body: JSON.stringify(body) })
    expect(response.status).toBe(400)
  })

  it('rejects oversized snapshots and non-JSON writes', async () => {
    expect((await request('/v1/feeds', { method: 'POST', headers: AUTH, body: JSON.stringify({ kind: 'titles', ics: 'x'.repeat(1024 * 1024 + 1) }) })).status).toBe(413)
    expect((await request('/v1/feeds', { method: 'POST', headers: { Authorization: AUTH.Authorization }, body: ICS })).status).toBe(400)
    expect((await request('/c/not-a-token.ics')).status).toBe(404)
    expect((await request('/c/' + 'f'.repeat(64) + '.ics')).status).toBe(404)
  })

  it('does not accept management credentials or serve documents over HTTP', async () => {
    const response = await exports.default.fetch('http://relay.example/v1/feeds', {
      method: 'POST', headers: AUTH, body: JSON.stringify({ kind: 'titles', ics: ICS }),
    })
    expect(response.status).toBe(400)
    const feed = await create()
    expect((await exports.default.fetch(feed.subscription_url.replace('https:', 'http:'))).status).toBe(400)
  })
})
