import { create } from 'zustand'
import { api } from '@/lib/api'

export interface ToolCall {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  duration?: number
  error?: string
  resultPreview?: string
}

export interface PlanStep {
  id: number
  tool_name: string
  description: string
  params?: Record<string, unknown>
  status: 'pending' | 'running' | 'completed' | 'failed'
}

export interface StepResult {
  step: number
  tool: string
  status: string
  result_preview?: string
  error?: string
  duration?: number
}

export interface AgentState {
  stage: 'router' | 'research' | 'plan' | 'execute' | 'synthesize' | 'done'
  plan: PlanStep[]
  current_step: number
  step_results: StepResult[]
  research_notes: string
  waiting_for: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  toolCalls?: ToolCall[]
  files?: { name: string; size: number; type: string }[]
  thinking?: string[]
  createdAt: number
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
}

interface ChatState {
  conversations: Conversation[]
  currentId: string | null
  messages: ChatMessage[]
  streaming: boolean
  sidebarOpen: boolean
  detailOpen: boolean

  // Agent state (full snapshot from server)
  agentState: AgentState | null

  // Model selection
  selectedModel: string  // model id (e.g. "deepseek", "kuaPao", "miniMax")
  availableModels: Array<{ id: string; name: string; provider: string; model: string; description: string; available: boolean }>

  // Actions
  newConversation: () => void
  selectConversation: (id: string) => void
  deleteConversation: (id: string) => void
  addMessage: (msg: Omit<ChatMessage, 'id' | 'createdAt'>) => void
  updateLastAssistant: (updates: Partial<ChatMessage>) => void
  addToolCall: (toolCall: ToolCall) => void
  updateToolCall: (id: string, updates: Partial<ToolCall>) => void
  setStreaming: (v: boolean) => void
  setAgentState: (state: AgentState) => void
  toggleSidebar: () => void
  toggleDetail: () => void
  setSelectedModel: (modelId: string) => void
  fetchModels: () => Promise<void>

  // Backend sync actions
  syncConversations: () => Promise<void>
  setCurrentId: (id: string) => Promise<void>
  syncNewConversation: () => Promise<string>
  syncDeleteConversation: (id: string) => Promise<void>
  restoreSession: () => Promise<void>
  updateConversationTitle: (id: string, title: string) => void
}

let msgId = 0
let convId = 0

function genId() {
  return `${Date.now()}-${++msgId}`
}

const CURRENT_ID_KEY = 'currentConversationId'

