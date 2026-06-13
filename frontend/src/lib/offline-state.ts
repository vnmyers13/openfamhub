import { create } from 'zustand'
import type { PendingOperation } from './idb'

export type SyncStatus = 'online' | 'offline' | 'syncing' | 'conflict'

interface OfflineState {
  status: SyncStatus
  pendingCount: number
  syncingEntity: string | null
  conflict: {
    operation: PendingOperation
    serverData: Record<string, unknown>
    localData: Record<string, unknown>
  } | null
  setStatus: (status: SyncStatus) => void
  setPendingCount: (count: number) => void
  setSyncingEntity: (entity: string | null) => void
  setConflict: (conflict: OfflineState['conflict']) => void
  clearConflict: () => void
  incrementPending: () => void
  decrementPending: () => void
}

export const useOfflineStore = create<OfflineState>((set) => ({
  status: 'online',
  pendingCount: 0,
  syncingEntity: null,
  conflict: null,
  setStatus: (status) => set({ status }),
  setPendingCount: (count) => set({ pendingCount: count }),
  setSyncingEntity: (entity) => set({ syncingEntity: entity }),
  setConflict: (conflict) => set({ status: 'conflict', conflict }),
  clearConflict: () => set({ status: 'online', conflict: null }),
  incrementPending: () => set((state) => ({ pendingCount: state.pendingCount + 1 })),
  decrementPending: () => set((state) => ({ pendingCount: Math.max(0, state.pendingCount - 1) })),
}))
