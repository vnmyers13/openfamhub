import { create } from 'zustand'

export interface User {
  id: string
  display_name: string
  role: string
  color_hex: string
  ui_mode: string
  avatar_type: string | null
  avatar_value: string | null
  family_id: string
  /** "pin" or "password": how this browser signed in. */
  auth_method?: string | null
  /** Whether admin actions are allowed right now (password session or recent unlock). */
  admin_unlocked?: boolean
}

interface AuthStore {
  user: User | null
  setUser: (user: User) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}))
