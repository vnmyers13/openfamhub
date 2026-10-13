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

/** Fraction sent (0-1) from an upload progress event, or null when the size isn't known. */
export function uploadFraction(e: { loaded: number; total?: number; progress?: number }): number | null {
  if (typeof e.progress === 'number') return Math.min(1, Math.max(0, e.progress))
  return e.total ? Math.min(1, e.loaded / e.total) : null
}

/**
 * Upload one file as the raw request body (the server streams it to disk).
 * `onProgress` gets the fraction sent, for the progress bar on large videos.
 */
export function useUploadMedia() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, onProgress }: { file: File; onProgress?: (fraction: number | null) => void }) =>
      (await apiClient.post('/media', file, {
        headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) },
        timeout: 0,
        onUploadProgress: onProgress ? (e) => onProgress(uploadFraction(e)) : undefined,
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
