import { useWallNotes } from '../api/wall'
import NoteBoardCanvas from '../components/NoteBoardCanvas'

export default function WallNotes() {
  const { data: board } = useWallNotes()
  if (!board) return <p className="text-lg text-slate-400">Loading notes…</p>
  if (board.items.length === 0) return <p className="text-lg text-slate-400">Nothing on the family board yet.</p>
  return <NoteBoardCanvas board={board} imageUrl={(id) => `/api/wall/media/${id}/wall`} readOnly />
}
