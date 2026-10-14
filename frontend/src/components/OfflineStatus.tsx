import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { discard, keepMine, merge, mergedChanges, replay, useOffline, type QueuedWrite } from '../lib/offline'

const btn = 'rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50'

/** One write that needs a person: someone else changed it, or the server refused it. */
function Decide({ write, onDone }: { write: QueuedWrite; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const act = async (fn: () => Promise<void>) => {
    setBusy(true)
    try { await fn() } finally { setBusy(false); onDone() }
  }
  const c = write.conflict
  const canKeepMine = !!c?.current
  const canMerge = !!c?.current && !!write.base && !!write.local && Object.keys(mergedChanges(write)).length > 0
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Offline change">
      <div className="w-full max-w-md space-y-3 rounded-xl border border-gray-700 bg-gray-900 p-5">
        <h2 className="text-lg font-semibold text-white">{c ? 'This changed while you were offline' : "This change wasn't saved"}</h2>
        <p className="text-sm text-gray-300"><b>{write.label}</b></p>
        <p className="text-sm text-gray-400">{c ? c.message : write.error}</p>
        {c && c.fields.length > 0 && <p className="text-xs text-gray-500">Changed by someone else: {c.fields.join(', ')}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          {c ? (
            <>
              <button className={`${btn} bg-gray-800 text-gray-200`} disabled={busy} onClick={() => act(() => discard(write))}>
                {canKeepMine ? 'Keep theirs' : 'OK, drop mine'}</button>
              {canMerge && <button className={`${btn} bg-gray-800 text-gray-200`} disabled={busy} onClick={() => act(() => merge(write))}>Merge</button>}
              {canKeepMine && <button className={`${btn} bg-primary text-white`} disabled={busy} onClick={() => act(() => keepMine(write))}>Keep mine</button>}
            </>
          ) : (
            <>
              <button className={`${btn} bg-gray-800 text-gray-200`} disabled={busy} onClick={() => act(() => discard(write))}>Discard</button>
              <button className={`${btn} bg-primary text-white`} disabled={busy} onClick={() => act(() => keepMine(write))}>Try again</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * The offline banner and sync indicator: shown while offline, while changes
 * are waiting, or when one needs a decision. Nothing when all is saved.
 */
export default function OfflineStatus() {
  const { online, pending, syncing, signInNeeded } = useOffline()
  const qc = useQueryClient()
  const [deciding, setDeciding] = useState(false)
  const stuck = pending.filter((w) => w.conflict || w.error)
  const waiting = pending.length - stuck.length
  if (online && pending.length === 0) return null
  const resume = () => void replay((keys) => keys.forEach((queryKey) => qc.invalidateQueries({ queryKey })))
  return (
    <>
      <div className={`flex flex-wrap items-center gap-3 px-4 py-2 text-sm ${online ? 'bg-slate-800 text-slate-200' : 'bg-amber-900/70 text-amber-100'}`}
        role="status">
        {!online && <span>📴 You're offline. Changes are kept on this device and sync when you're back.</span>}
        {online && signInNeeded && <span>🔑 Sign in again to save {pending.length} change{pending.length === 1 ? '' : 's'}.</span>}
        {online && !signInNeeded && waiting > 0 && <span>{syncing ? 'Syncing…' : `${waiting} change${waiting === 1 ? '' : 's'} waiting to sync`}</span>}
        {!online && waiting > 0 && <span className="text-amber-200">({waiting} waiting)</span>}
        {online && waiting > 0 && !syncing && <button className="underline" onClick={resume}>Sync now</button>}
        {stuck.length > 0 && (
          <button className="ml-auto rounded bg-amber-600 px-2 py-0.5 text-white" onClick={() => setDeciding(true)}>
            {stuck.length} need{stuck.length === 1 ? 's' : ''} a decision</button>
        )}
      </div>
      {deciding && stuck[0] && <Decide write={stuck[0]} onDone={() => { setDeciding(false); resume() }} />}
    </>
  )
}
