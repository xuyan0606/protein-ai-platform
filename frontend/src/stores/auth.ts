import { create } from 'zustand'
import { api, clearAuthTokens, getAccessToken, getRefreshToken, storeAuthTokens } from '@/lib/api'

const CURRENT_CONVERSATION_ID_KEY = 'currentConversationId'
const USER_SCOPED_RESET_EVENT = 'protein-ai:user-scoped-reset'
const DEV_AUTO_AUTH = import.meta.env.DEV
const DEV_USER: User = {
  id: 'dev-admin',
  email: 'admin@protein.local',
  name: 'Admin',
  role: 'admin',
}

function clearUserScopedClientState() {
  try {
    localStorage.removeItem(CURRENT_CONVERSATION_ID_KEY)
    for (let i = localStorage.length - 1; i >= 0; i -= 1) {
      const key = localStorage.key(i)
      if (key?.startsWith(`${CURRENT_CONVERSATION_ID_KEY}:`)) {
        localStorage.removeItem(key)
      }
    }
  } catch {
    // Ignore storage access errors; the chat store will still reset in memory.
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(USER_SCOPED_RESET_EVENT))
  }
}

async function clearServerAuthCookies() {
  try {
    await api.logout()
  } catch {
    // Best-effort: local tokens/state are still cleared below.
  }
}

interface User {
  id: string
  email: string
  name: string
  role?: string
}

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isLoading: boolean
  initialized: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: DEV_AUTO_AUTH ? DEV_USER : null,
  token: getAccessToken(),
  refreshToken: getRefreshToken(),
  isLoading: false,
  initialized: DEV_AUTO_AUTH,
  error: null,

  login: async (email: string, password: string) => {
    clearUserScopedClientState()
    clearAuthTokens()
    set({ isLoading: true, error: null })
    try {
      await clearServerAuthCookies()
      const data = await api.login(email, password)
      clearUserScopedClientState()
      storeAuthTokens(data.access_token, data.refresh_token)
      set({
        user: { ...data.user, id: String(data.user.id) },
        token: data.access_token,
        refreshToken: data.refresh_token,
        isLoading: false,
        initialized: true,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      set({ isLoading: false, error: message })
      throw err
    }
  },

  register: async (email: string, password: string, name: string) => {
    clearUserScopedClientState()
    clearAuthTokens()
    set({ isLoading: true, error: null })
    try {
      await clearServerAuthCookies()
      const data = await api.register(email, password, name)
      clearUserScopedClientState()
      storeAuthTokens(data.access_token, data.refresh_token)
      set({
        user: { ...data.user, id: String(data.user.id) },
        token: data.access_token,
        refreshToken: data.refresh_token,
        isLoading: false,
        initialized: true,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed'
      set({ isLoading: false, error: message })
      throw err
    }
  },

  logout: async () => {
    clearUserScopedClientState()
    clearAuthTokens()
    await clearServerAuthCookies()
    set({ user: null, token: null, refreshToken: null, error: null, isLoading: false, initialized: true })
  },

  clearError: () => set({ error: null }),

  checkAuth: async () => {
    if (DEV_AUTO_AUTH) {
      set({
        user: DEV_USER,
        isLoading: false,
        initialized: true,
        error: null,
      })
      return
    }
    set({ isLoading: true })
    try {
      const session = await api.getSession()
      if (!session.authenticated || !session.user) {
        const refreshToken = getRefreshToken()
        if (refreshToken) {
          try {
            const refreshed = await api.refreshSession()
            storeAuthTokens(refreshed.access_token, refreshed.refresh_token)
            set({
              user: { ...refreshed.user, id: String(refreshed.user.id) },
              token: refreshed.access_token,
              refreshToken: refreshed.refresh_token,
              isLoading: false,
              initialized: true,
              error: null,
            })
            return
          } catch {
            // Fall through to clearing local auth state.
          }
        }
        clearAuthTokens()
        set({ user: null, token: null, refreshToken: null, isLoading: false, initialized: true, error: null })
        return
      }

      let token = getAccessToken()
      let refreshToken = getRefreshToken()
      if (!token) {
        try {
          const refreshed = await api.refreshSession()
          storeAuthTokens(refreshed.access_token, refreshed.refresh_token)
          token = refreshed.access_token
          refreshToken = refreshed.refresh_token
        } catch {
          // Keep the recovered cookie-backed session even if token sync fails.
        }
      }

      set({
        user: { ...session.user, id: String(session.user.id) },
        token,
        refreshToken,
        isLoading: false,
        initialized: true,
        error: null,
      })
    } catch {
      clearAuthTokens()
      set({ user: null, token: null, refreshToken: null, isLoading: false, initialized: true, error: null })
    }
  },
}))

if (typeof window !== 'undefined') {
  const w = window as Window & { __proteinAiAuthSyncBound?: boolean }
  if (!w.__proteinAiAuthSyncBound) {
    w.__proteinAiAuthSyncBound = true

    window.addEventListener('protein-ai:auth-updated', () => {
      useAuthStore.setState({
        token: getAccessToken(),
        refreshToken: getRefreshToken(),
        initialized: true,
      })
    })

    window.addEventListener('protein-ai:auth-cleared', () => {
      useAuthStore.setState({
        user: null,
        token: null,
        refreshToken: null,
        isLoading: false,
        initialized: true,
        error: null,
      })
    })
  }
}
