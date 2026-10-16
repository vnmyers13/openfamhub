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
  const [items, setItems] = useState<NoteItemUnion[]>([])
  const editable = user?.role !== 'viewer'
  const shown = board ? { ...board, items: items.length ? items : board.items } : undefined
  if (isLoading || !shown) return <div className="min-h-screen bg-gray-950 p-6 text-slate-400">Loading notes…</div>
  const addNote = () => setItems([...shown.items, { id: crypto.randomUUID(), type: 'note', x: 80, y: 80, width: 240, height: 120, color: '#fef08a', text: 'New note' }])
  const addSticker = () => setItems([...shown.items, { id: crypto.randomUUID(), type: 'sticker', x: 360, y: 140, size: 64, emoji: '⭐' }])
  const addSketch = () => setItems([...shown.items, { id: crypto.randomUUID(), type: 'stroke', color: '#2563eb', points: [{ x: 100, y: 400 }, { x: 220, y: 450 }, { x: 340, y: 390 }] }])
  const addPhoto = () => { const photo = media.find((item) => item.kind === 'photo' && item.status === 'ready'); if (photo) setItems([...shown.items, { id: crypto.randomUUID(), type: 'image', x: 500, y: 100, width: 280, height: 180, media_id: photo.id }]) }
  const exportPng = () => {
    const svg = document.querySelector('svg[aria-label="Family notes board"], svg.h-auto')
    if (!svg) return
    const image = new Image(); const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' }))
    image.onload = () => { const canvas = document.createElement('canvas'); canvas.width = 1000; canvas.height = 700; canvas.getContext('2d')?.drawImage(image, 0, 0); canvas.toBlob((blob) => { if (blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'family-notes.png'; a.click() } URL.revokeObjectURL(url) }) }
    image.src = url
  }
  return <div className="min-h-screen bg-gray-950 p-6 text-white"><div className="mx-auto max-w-5xl space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">{shown.title}</h1><div className="flex gap-2">
      {editable && <button onClick={addNote} className="rounded bg-slate-700 px-3 py-2">Add note</button>}
      {editable && <button onClick={addSticker} className="rounded bg-slate-700 px-3 py-2">Add sticker</button>}
      {editable && <button onClick={addSketch} className="rounded bg-slate-700 px-3 py-2">Add sketch</button>}
      {editable && <button onClick={addPhoto} disabled={!media.some((item) => item.kind === 'photo' && item.status === 'ready')} className="rounded bg-slate-700 px-3 py-2 disabled:opacity-50">Add photo</button>}
      {editable && <button onClick={() => save.mutate({ title: shown.title, items: shown.items })} className="rounded bg-primary px-3 py-2">Save board</button>}
      <button onClick={exportPng} className="rounded bg-slate-700 px-3 py-2">Export PNG</button>
    </div></div>
    <NoteBoardCanvas board={shown} imageUrl={(id) => `/api/media/${id}/wall`} readOnly={!editable} />
  </div></div>
}
