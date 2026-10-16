import { useState } from 'react'
import NoteBoardCanvas from '../components/NoteBoardCanvas'
import { useNoteBoard, useSaveNoteBoard, type NoteItemUnion } from '../api/notes'
import { useAuthStore } from '../stores/auth'
import { useMedia } from '../api/media'

export default function NotesPage() {
  const { data: board, isLoading } = useNoteBoard()
  const save = useSaveNoteBoard()
  const user = useAuthStore((state) => state.user)
  const { data: media = [] } = useMedia()
  const [items, setItems] = useState<NoteItemUnion[] | null>(null)
  const [title, setTitle] = useState<string | null>(null)
  const [photoId, setPhotoId] = useState('')
  const [drawing, setDrawing] = useState(false)
  const editable = user?.role !== 'viewer'
  const shown = board ? { ...board, title: title ?? board.title, items: items ?? board.items } : undefined
  if (isLoading || !shown) return <div className="min-h-screen bg-gray-950 p-6 text-slate-400">Loading notes…</div>
  const addNote = () => setItems([...shown.items, { id: crypto.randomUUID(), type: 'note', x: 80, y: 80, width: 240, height: 120, color: '#fef08a', text: 'New note' }])
  const addSticker = () => setItems([...shown.items, { id: crypto.randomUUID(), type: 'sticker', x: 360, y: 140, size: 64, emoji: '⭐' }])
  const addSketch = () => setDrawing((value) => !value)
  const addPhoto = () => { const id = photoId || media.find((item) => item.kind === 'photo' && item.status === 'ready')?.id; if (id) setItems([...shown.items, { id: crypto.randomUUID(), type: 'image', x: 500, y: 100, width: 280, height: 180, media_id: id }]) }
  const exportPng = async () => {
    const svg = document.querySelector('svg[aria-label="Family notes board"], svg.h-auto')
    if (!svg) return
    const copy = svg.cloneNode(true) as SVGElement
    await Promise.all(Array.from(copy.querySelectorAll('image')).map(async (node) => {
      const source = node.getAttribute('href'); if (!source) return
      const blob = await fetch(source, { credentials: 'same-origin' }).then((res) => res.blob())
      await new Promise<void>((resolve) => { const reader = new FileReader(); reader.onload = () => { node.setAttribute('href', String(reader.result)); resolve() }; reader.readAsDataURL(blob) })
    }))
    const image = new Image(); const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml' }))
    image.onload = () => { const canvas = document.createElement('canvas'); canvas.width = 1000; canvas.height = 700; canvas.getContext('2d')?.drawImage(image, 0, 0); canvas.toBlob((blob) => { if (blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'family-notes.png'; a.click() } URL.revokeObjectURL(url) }) }
    image.src = url
  }
  return <div className="min-h-screen bg-gray-950 p-6 text-white"><div className="mx-auto max-w-5xl space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">{editable ? <input aria-label="Board title" value={shown.title} onChange={(e) => setTitle(e.target.value)} className="rounded bg-slate-800 px-3 py-2 text-2xl font-bold" /> : <h1 className="text-2xl font-bold">{shown.title}</h1>}<div className="flex gap-2">
      {editable && <button onClick={addNote} className="rounded bg-slate-700 px-3 py-2">Add note</button>}
      {editable && <button onClick={addSticker} className="rounded bg-slate-700 px-3 py-2">Add sticker</button>}
      {editable && <button onClick={addSketch} className="rounded bg-slate-700 px-3 py-2">{drawing ? 'Finish sketch' : 'Add sketch'}</button>}
      {editable && <button onClick={addPhoto} disabled={!media.some((item) => item.kind === 'photo' && item.status === 'ready')} className="rounded bg-slate-700 px-3 py-2 disabled:opacity-50">Add photo</button>}
      {editable && <select aria-label="Board photo" value={photoId} onChange={(e) => setPhotoId(e.target.value)} className="rounded bg-slate-800 px-2"><option value="">Choose photo</option>{media.filter((item) => item.kind === 'photo' && item.status === 'ready').map((item) => <option key={item.id} value={item.id}>{item.original_name}</option>)}</select>}
      {editable && <button onClick={() => save.mutate({ title: shown.title, items: shown.items })} className="rounded bg-primary px-3 py-2">Save board</button>}
      <button onClick={exportPng} className="rounded bg-slate-700 px-3 py-2">Export PNG</button>
    </div></div>
    <NoteBoardCanvas board={shown} imageUrl={(id) => `/api/media/${id}/wall`} readOnly={!editable} onDraw={drawing ? (points) => setItems([...shown.items, { id: crypto.randomUUID(), type: 'stroke', color: '#2563eb', points }]) : undefined} />
  </div></div>
}
