import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export type Point = { x: number; y: number }
export type NoteItem = { id: string; type: 'note'; x: number; y: number; width: number; height: number; color: string; text: string }
export type StickerItem = { id: string; type: 'sticker'; x: number; y: number; size: number; emoji: string }
export type ImageItem = { id: string; type: 'image'; x: number; y: number; width: number; height: number; media_id: string }
export type StrokeItem = { id: string; type: 'stroke'; color: string; points: Point[] }
export type NoteItemUnion = NoteItem | StickerItem | ImageItem | StrokeItem
export type NoteBoard = { id: string; title: string; items: NoteItemUnion[]; updated_by: string | null }

export function useNoteBoard() {
  return useQuery({ queryKey: ['notes', 'board'], queryFn: async () => (await apiClient.get('/notes/board')).data as NoteBoard })
}

export function useSaveNoteBoard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ title, items }: Pick<NoteBoard, 'title' | 'items'>) => (await apiClient.put('/notes/board', { title, items })).data as NoteBoard,
    onSuccess: (board) => qc.setQueryData(['notes', 'board'], board),
  })
}
