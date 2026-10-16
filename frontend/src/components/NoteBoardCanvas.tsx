import type { NoteBoard, NoteItemUnion } from '../api/notes'

export type { NoteBoard, NoteItemUnion }

export default function NoteBoardCanvas({ board, imageUrl, readOnly = false }: { board: NoteBoard; imageUrl: (id: string) => string; readOnly?: boolean }) {
  return <svg viewBox="0 0 1000 700" className="h-auto w-full rounded-xl bg-amber-50" aria-label={readOnly ? 'Family notes board' : undefined}>
    {board.items.map((item) => <Item key={item.id} item={item} imageUrl={imageUrl} />)}
  </svg>
}

function Item({ item, imageUrl }: { item: NoteItemUnion; imageUrl: (id: string) => string }) {
  if (item.type === 'note') return <g transform={`translate(${item.x} ${item.y})`}><rect width={item.width} height={item.height} rx="12" fill={item.color} /><text x="16" y="30" fill="#1e293b" fontSize="24">{item.text}</text></g>
  if (item.type === 'sticker') return <text x={item.x} y={item.y + item.size} fontSize={item.size} aria-label={`Sticker: ${item.emoji}`}>{item.emoji}</text>
  if (item.type === 'image') return <image href={imageUrl(item.media_id)} x={item.x} y={item.y} width={item.width} height={item.height} preserveAspectRatio="xMidYMid slice" role="img" aria-label="Board photo" />
  return <polyline points={item.points.map((point) => `${point.x},${point.y}`).join(' ')} fill="none" stroke={item.color} strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
}
