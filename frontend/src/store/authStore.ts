import { create } from 'zustand'

export type UserRole = 'staff' | 'trainer' | 'manager' | 'admin'

export interface AuthUser {
  id: number
  email: string
  first_name: string
  last_name: string
  role: UserRole
  department: string | null
  mfa_enabled: boolean
}

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  isAuthenticated: boolean
  setAuth: (user: AuthUser, token: string) => void
  setToken: (token: string) => void
  logout: () => void
}

function _loadStoredAuth(): Pick<AuthState, 'user' | 'accessToken' | 'isAuthenticated'> {
  try {
    const raw = sessionStorage.getItem('forge_auth')
    if (!raw) return { user: null, accessToken: null, isAuthenticated: false }
    const { user, accessToken } = JSON.parse(raw)
    if (!user || !accessToken) return { user: null, accessToken: null, isAuthenticated: false }
    return { user, accessToken, isAuthenticated: true }
  } catch {
    return { user: null, accessToken: null, isAuthenticated: false }
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  ..._loadStoredAuth(),

  setAuth: (user, token) => {
    sessionStorage.setItem('forge_auth', JSON.stringify({ user, accessToken: token }))
    set({ user, accessToken: token, isAuthenticated: true })
  },

  setToken: (token) => {
    try {
      const raw = sessionStorage.getItem('forge_auth')
      if (raw) {
        const parsed = JSON.parse(raw)
        sessionStorage.setItem('forge_auth', JSON.stringify({ ...parsed, accessToken: token }))
      }
    } catch { /* ignore */ }
    set({ accessToken: token })
  },

  logout: () => {
    sessionStorage.removeItem('forge_auth')
    set({ user: null, accessToken: null, isAuthenticated: false })
  },
}))
