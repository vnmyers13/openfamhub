import { DurableObject } from 'cloudflare:workers'

export interface Env {
  FEEDS: DurableObjectNamespace<FeedStore>
  RELAY_API_TOKEN: string
}

const MAX_ICS_BYTES = 1024 * 1024
// JSON may escape every document byte as six characters.
const MAX_REQUEST_BYTES = MAX_ICS_BYTES * 6 + 1024
const encoder = new TextEncoder()
const opaque = () => hex(crypto.getRandomValues(new Uint8Array(32)))
const hex = (bytes: Uint8Array) => [...bytes].map((n) => n.toString(16).padStart(2, '0')).join('')
const digest = (value: string) => crypto.subtle.digest('SHA-256', encoder.encode(value))
const empty = (status: number) => new Response(null, { status, headers: { 'Cache-Control': 'no-store' } })

async function authorized(request: Request, token: string): Promise<boolean> {
  if (!token) return false // Missing secret must fail closed, including "Bearer ".
  const [actual, expected] = await Promise.all([
    digest(request.headers.get('Authorization') ?? ''), digest('Bearer ' + token),
  ])
  // Fixed-size digests avoid a length-dependent secret comparison.
  return crypto.subtle.timingSafeEqual(actual, expected)
}

class InvalidRequest extends Error {
  constructor(readonly status: number) { super() }
}

async function document(request: Request, creating: boolean): Promise<{ kind?: string; ics: string }> {
  if (request.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json') {
    throw new InvalidRequest(400)
  }
  if (Number(request.headers.get('Content-Length')) > MAX_REQUEST_BYTES) throw new InvalidRequest(413)
  const reader = request.body?.getReader()
  if (!reader) throw new InvalidRequest(400)
  const chunks: Uint8Array[] = []
  let length = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      length += value.byteLength
      if (length > MAX_REQUEST_BYTES) {
        await reader.cancel()
        throw new InvalidRequest(413)
      }
      chunks.push(value)
    }
  } finally {
    reader.releaseLock()
  }
  const bytes = new Uint8Array(length)
  let offset = 0
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
  let body: unknown
  try { body = JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes)) }
  catch { throw new InvalidRequest(400) }
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new InvalidRequest(400)
  const values = body as Record<string, unknown>
  const keys = Object.keys(values)
  if (keys.some((k) => k !== 'ics' && !(creating && k === 'kind'))
      || typeof values.ics !== 'string' || (creating && values.kind !== 'titles' && values.kind !== 'full')) {
    throw new InvalidRequest(400)
  }
  if (encoder.encode(values.ics).byteLength > MAX_ICS_BYTES) throw new InvalidRequest(413)
  return { ics: values.ics, ...(creating ? { kind: values.kind as string } : {}) }
}

export class FeedStore extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env)
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS feeds (
      relay_id TEXT PRIMARY KEY,
      token_hash TEXT NOT NULL UNIQUE,
      kind TEXT NOT NULL CHECK (kind IN ('titles', 'full')),
      ics TEXT NOT NULL
    )`)
  }

  async fetch(request: Request): Promise<Response> {
    try {
      return await this.respond(request)
    } catch {
      // Catch read failures here too: the runtime logs uncaught DO exceptions.
      return empty(503)
    }
  }

  private async respond(request: Request): Promise<Response> {
    const url = new URL(request.url)
    if (url.pathname.startsWith('/v1/')) {
      if (!await authorized(request, this.env.RELAY_API_TOKEN)) return empty(401)
      try {
        if (url.pathname === '/v1/feeds' && request.method === 'POST') {
          const { kind, ics } = await document(request, true)
          const relayId = opaque(), token = opaque()
          const tokenHash = hex(new Uint8Array(await digest(token)))
          this.ctx.storage.transactionSync(() => {
            this.ctx.storage.sql.exec('INSERT INTO feeds (relay_id, token_hash, kind, ics) VALUES (?, ?, ?, ?)', relayId, tokenHash, kind!, ics)
          })
          return Response.json({ relay_id: relayId, subscription_url: url.origin + '/c/' + token + '.ics' }, {
            status: 201, headers: { 'Cache-Control': 'no-store' },
          })
        }
        const match = /^\/v1\/feeds\/([a-f0-9]{64})$/.exec(url.pathname)
        if (match && request.method === 'PUT') {
          const { ics } = await document(request, false)
          const updated = this.ctx.storage.transactionSync(() =>
            this.ctx.storage.sql.exec('UPDATE feeds SET ics = ? WHERE relay_id = ? RETURNING relay_id', ics, match[1]).toArray())
          return empty(updated.length ? 204 : 404)
        }
        if (match && request.method === 'DELETE') {
          this.ctx.storage.transactionSync(() => {
            this.ctx.storage.sql.exec('DELETE FROM feeds WHERE relay_id = ?', match[1])
          })
          return empty(204) // Idempotent revocation; never recreate a missing feed.
        }
        return empty(404)
      } catch (error) {
        if (error instanceof InvalidRequest) return empty(error.status)
        // An uncaught DO error is logged by workerd before the Worker can catch
        // it. Contain storage/provider details here, not only in the front door.
        return empty(503)
      }
    }
    const match = /^\/c\/([a-f0-9]{64})\.ics$/.exec(url.pathname)
    if (match && request.method === 'GET') {
      const hash = hex(new Uint8Array(await digest(match[1])))
      const rows = this.ctx.storage.sql.exec<{ ics: string }>('SELECT ics FROM feeds WHERE token_hash = ?', hash).toArray()
      if (rows.length) return new Response(rows[0].ics, {
        headers: { 'Content-Type': 'text/calendar; charset=utf-8', 'Cache-Control': 'no-store' },
      })
    }
    return empty(404)
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      if (new URL(request.url).protocol !== 'https:') return empty(400)
      // One strongly consistent owner for every token and complete document.
      return await env.FEEDS.get(env.FEEDS.idFromName('feeds')).fetch(request)
    } catch {
      // Never echo or log requests, bearer tokens, documents or storage errors.
      return empty(503)
    }
  },
} satisfies ExportedHandler<Env>
