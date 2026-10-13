import type { Member } from '../../api/chores'

export const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white disabled:opacity-50'
export const button = 'rounded px-3 py-1 text-sm font-medium disabled:opacity-50'
export const primary = `${button} bg-primary text-white hover:bg-primary-dark`
export const subtle = `${button} bg-gray-800 text-gray-200 hover:bg-gray-700`

export function nameOf(members: Member[] | undefined, id: string | null | undefined, fallback = 'Anyone'): string {
  if (!id) return fallback
  return members?.find((m) => m.id === id)?.display_name ?? 'Someone'
}
