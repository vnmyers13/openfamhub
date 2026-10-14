import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useDeletePantry, usePantry, useRestock, useSavePantry, type PantryItem } from '../../api/meals'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'

const num = (v: string) => (v.trim() === '' ? null : Math.max(0, Number(v) || 0))
const label = 'mb-1 block text-xs text-gray-400'

function PantryForm({ item, onDone, onError }: { item?: PantryItem; onDone: () => void; onError: (m: string) => void }) {
  const save = useSavePantry()
  const [name, setName] = useState(item?.name ?? '')
  const [quantity, setQuantity] = useState(item?.quantity?.toString() ?? '')
  const [unit, setUnit] = useState(item?.unit ?? '')
  const [low, setLow] = useState(item?.low_at?.toString() ?? '')
  const [expires, setExpires] = useState(item?.expires_on ?? '')
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await save.mutateAsync({ id: item?.id, name: name.trim(), quantity: num(quantity), unit: unit.trim() || null,
        low_at: num(low), expires_on: expires || null })
      onDone()
    } catch (err) {
      onError(errorDetail(err, "Couldn't save that"))
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border border-gray-800 bg-gray-900 p-4 sm:grid-cols-[1fr_5rem_5rem_6rem_9rem_auto]"
      aria-label={item ? `Edit ${item.name}` : 'New pantry item'}>
      <div><label htmlFor="pantry-name" className={label}>Item</label>
        <input id="pantry-name" className={input} value={name} maxLength={128} required onChange={(e) => setName(e.target.value)} /></div>
      <div><label htmlFor="pantry-qty" className={label}>Have</label>
        <input id="pantry-qty" type="number" min={0} step="any" className={input} value={quantity} onChange={(e) => setQuantity(e.target.value)} /></div>
      <div><label htmlFor="pantry-unit" className={label}>Unit</label>
        <input id="pantry-unit" className={input} value={unit} maxLength={32} onChange={(e) => setUnit(e.target.value)} /></div>
      <div><label htmlFor="pantry-low" className={label}>Low at</label>
        <input id="pantry-low" type="number" min={0} step="any" className={input} value={low} onChange={(e) => setLow(e.target.value)} /></div>
      <div><label htmlFor="pantry-expires" className={label}>Use by</label>
        <input id="pantry-expires" type="date" className={input} value={expires} onChange={(e) => setExpires(e.target.value)} /></div>
      <div className="flex items-end gap-2">
        <button type="button" className={subtle} onClick={onDone}>Cancel</button>
        <button type="submit" className={primary} disabled={save.isPending || !name.trim()}>Save</button>
      </div>
    </form>
  )
}

function Flags({ item }: { item: PantryItem }) {
  const flags = [
    item.expired && <span key="x" className="rounded bg-red-900/60 px-2 py-0.5 text-xs text-red-200">Expired</span>,
    !item.expired && item.expires_soon && <span key="s" className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-200">Use soon</span>,
    item.is_low && <span key="l" className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-200">Running low</span>,
  ].filter(Boolean)
  return <>{flags}</>
}

export default function PantryTab() {
  const user = useAuthStore((s) => s.user)
  const canEdit = !!user && user.role !== 'viewer'
  const { data: items } = usePantry()
  const del = useDeletePantry()
  const restock = useRestock()
  const [editing, setEditing] = useState<string | null>(null) // 'new' or an item id
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const needs = (items ?? []).filter((i) => i.is_low || i.expired).length
  const doRestock = async () => {
    setError(null)
    try {
      const { added } = await restock.mutateAsync()
      setNote(added ? `Added ${added} to the shopping list.` : "They're already on the shopping list.")
    } catch (err) {
      setError(errorDetail(err, "Couldn't update the shopping list"))
    }
  }
  return (
    <div>
      <Banner text={error} onClose={() => setError(null)} />
      {note && <p className="mb-4 rounded bg-emerald-900/40 px-4 py-2 text-sm text-emerald-200" role="status">{note}</p>}
      {canEdit && (
        <div className="mb-4 flex flex-wrap justify-end gap-2">
          {needs > 0 && <button className={subtle} disabled={restock.isPending} onClick={doRestock}>Put {needs} low or expired on the list</button>}
          <button className={primary} onClick={() => setEditing('new')}>+ Item</button>
        </div>
      )}
      {editing === 'new' && <div className="mb-3"><PantryForm onDone={() => setEditing(null)} onError={setError} /></div>}
      {items && items.length === 0 && <p className="text-sm text-gray-500">Nothing in the pantry yet. Add what you keep on hand to get low-stock and use-by reminders here.</p>}
      <ul className="space-y-1">
        {(items ?? []).map((i) => editing === i.id ? <li key={i.id}><PantryForm item={i} onDone={() => setEditing(null)} onError={setError} /></li> : (
          <li key={i.id} className="flex flex-wrap items-center gap-3 rounded border border-gray-800 bg-gray-900 px-3 py-2">
            <span className="flex-1 text-white">{i.name}</span>
            <span className="text-sm text-gray-400">{i.quantity !== null ? `${i.quantity}${i.unit ? ` ${i.unit}` : ''}` : ''}</span>
            {i.expires_on && <span className="text-xs text-gray-500">use by {new Date(`${i.expires_on}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>}
            <Flags item={i} />
            {canEdit && (
              <span className="flex gap-1">
                <button className={subtle} onClick={() => setEditing(i.id)} aria-label={`Edit: ${i.name}`}>Edit</button>
                <button className={subtle} aria-label={`Remove: ${i.name}`}
                  onClick={() => del.mutateAsync(i.id).catch((err) => setError(errorDetail(err, "Couldn't remove that")))}>✕</button>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
