import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useDeleteTodo, useFamilyMembers, useSaveTodo, useTodos } from '../../api/chores'
import { useAuthStore } from '../../stores/auth'
import { Banner, MemberSelect } from './Controls'
import { input, nameOf, primary } from './shared'

export default function TodosTab() {
  const user = useAuthStore((s) => s.user)
  const [showDone, setShowDone] = useState(false)
  const { data: todos } = useTodos(showDone)
  const { data: members } = useFamilyMembers()
  const save = useSaveTodo()
  const remove = useDeleteTodo()
  const [title, setTitle] = useState('')
  const [assignee, setAssignee] = useState<string | null>(null)
  const [due, setDue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const canEdit = !!user && user.role !== 'viewer'

  const run = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(errorDetail(err, "That didn't work"))
    }
  }

  const add = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    void run(async () => {
      await save.mutateAsync({ title: title.trim(), assigned_to: assignee, due_date: due || null })
      setTitle('')
      setDue('')
      setAssignee(null)
    })
  }

  return (
    <div>
      <Banner text={error} onClose={() => setError(null)} />
      {canEdit && (
        <form onSubmit={add} className="mb-6 grid gap-2 rounded-lg border border-gray-800 bg-gray-900 p-3 sm:grid-cols-[1fr_10rem_10rem_auto]">
          <label className="sr-only" htmlFor="todo-title">New to-do</label>
          <input id="todo-title" className={input} placeholder="Add a to-do…" value={title} maxLength={256}
            onChange={(e) => setTitle(e.target.value)} />
          <label className="sr-only" htmlFor="todo-who">For</label>
          <MemberSelect id="todo-who" value={assignee} onChange={setAssignee} members={members} anyoneLabel="Anyone" />
          <label className="sr-only" htmlFor="todo-due">Due</label>
          <input id="todo-due" type="date" className={input} value={due} onChange={(e) => setDue(e.target.value)} />
          <button type="submit" className={primary} disabled={save.isPending || !title.trim()}>Add</button>
        </form>
      )}
      <label className="mb-3 flex items-center gap-2 text-sm text-gray-400">
        <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Show done
      </label>
      {todos && todos.length === 0 && <p className="text-sm text-gray-500">Nothing to do. 🎉</p>}
      <ul className="space-y-2">
        {(todos ?? []).map((t) => (
          <li key={t.id} className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
            <input type="checkbox" checked={t.done} disabled={!canEdit} aria-label={`Done: ${t.title}`}
              onChange={(e) => void run(() => save.mutateAsync({ id: t.id, done: e.target.checked }))} />
            <div className="min-w-0 flex-1">
              <p className={`truncate ${t.done ? 'text-gray-500 line-through' : 'text-white'}`}>{t.title}</p>
              <p className="text-xs text-gray-400">
                {nameOf(members, t.assigned_to)}{t.due_date ? ` · due ${t.due_date}` : ''}
              </p>
            </div>
            {(user?.role === 'admin' || t.created_by === user?.id) && (
              <button className="text-sm text-gray-500 hover:text-red-300" aria-label={`Delete ${t.title}`}
                onClick={() => void run(() => remove.mutateAsync(t.id))}>✕</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
