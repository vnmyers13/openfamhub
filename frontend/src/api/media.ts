import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export interface MediaItem {
  id: string
  kind: 'photo' | 'video'
  status: 'processing' | 'ready' | 'failed'
  error: string | null
  original_name: string
  width: number | null
  height: number | null
  duration_s: number | null
  uploaded_by: string | null
  created_at: string | null
  wall_url: string
  thumb_url: string
}

export function useMedia() {
  return useQuery({
    queryKey: ['media'],
    queryFn: async () => (await apiClient.get('/media')).data as MediaItem[],
    // Poll while a video is converting.
    refetchInterval: (query) =>
      (query.state.data as MediaItem[] | undefined)?.some((i) => i.status === 'processing') ? 5000 : false,
  })
}

/** Upload one file as the raw request body (the server streams it to disk). */
export function useUploadMedia() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) =>
      (await apiClient.post('/media', file, {
        headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) },
        timeout: 0,
      })).data as MediaItem,
    onSettled: () => qc.invalidateQueries({ queryKey: ['media'] }),
  })
}

export function useDeleteMedia() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/media/${id}`)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['media'] }),
  })
}
