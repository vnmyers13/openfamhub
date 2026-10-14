import { useState } from 'react'
import { useFamilyMembers } from '../../api/chores'
import { errorDetail } from '../../api/client'
import { useAddBook, useBooks, useDeleteBook, useUpdateBook, type Book, type BookStatus } from '../../api/home'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, nameOf, primary, subtle } from '../chores/shared'

type Shelf = 'mine' | 'family' | 'everyone'
const TABS: { key: Shelf; label: string }[] = [
  { key: 'mine', label: 'My books' }, { key: 'family', label: 'Family library' }, { key: 'everyone', label: "Everyone's" },
]
const STATUS: Record<BookStatus, string> = { want_to_read: 'Want to read', reading: 'Reading', finished: 'Finished' }
const NEXT: Record<BookStatus, BookStatus | null> = { want_to_read: 'reading', reading: 'finished', finished: null }
const NEXT_LABEL: Record<BookStatus, string> = { want_to_read: 'Start reading', reading: 'Finished it!', finished: '' }

/** Reading lists and the family library; finishing a book earns its reader 50 points (once). */
export default function BooksPage() {
  const user = useAuthStore((s) => s.user)
  const canEdit = !!user && user.role !== 'viewer'
  const [shelf, setShelf] = useState<Shelf>(canEdit ? 'mine' : 'everyone')
  const { data: books } = useBooks(shelf)
  const { data: members } = useFamilyMembers()
  const add = useAddBook()
  const update = useUpdateBook()
  const del = useDeleteBook()
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [cheer, setCheer] = useState<string | null>(null)

  const run = async (fn: () => Promise<Book | unknown>, fallback: string) => {
    setError(null)
    setCheer(null)
    try {
      const result = await fn()
      if (result && typeof result === 'object' && 'points_awarded' in result && (result as Book).points_awarded) {
        setCheer(`🎉 Finished "${(result as Book).title}": +50 points!`)
      }
    } catch (err) {
      setError(errorDetail(err, fallback))
    }
  }
  const mayChange = (b: Book) => canEdit && (b.owner_id === null || b.owner_id === user?.id || user?.role === 'admin')
  const mayEdit = (b: Book) => canEdit && (user?.role === 'admin' || (b.owner_id ? b.owner_id === user?.id : b.added_by === user?.id))
  const whose = (b: Book) => b.owner_id ? `${nameOf(members, b.owner_id)}'s list` : 'Family library'

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-4 text-2xl font-bold text-white">Books</h1>
        <div className="mb-6 flex flex-wrap gap-1 border-b border-gray-800" role="tablist">
          {TABS.filter((t) => canEdit || t.key !== 'mine').map((t) => (
            <button key={t.key} role="tab" aria-selected={shelf === t.key} onClick={() => setShelf(t.key)}
              className={`px-4 py-2 text-sm ${shelf === t.key ? 'border-b-2 border-primary text-white' : 'text-gray-400 hover:text-white'}`}>{t.label}</button>
          ))}
        </div>
        <Banner text={error} onClose={() => setError(null)} />
        {cheer && <p className="mb-4 rounded bg-emerald-900/40 px-4 py-2 text-sm text-emerald-200" role="status">{cheer}</p>}
        {canEdit && shelf !== 'everyone' && (
          <form className="mb-4 flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault()
            run(async () => {
              await add.mutateAsync({ title: title.trim(), author: author.trim() || null, shelf: shelf === 'family' ? 'family' : 'mine' })
              setTitle('')
              setAuthor('')
            }, "Couldn't add the book")
          }}>
            <input className={`${input} flex-1`} placeholder="Title" aria-label="Book title" maxLength={256} value={title} onChange={(e) => setTitle(e.target.value)} />
            <input className={`${input} sm:w-48`} placeholder="Author (optional)" aria-label="Author" maxLength={256} value={author} onChange={(e) => setAuthor(e.target.value)} />
            <button type="submit" className={primary} disabled={!title.trim() || add.isPending}>{shelf === 'family' ? 'Add to library' : 'Add to my list'}</button>
          </form>
        )}
        {books && books.length === 0 && (
          <p className="text-sm text-gray-500">{shelf === 'family' ? 'The family library is empty.' : 'No books yet.'}</p>
        )}
        <ul className="space-y-2">
          {(books ?? []).map((b) => {
            const next = NEXT[b.status]
            return (
              <li key={b.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className={`font-medium ${b.status === 'finished' ? 'text-gray-400' : 'text-white'}`}>{b.title}</p>
                  <p className="text-xs text-gray-500">
                    {b.author && <>{b.author} · </>}{STATUS[b.status]}
                    {b.reader_id && b.owner_id === null && <> · {nameOf(members, b.reader_id)}</>}
                    {shelf === 'everyone' && <> · {whose(b)}</>}
                  </p>
                </div>
                {mayChange(b) && next && (
                  <button className={next === 'finished' ? primary : subtle} disabled={update.isPending}
                    aria-label={`${NEXT_LABEL[b.status]}: ${b.title}`}
                    onClick={() => run(() => update.mutateAsync({ id: b.id, status: next }), "Couldn't update the book")}>{NEXT_LABEL[b.status]}</button>
                )}
                {mayChange(b) && b.status !== 'want_to_read' && (
                  <button className={subtle} aria-label={`${b.owner_id ? 'Move back' : 'Back on the shelf'}: ${b.title}`}
                    onClick={() => run(() => update.mutateAsync({ id: b.id, status: 'want_to_read' }), "Couldn't update the book")}>
                    {b.owner_id ? 'Not started' : 'Back on the shelf'}</button>
                )}
                {mayEdit(b) && (
                  <button className={subtle} aria-label={`Remove: ${b.title}`}
                    onClick={() => window.confirm(`Remove "${b.title}"?`) && run(() => del.mutateAsync(b.id), "Couldn't remove the book")}>✕</button>
                )}
              </li>
            )
          })}
        </ul>
        <p className="mt-6 text-xs text-gray-500">Finishing a book earns its reader 50 points, once per book.</p>
      </div>
    </div>
  )
}
