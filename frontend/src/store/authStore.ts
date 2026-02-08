/**
 * Auth Store - Global authentication state management
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
  id: string
  email: string
  full_name: string | null
  role: 'owner' | 'admin' | 'member' | 'viewer'
  organization_id: string
  organization_name: string
  is_active: boolean
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

interface AuthState {
  user: User | null
  tokens: AuthTokens | null
  isAuthenticated: boolean
  isLoading: boolean
  tokenExpiresAt: number | null // epoch ms when access token expires

  // Actions
  setAuth: (user: User, tokens: AuthTokens) => void
  logout: () => void
  setLoading: (loading: boolean) => void
  updateUser: (user: Partial<User>) => void
  isTokenExpired: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: true,
      tokenExpiresAt: null,

      setAuth: (user, tokens) => set({
        user,
        tokens,
        isAuthenticated: true,
        isLoading: false,
        // Store absolute expiry time (subtract 30s buffer for clock skew)
        tokenExpiresAt: Date.now() + (tokens.expires_in - 30) * 1000,
      }),

      logout: () => set({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        tokenExpiresAt: null,
      }),

      setLoading: (loading) => set({ isLoading: loading }),

      updateUser: (updates) => set((state) => ({
        user: state.user ? { ...state.user, ...updates } : null,
      })),

      isTokenExpired: () => {
        const { tokenExpiresAt } = get()
        if (!tokenExpiresAt) return true
        return Date.now() >= tokenExpiresAt
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
        tokenExpiresAt: state.tokenExpiresAt,
      }),
    }
  )
)

// Helper to get auth header
export function getAuthHeader(): Record<string, string> {
  const tokens = useAuthStore.getState().tokens
  if (tokens?.access_token) {
    return { Authorization: `Bearer ${tokens.access_token}` }
  }
  return {}
}