let _syncing = false

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentId: null,
  messages: [],
  streaming: false,
  sidebarOpen: true,
  detailOpen: true,
  agentState: null,
  selectedModel: (localStorage.getItem('selectedModel') as string) || 'deepseek',
  availableModels: [],

  newConversation: () => {
    const id = `conv-${++convId}`
    set((s) => ({
      conversations: [
        { id, title: 'New Conversation', messages: [], createdAt: Date.now() },
        ...s.conversations,
      ],
      currentId: id,
      messages: [],
      agentState: null,
    }))
  },

  selectConversation: (id) => {
    const conv = get().conversations.find((c) => c.id === id)
    if (conv) {
      set({ currentId: id, messages: conv.messages, agentState: null })
    }
  },

  deleteConversation: (id) => {
    set((s) => {
      const conversations = s.conversations.filter((c) => c.id !== id)
      const currentId = s.currentId === id ? null : s.currentId
      const messages = currentId
        ? conversations.find((c) => c.id === currentId)?.messages || []
        : []
      return { conversations, currentId, messages }
    })
  },

  addMessage: (msg) => {
    const full: ChatMessage = { ...msg, id: genId(), createdAt: Date.now() }
    set((s) => {
      const messages = [...s.messages, full]

      // Also update the message list in the current conversation
      const conversations = s.conversations.map((c) => {
        if (c.id === s.currentId) {
          return { ...c, messages }
        }
        return c
      })

      return { messages, conversations }
    })
  },

  updateLastAssistant: (updates) => {
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, ...updates }
      }

      // Also update the current conversation's messages
      const conversations = s.conversations.map((c) => {
        if (c.id === s.currentId) {
          return { ...c, messages }
        }
        return c
      })

      return { messages, conversations }
    })
  },

  addToolCall: (tc) => {
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last && last.role === 'assistant') {
        const existing = last.toolCalls || []
        messages[messages.length - 1] = {
          ...last,
          toolCalls: [...existing, tc],
        }
      }
      return { messages }
    })
  },

  updateToolCall: (id, updates) => {
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last?.toolCalls) {
        messages[messages.length - 1] = {
          ...last,
          toolCalls: last.toolCalls.map((tc) =>
            tc.id === id ? { ...tc, ...updates } : tc
          ),
        }
      }
      return { messages }
    })
  },

  setStreaming: (v) => set({ streaming: v }),
  setAgentState: (state) => set({ agentState: state }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleDetail: () => set((s) => ({ detailOpen: !s.detailOpen })),

  updateConversationTitle: (id: string, title: string) => {
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }))
  },

  setSelectedModel: (modelId: string) => {
    localStorage.setItem('selectedModel', modelId)
    set({ selectedModel: modelId })
  },

  fetchModels: async () => {
    try {
      const models = await api.getModels()
      set({ availableModels: models })
    } catch (err) {
      console.error('Failed to fetch models:', err)
    }
  },

  // --- Backend sync actions ---

  syncConversations: async () => {
    if (_syncing) return  // prevent concurrent sync calls
    _syncing = true
    try {
      const data = await api.getConversations()
      const seen = new Set<string>()
      const conversations: Conversation[] = []
      for (const c of data) {
        if (seen.has(c.id)) continue
        seen.add(c.id)
        conversations.push({
          id: c.id,
          title: c.title || 'Untitled',
          messages: (c.messages || []).map((m: any) => ({
            id: m.id || genId(),
            role: m.role,
            content: m.content || '',
            toolCalls: m.tool_calls || m.toolCalls || [],
            files: m.files || [],
            thinking: m.thinking || [],
            createdAt: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
          })),
          createdAt: c.created_at ? new Date(c.created_at).getTime() : Date.now(),
        })
      }
      set({ conversations })
    } catch (err) {
      console.error('Failed to sync conversations:', err)
    } finally {
      _syncing = false
    }
  },

  setCurrentId: async (id: string) => {
    localStorage.setItem(CURRENT_ID_KEY, id)
    try {
      const data = await api.getConversation(id)
      const messages: ChatMessage[] = (data.messages || []).map((m: any) => ({
        id: m.id || genId(),
        role: m.role,
        content: m.content || '',
        toolCalls: m.tool_calls || m.toolCalls || [],
        files: m.files || [],
        thinking: m.thinking || [],
        createdAt: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
      }))

      // Update or add this conversation in the list
      set((s) => {
        const existing = s.conversations.find((c) => c.id === id)
        const conversations = existing
          ? s.conversations.map((c) =>
              c.id === id ? { ...c, messages, title: data.title || c.title } : c
            )
          : [
              {
                id,
                title: data.title || 'Untitled',
                messages,
                createdAt: data.created_at
                  ? new Date(data.created_at).getTime()
                  : Date.now(),
              },
              ...s.conversations,
            ]
        return { currentId: id, messages, conversations, agentState: null }
      })
    } catch (err) {
      console.error('Failed to load conversation:', err)
    }
  },

  syncNewConversation: async () => {
    try {
      const data = await api.createConversation()
      const conv: Conversation = {
        id: data.id,
        title: data.title || 'New Conversation',
        messages: [],
        createdAt: data.created_at ? new Date(data.created_at).getTime() : Date.now(),
      }
      set((s) => ({
        conversations: [conv, ...s.conversations],
        currentId: conv.id,
        messages: [],
        agentState: null,
      }))
      return conv.id
    } catch (err) {
      console.error('Failed to create conversation:', err)
      // Fallback: create a local-only conversation
      const id = `conv-${++convId}`
      set((s) => ({
        conversations: [
          { id, title: 'New Conversation', messages: [], createdAt: Date.now() },
          ...s.conversations,
        ],
        currentId: id,
        messages: [],
        agentState: null,
      }))
      return id
    }
  },

  syncDeleteConversation: async (id: string) => {
    // Optimistic: remove from UI immediately
    const previousState = get()
    set((s) => {
      const conversations = s.conversations.filter((c) => c.id !== id)
      const currentId = s.currentId === id ? null : s.currentId
      const messages = currentId
        ? conversations.find((c) => c.id === currentId)?.messages || []
        : []
      return { conversations, currentId, messages }
    })

    try {
      await api.deleteConversation(id)
    } catch (err) {
      console.error('Failed to delete conversation:', err)
      // Revert on failure
      set({
        conversations: previousState.conversations,
        currentId: previousState.currentId,
        messages: previousState.messages,
      })
    }
  },

  restoreSession: async () => {
    // Load conversations from backend (deduped, concurrent-safe)
    await get().syncConversations()

    // Restore last selected conversation if saved
    const savedId = localStorage.getItem(CURRENT_ID_KEY)
    if (savedId) {
      try {
        await get().setCurrentId(savedId)
      } catch {
        localStorage.removeItem(CURRENT_ID_KEY)
      }
    }
  },
}))
