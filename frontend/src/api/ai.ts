import { apiClient } from './client'

export type DraftKind = 'event' | 'chore' | 'todo'
export type DraftAction = { kind: DraftKind; operation: 'create' | 'update'; target_id?: string; fields: Record<string, unknown> }
export type Draft = { action: DraftAction; summary: string }

export async function createAiDraft(request: string, audio_base64?: string): Promise<Draft> {
  return (await apiClient.post('/ai/draft', { request, ...(audio_base64 ? { audio_base64 } : {}) })).data as Draft
}

/** The model never receives a write capability: confirmed actions use normal APIs. */
export async function confirmAiDraft(draft: Draft): Promise<void> {
  const { kind, operation, target_id, fields } = draft.action
  const root = kind === 'event' ? '/calendar/events' : kind === 'chore' ? '/chores/templates' : '/todos'
  if (operation === 'create') await apiClient.post(root, fields)
  else await apiClient.patch(`${root}/${target_id}`, fields)
}
