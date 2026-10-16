import { useState } from 'react'
import { createAiDraft, confirmAiDraft, type Draft } from '../api/ai'
import { errorDetail } from '../api/client'

export default function VoiceAssistant() {
  const [open, setOpen] = useState(false)
  const [request, setRequest] = useState('')
  const [audio, setAudio] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  const makeDraft = async () => {
    setWorking(true); setError(''); setDraft(null)
    try { setDraft(await createAiDraft(request, audio ?? undefined)) } catch (err) { setError(errorDetail(err, 'The local AI could not make a draft.')) } finally { setWorking(false) }
  }
  const confirm = async () => {
    if (!draft) return
    setWorking(true); setError('')
    try { await confirmAiDraft(draft); setOpen(false); setDraft(null); setRequest('') } catch (err) { setError(errorDetail(err, "Couldn't save the confirmed action.")) } finally { setWorking(false) }
  }
  return <>
    <button onClick={() => setOpen(true)} className="rounded bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700">Ask local assistant</button>
    {open && <div role="dialog" aria-modal="true" aria-label="Local assistant" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div className="w-full max-w-lg space-y-4 rounded-xl bg-slate-900 p-6 text-slate-100 shadow-xl">
        <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Local assistant</h2><button onClick={() => setOpen(false)} aria-label="Close">×</button></div>
        <p className="text-sm text-slate-400">Your request stays on this server and its configured local model. Nothing is saved until you confirm.</p>
        <label className="block text-sm" htmlFor="ai-request">What would you like to do?</label>
        <textarea id="ai-request" value={request} onChange={(e) => setRequest(e.target.value)} className="w-full rounded bg-slate-800 p-2" maxLength={2000} />
        <label className="block text-sm" htmlFor="ai-audio">Voice recording</label>
        <input id="ai-audio" type="file" accept="audio/wav,audio/mpeg" onChange={(e) => {
          const file = e.target.files?.[0]
          if (!file) { setAudio(null); return }
          const reader = new FileReader()
          reader.onload = () => setAudio(String(reader.result).split(',', 2)[1] ?? null)
          reader.readAsDataURL(file)
        }} />
        <p className="text-xs text-slate-400">Optional WAV or MP3 recording, processed only by your configured local model.</p>
        {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        {draft && <div className="rounded bg-slate-800 p-3"><p>{draft.summary}</p><p className="mt-1 text-xs text-slate-400">Review this draft before confirming.</p></div>}
        <div className="flex justify-end gap-2">
          {draft ? <button onClick={confirm} disabled={working} className="rounded bg-primary px-3 py-2">Confirm</button> : <button onClick={makeDraft} disabled={(!request.trim() && !audio) || working} className="rounded bg-primary px-3 py-2">Create draft</button>}
        </div>
      </div>
    </div>}
  </>
}
