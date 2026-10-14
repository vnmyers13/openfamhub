import { useState } from 'react'
import { errorDetail } from '../../api/client'
import {
  useAddShopping, useClearChecked, useDeleteShopping, useShopping, useShoppingFromPlan, useShoppingHistory,
  useUpdateShopping, type ShoppingItem,
} from '../../api/meals'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'

function Row({ item, canEdit, onToggle, onDelete }: {
  item: ShoppingItem; canEdit: boolean; onToggle: () => void; onDelete: () => void
}) {
  return (
    <li className="flex items-center gap-3 rounded border border-gray-800 bg-gray-900 px-3 py-2">
      <input type="checkbox" className="h-5 w-5" checked={item.checked} disabled={!canEdit} onChange={onToggle}
        aria-label={`${item.checked ? 'Not bought' : 'Bought'}: ${item.name}`} />
      <div className="min-w-0 flex-1">
        <p className={`truncate ${item.checked ? 'text-gray-500 line-through' : 'text-white'}`}>
          {item.name}{item.quantity && <span className="text-gray-400"> · {item.quantity}</span>}
        </p>
        {(item.recipe_title || item.in_pantry || item.source === 'pantry') && (
          <p className="text-xs text-gray-500">
            {item.recipe_title && <>for {item.recipe_title}</>}
            {item.source === 'pantry' && <>running low in the pantry</>}
            {item.in_pantry && <span className="text-amber-300">{item.recipe_title ? ' · ' : ''}you may have {item.in_pantry}</span>}
          </p>
        )}
      </div>
      {canEdit && <button className={subtle} onClick={onDelete} aria-label={`Remove: ${item.name}`}>✕</button>}
    </li>
  )
}

export default function ShoppingTab() {
  const user = useAuthStore((s) => s.user)
  const canEdit = !!user && user.role !== 'viewer'
  const { data: items } = useShopping()
  const add = useAddShopping()
  const update = useUpdateShopping()
  const del = useDeleteShopping()
  const fromPlan = useShoppingFromPlan()
  const clear = useClearChecked()
  const [name, setName] = useState('')
  const [qty, setQty] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const { data: history } = useShoppingHistory(showHistory)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const run = async (fn: () => Promise<unknown>, fallback: string) => {
    setError(null)
    try { await fn() } catch (err) { setError(errorDetail(err, fallback)) }
  }
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    run(async () => {
      await add.mutateAsync({ name: name.trim(), quantity: qty.trim() || null })
      setName('')
      setQty('')
    }, "Couldn't add that")
  }
  const todo = (items ?? []).filter((i) => !i.checked)
  const done = (items ?? []).filter((i) => i.checked)
  const row = (i: ShoppingItem) => (
    <Row key={i.id} item={i} canEdit={canEdit}
      onToggle={() => run(() => update.mutateAsync({ id: i.id, checked: !i.checked }), "Couldn't update that")}
      onDelete={() => run(() => del.mutateAsync(i.id), "Couldn't remove that")} />
  )
  return (
    <div className="max-w-2xl">
      <Banner text={error} onClose={() => setError(null)} />
      {note && <p className="mb-4 rounded bg-emerald-900/40 px-4 py-2 text-sm text-emerald-200" role="status">{note}</p>}
      {canEdit && (
        <div className="mb-4 flex flex-wrap gap-2">
          <form onSubmit={submit} className="flex flex-1 gap-2">
            <input className={input} placeholder="Add an item" aria-label="New item" maxLength={256} value={name} onChange={(e) => setName(e.target.value)} />
            <input className={`${input} w-24`} placeholder="How much" aria-label="How much" maxLength={64} value={qty} onChange={(e) => setQty(e.target.value)} />
            <button type="submit" className={primary} disabled={!name.trim() || add.isPending}>Add</button>
          </form>
          <button className={subtle} disabled={fromPlan.isPending} onClick={() => run(async () => {
            const res = await fromPlan.mutateAsync(undefined)
            setNote(res.added || res.removed ? `Added ${res.added} from this week's meals${res.removed ? `, removed ${res.removed}` : ''}.` : "Everything for this week's meals is already here.")
          }, "Couldn't add this week's meals")}>Add this week's meals</button>
        </div>
      )}
      {items && items.length === 0 && <p className="text-sm text-gray-500">The list is empty.</p>}
      <ul className="space-y-1">{todo.map(row)}</ul>
      {done.length > 0 && (
        <section className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">In the cart ({done.length})</h2>
            {canEdit && <button className={subtle} onClick={() => run(() => clear.mutateAsync(), "Couldn't clear the cart")}>Done shopping</button>}
          </div>
          <ul className="space-y-1">{done.map(row)}</ul>
        </section>
      )}
      <p className="mt-6 text-xs text-gray-500">Bought items move to the history each Monday (or when you press "Done shopping").{' '}
        <button className="underline" onClick={() => setShowHistory((s) => !s)}>{showHistory ? 'Hide history' : 'Show history'}</button>
      </p>
      {showHistory && (
        <ul className="mt-2 space-y-1 text-sm text-gray-400">
          {(history ?? []).map((h) => <li key={h.id}>{h.name}{h.checked_at && ` · ${new Date(h.checked_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}`}</li>)}
          {history && history.length === 0 && <li>Nothing yet.</li>}
        </ul>
      )}
    </div>
  )
}
