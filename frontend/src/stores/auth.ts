import { create } from 'zustand'
import { api } from '@/lib/api'

interface User {
  id: string
  email: string
  name: string
}

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  clearError: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      const data = await api.login(email, password)
      const token = data.access_token
      localStorage.setItem('token', token)
      set({ user: { ...data.user, id: String(data.user.id) }, token, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      set({ isLoading: false, error: message })
      throw err
    }
  },

  register: async (email: string, password: string, name: string) => {
    set({ isLoading: true, error: null })
    try {
      const data = await api.register(email, password, name)
      const token = data.access_token
      localStorage.setItem('token', token)
      set({ user: { ...data.user, id: String(data.user.id) }, token, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed'
      set({ isLoading: false, error: message })
      throw err
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null, error: null })
  },

  clearError: () => set({ error: null }),

  checkAuth: async () => {
    const { token } = get()
    if (!token) {
      set({ user: null, isLoading: false })
      return
    }
    set({ isLoading: true })
    try {
      const user = await api.getMe()
      set({ user, isLoading: false, error: null })
    } catch {
      localStorage.removeItem('token')
      set({ user: null, token: null, isLoading: false, error: null })
    }
  },
}))
