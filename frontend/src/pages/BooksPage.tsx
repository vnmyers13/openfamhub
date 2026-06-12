import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

interface Book {
  id: string
  title: string
  author?: string
  status: 'reading' | 'want_to_read' | 'completed'
  notes?: string
  created_by_id: string
  created_at: string
  updated_at: string
}

export default function BooksPage() {
  const [activeTab, setActiveTab] = useState<'my' | 'shared'>('my')
  const [showForm, setShowForm] = useState(false)
  const [formTitle, setFormTitle] = useState('')
  const [formAuthor, setFormAuthor] = useState('')
  const [formStatus, setFormStatus] = useState<'reading' | 'want_to_read' | 'completed'>('want_to_read')
  const [formNotes, setFormNotes] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editAuthor, setEditAuthor] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const user = useAuthStore((s) => s.user)
  const queryClient = useQueryClient()

  const { data: books = [] } = useQuery({
    queryKey: ['books', activeTab === 'my' ? 'my' : 'shared'],
    queryFn: async () => {
      const res = await api.get(activeTab === 'my' ? '/books/' : '/books/shared')
      return res.data as Book[]
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: { title: string; author?: string; status: string; notes?: string }) =>
      api.post('/books/', data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setShowForm(false)
      setFormTitle('')
      setFormAuthor('')
      setFormStatus('want_to_read')
      setFormNotes('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title?: string; author?: string; notes?: string } }) =>
      api.patch(`/books/${id}`, data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setEditingId(null)
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/books/${id}/status`, { status }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/books/${id}`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
  })

  const groupedBooks = books.reduce((acc, book) => {
    if (!acc[book.status]) acc[book.status] = []
    acc[book.status].push(book)
    return acc
  }, {} as Record<string, Book[]>)

  const statusLabels: Record<string, string> = {
    reading: '📖 Currently Reading',
    want_to_read: '📚 Want to Read',
    completed: '✅ Completed',
  }

  const isOwner = (book: Book) => user && book.created_by_id === user.id
  const isAdmin = user?.role === 'admin'

  const handleCreate = () => {
    if (!formTitle.trim()) return
    createMutation.mutate({ title: formTitle, author: formAuthor || undefined, status: formStatus, notes: formNotes || undefined })
  }

  const handleEdit = (book: Book) => {
    setEditingId(book.id)
    setEditTitle(book.title)
    setEditAuthor(book.author || '')
    setEditNotes(book.notes || '')
  }

  const handleSaveEdit = () => {
    if (!editingId || !editTitle.trim()) return
    updateMutation.mutate({ id: editingId, data: { title: editTitle, author: editAuthor || undefined, notes: editNotes || undefined } })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Books</h1>
        {activeTab === 'my' && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            {showForm ? 'Cancel' : '+ Add Book'}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('my')}
          className={`px-4 py-2 rounded-lg transition ${
            activeTab === 'my' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          My Books
        </button>
        <button
          onClick={() => setActiveTab('shared')}
          className={`px-4 py-2 rounded-lg transition ${
            activeTab === 'shared' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          Family Library
        </button>
      </div>

      {/* Add Book Form */}
      {showForm && activeTab === 'my' && (
        <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Add a Book</h2>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Book title *"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              placeholder="Author (optional)"
              value={formAuthor}
              onChange={(e) => setFormAuthor(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <select
              value={formStatus}
              onChange={(e) => setFormStatus(e.target.value as 'reading' | 'want_to_read' | 'completed')}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="want_to_read">Want to Read</option>
              <option value="reading">Currently Reading</option>
              <option value="completed">Completed</option>
            </select>
            <textarea
              placeholder="Notes (optional)"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
              rows={2}
            />
            <button
              onClick={handleCreate}
              disabled={createMutation.isPending}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
            >
              {createMutation.isPending ? 'Adding...' : 'Add Book'}
            </button>
          </div>
        </div>
      )}

      {/* Books by Status */}
      {Object.keys(groupedBooks).length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No books yet</p>
          {activeTab === 'my' && (
            <p className="mt-2">Click "+ Add Book" to get started!</p>
          )}
        </div>
      ) : (
        Object.entries(groupedBooks).map(([status, books]) => (
          <div key={status} className="space-y-3">
            <h2 className="text-lg font-semibold text-white">{statusLabels[status]}</h2>
            {books.map((book) => (
              <div key={book.id} className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 space-y-2">
                {editingId === book.id ? (
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                    <input
                      type="text"
                      value={editAuthor}
                      onChange={(e) => setEditAuthor(e.target.value)}
                      placeholder="Author"
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                    <textarea
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      placeholder="Notes"
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleSaveEdit}
                        disabled={updateMutation.isPending}
                        className="px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-1 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="text-white font-medium">{book.title}</h3>
                        {book.author && <p className="text-sm text-gray-400">by {book.author}</p>}
                        {book.notes && <p className="text-sm text-gray-300 mt-1">{book.notes}</p>}
                        {activeTab === 'shared' && (
                          <p className="text-xs text-gray-500 mt-1">Added by {book.created_by_id}</p>
                        )}
                      </div>
                      <div className="flex gap-1">
                        {isOwner(book) && (
                          <>
                            <button
                              onClick={() => handleEdit(book)}
                              className="px-2 py-1 text-xs text-blue-400 hover:text-blue-300"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteMutation.mutate(book.id)}
                              className="px-2 py-1 text-xs text-red-400 hover:text-red-300"
                            >
                              Delete
                            </button>
                          </>
                        )}
                        {isAdmin && activeTab === 'shared' && isOwner(book) === false && (
                          <>
                            <button
                              onClick={() => handleEdit(book)}
                              className="px-2 py-1 text-xs text-blue-400 hover:text-blue-300"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteMutation.mutate(book.id)}
                              className="px-2 py-1 text-xs text-red-400 hover:text-red-300"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                    {isOwner(book) && (
                      <select
                        value={book.status}
                        onChange={(e) => statusMutation.mutate({ id: book.id, status: e.target.value })}
                        className="text-xs px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                      >
                        <option value="want_to_read">Want to Read</option>
                        <option value="reading">Currently Reading</option>
                        <option value="completed">Completed</option>
                      </select>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  )
}
