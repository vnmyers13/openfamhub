import { useState } from 'react'
import { errorDetail } from '../../api/client'
import {
  isSecret, testServerSetting, useSaveServerSettings, useServerSettings, type ServerSettings, type TestResult,
} from '../../api/serverSettings'

export interface FieldDef {
  name: string
  label: string
  kind: 'text' | 'url' | 'number' | 'time' | 'secret' | 'select'
  options?: { value: string; label: string }[]
  placeholder?: string
  help?: string
}

const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white disabled:opacity-50'

/**
 * A group of server settings saved together. Only changed fields are sent.
 * Secrets show whether one is set; typing replaces it, Clear removes it, and
 * the current one is never shown. Fields set in `.env` are read-only here.
 */
export default function ServerSettingsForm({ title, fields, test, intro }: {
  title: string; fields: FieldDef[]; test?: { what: 'home-assistant' | 'ntfy' | 'email'; label: string }; intro?: React.ReactNode
}) {
  const { data } = useServerSettings()
  if (!data) return <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 text-sm text-gray-400" aria-label={title}>Loading…</section>
  return <Form key={JSON.stringify(data)} title={title} fields={fields} test={test} intro={intro} data={data} />
}

function Form({ title, fields, test, intro, data }: {
  title: string; fields: FieldDef[]; test?: { what: 'home-assistant' | 'ntfy' | 'email'; label: string }; intro?: React.ReactNode; data: ServerSettings
}) {
  const save = useSaveServerSettings()
  const [draft, setDraft] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((f) => {
    const s = data[f.name]
    return [f.name, isSecret(s) || s === undefined ? '' : String(s.value)]
  })))
  const [clears, setClears] = useState<Set<string>>(new Set())
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)

  const changes = (): Record<string, string | number> => {
    const out: Record<string, string | number> = {}
    for (const f of fields) {
      const s = data[f.name]
      if (!s || s.locked) continue
      const v = draft[f.name].trim()
      if (isSecret(s)) {
        if (clears.has(f.name)) out[f.name] = ''
        else if (v) out[f.name] = v
      } else if (v !== String(s.value)) {
        out[f.name] = f.kind === 'number' ? Number(v) : v
      }
    }
    return out
  }
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)
    const body = changes()
    if (Object.keys(body).length === 0) {
      setMessage({ ok: true, text: 'Nothing changed.' })
      return
    }
    try {
      await save.mutateAsync(body)
      setMessage({ ok: true, text: 'Saved.' })
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, "Couldn't save") })
    }
  }
  const runTest = async () => {
    if (!test) return
    setTesting(true)
    setMessage(null)
    try {
      const r: TestResult = await testServerSetting(test.what)
      setMessage({ ok: r.ok, text: r.message })
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, "Couldn't run the test") })
    } finally {
      setTesting(false)
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-6" aria-label={title}>
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      {intro}
      {fields.map((f) => {
        const s = data[f.name]
        if (!s) return null
        const id = `server-${f.name}`
        const secret = isSecret(s)
        return (
          <div key={f.name}>
            <label htmlFor={id} className="mb-1 block text-sm text-gray-300">{f.label}</label>
            <div className="flex gap-2">
              {f.kind === 'select' ? (
                <select id={id} className={input} disabled={s.locked} value={draft[f.name]}
                  onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))}>
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input id={id} className={input} disabled={s.locked || (secret && clears.has(f.name))} autoComplete="off"
                  type={secret ? 'password' : f.kind === 'number' ? 'number' : f.kind === 'time' ? 'time' : 'text'}
                  placeholder={secret ? (s.is_set ? 'Set (type to replace)' : 'Not set') : f.placeholder}
                  value={draft[f.name]} onChange={(e) => setDraft((d) => ({ ...d, [f.name]: e.target.value }))} />
              )}
              {secret && s.is_set && !s.locked && (
                <button type="button" className="rounded border border-gray-700 px-3 text-sm text-gray-300 hover:border-gray-500"
                  aria-pressed={clears.has(f.name)} aria-label={`Clear ${f.label}`}
                  onClick={() => setClears((c) => { const n = new Set(c); if (n.has(f.name)) n.delete(f.name); else n.add(f.name); return n })}>
                  {clears.has(f.name) ? 'Keep' : 'Clear'}
                </button>
              )}
            </div>
            {s.locked && <p className="mt-1 text-xs text-amber-300">Set in .env on the server; change it there.</p>}
            {secret && s.unreadable && !s.locked && (
              <p className="mt-1 text-xs text-red-300" role="alert">The saved one can't be read any more (the server's SECRET_KEY changed). Enter it again.</p>
            )}
            {f.help && <p className="mt-1 text-xs text-gray-500">{f.help}</p>}
          </div>
        )
      })}
      {message && <p className={`text-sm ${message.ok ? 'text-green-300' : 'text-red-300'}`} role={message.ok ? 'status' : 'alert'}>{message.text}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        {test && (
          <button type="button" onClick={runTest} disabled={testing}
            className="rounded border border-gray-700 px-4 py-2 text-sm text-gray-200 hover:border-gray-500 disabled:opacity-50">
            {testing ? 'Trying…' : test.label}
          </button>
        )}
        <button type="submit" disabled={save.isPending}
          className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}
