import { create } from 'zustand'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
}

export interface UIState {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
  /** Whether conversations are being fetched from the backend */
  conversationsLoading: boolean
  setConversationsLoading: (v: boolean) => void
  /** SSE stream error message, null when no error */
  streamError: string | null
  setStreamError: (msg: string | null) => void
  /** Network offline state */
  isOffline: boolean
  setIsOffline: (v: boolean) => void
}

let toastId = 0

export const useUIStore = create<UIState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = `toast-${++toastId}-${Date.now()}`
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }))
  },
  removeToast: (id) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
  },
  conversationsLoading: false,
  setConversationsLoading: (v) => set({ conversationsLoading: v }),
  streamError: null,
  setStreamError: (msg) => set({ streamError: msg }),
  isOffline: false,
  setIsOffline: (v) => set({ isOffline: v }),
}))
