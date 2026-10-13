import type { Member } from '../../api/chores'
import { input } from './shared'

export function MemberSelect({ id, value, onChange, members, anyoneLabel = 'Anyone' }: {
  id: string; value: string | null; onChange: (v: string | null) => void; members: Member[] | undefined; anyoneLabel?: string
}) {
  return (
    <select id={id} className={input} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">{anyoneLabel}</option>
      {(members ?? []).filter((m) => m.role !== 'viewer').map((m) => (
        <option key={m.id} value={m.id}>{m.display_name}</option>
      ))}
    </select>
  )
}

export function Banner({ text, onClose }: { text: string | null; onClose: () => void }) {
  if (!text) return null
  return (
    <div className="mb-4 flex items-start justify-between gap-3 rounded bg-red-900/50 px-4 py-2 text-sm text-red-300" role="alert">
      <span>{text}</span>
      <button onClick={onClose} aria-label="Dismiss" className="text-red-200">✕</button>
    </div>
  )
}
