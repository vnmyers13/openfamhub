import { useState } from 'react'
import { useAddShopping, type ShoppingItem } from '../../api/meals'
import { progressLabel, readText, type OcrProgress } from '../../lib/ocr'
import { parseListLines } from '../../lib/ocrLines'
import { input, primary, subtle } from '../chores/shared'

interface Row { name: string; quantity: string; include: boolean; onList: boolean }

/**
 * Scan a list (Phase 10): take or choose a photo of a paper list, read it on
 * this device (lib/ocr), check the lines, then add them to the shopping list.
 * Headings and smudges are skipped; things already on the list start unticked.
 * Adding works offline too (queued like typing them in).
 */
export default function ScanListModal({ items, onClose }: { items: ShoppingItem[]; onClose: (added: number) => void }) {
  const add = useAddShopping()
  const [preview, setPreview] = useState<string | null>(null)
  const [progress, setProgress] = useState<OcrProgress | null>(null)
  const [reading, setReading] = useState(false)
  const [rows, setRows] = useState<Row[] | null>(null)
  const [skipped, setSkipped] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const onPhoto = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    setRows(null)
    setProgress(null)
    setReading(true)
    setPreview((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(file) })
    try {
      const lines = parseListLines(await readText(file, setProgress))
      const have = new Set(items.filter((i) => !i.checked).map((i) => i.name.toLowerCase()))
      const found = lines.filter((l) => l.kind === 'item' && !l.duplicate).map((l) => {
        const onList = have.has(l.name.toLowerCase())
        return { name: l.name, quantity: l.quantity ?? '', include: !onList, onList }
      })
      setSkipped(lines.filter((l) => l.kind !== 'item').map((l) => l.text))
      if (found.length === 0) setError('No list items found. Try a closer, brighter photo of the list.')
      else setRows(found)
    } catch {
      setError("Couldn't read that photo. Try again, or try another one.")
    } finally {
      setReading(false)
    }
  }

  const change = (i: number, patch: Partial<Row>) => setRows((rs) => rs && rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const chosen = (rows ?? []).filter((r) => r.include && r.name.trim())

  const addAll = async () => {
    setAdding(true)
    setError(null)
    let added = 0
    try {
      for (const r of chosen) {
        await add.mutateAsync({ name: r.name.trim(), quantity: r.quantity.trim() || null })
        added += 1
      }
      close(added)
    } catch {
      setError(`Added ${added} of ${chosen.length}; couldn't add the rest. Check the names and try again.`)
      setRows((rs) => rs && rs.filter((r) => !chosen.slice(0, added).includes(r)))
    } finally {
      setAdding(false)
    }
  }

  const close = (added: number) => {
    if (preview) URL.revokeObjectURL(preview)
    onClose(added)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" role="dialog"
      aria-modal="true" aria-labelledby="scan-title">
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-xl border border-gray-800 bg-gray-900 p-5 sm:rounded-xl">
        <h2 id="scan-title" className="text-lg font-semibold text-white">Scan a list</h2>
        <p className="mt-1 text-sm text-gray-400">Take a photo of a paper list. It's read on this device; the photo isn't uploaded.</p>

        <label className="mt-4 flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-gray-600 p-3 text-sm text-gray-300 hover:border-gray-400">
          {preview ? <img src={preview} alt="" className="h-16 w-16 rounded object-cover" /> : <span className="text-2xl" aria-hidden>📷</span>}
          <span>{preview ? 'Use another photo' : 'Take or choose a photo'}</span>
          <input type="file" accept="image/*" capture="environment" className="sr-only" aria-label="Take or choose a photo"
            disabled={reading || adding} onChange={(e) => { void onPhoto(e.target.files?.[0]); e.target.value = '' }} />
        </label>

        {reading && <p className="mt-3 text-sm text-gray-300" role="status">{progressLabel(progress)}</p>}
        {error && <p className="mt-3 rounded bg-red-900/50 px-3 py-2 text-sm text-red-300" role="alert">{error}</p>}

        {rows && (
          <>
            <ul className="mt-4 space-y-2">
              {rows.map((r, i) => (
                <li key={i} className="flex items-center gap-2">
                  <input type="checkbox" className="h-5 w-5" checked={r.include} aria-label={`Add item ${i + 1}`}
                    onChange={(e) => change(i, { include: e.target.checked })} />
                  <div className="min-w-0 flex-1">
                    <input className={input} value={r.name} maxLength={256} aria-label={`Item ${i + 1}`}
                      onChange={(e) => change(i, { name: e.target.value })} />
                    {r.onList && <p className="mt-0.5 text-xs text-amber-300">already on the list</p>}
                  </div>
                  <input className={`${input} w-24`} value={r.quantity} maxLength={64} placeholder="How much"
                    aria-label={`How much for item ${i + 1}`} onChange={(e) => change(i, { quantity: e.target.value })} />
                </li>
              ))}
            </ul>
            {skipped.length > 0 && <p className="mt-3 text-xs text-gray-500">Skipped: {skipped.join(', ')}</p>}
          </>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className={subtle} onClick={() => close(0)} disabled={adding}>Cancel</button>
          {rows && (
            <button type="button" className={primary} disabled={chosen.length === 0 || adding} onClick={() => void addAll()}>
              {adding ? 'Adding…' : `Add ${chosen.length} to the list`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
