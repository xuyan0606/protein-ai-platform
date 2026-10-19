import { create } from 'zustand'
import { ApiError, api, isUnauthorizedError, normalizeFileDownloadUrl, type ApiAgentState, type ApiConversationMessage, type ApiRecord } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

export interface ToolCall {
  id: string
  name: string
  status: 'pending' | 'running' | 'submitted' | 'completed' | 'failed'
  duration?: number
  error?: string
  resultPreview?: string
  rawResult?: string
}

export interface PlanStep {
  id: number
  tool_name: string
  description: string
  params?: Record<string, unknown>
  status: 'pending' | 'running' | 'submitted' | 'completed' | 'failed'
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
  strategy_signature?: string | null
  task_fingerprint?: string | null
  next_action?: string | null
  artifacts?: Record<string, unknown>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  toolCalls?: ToolCall[]
  files?: { name: string; size: number; type: string; objectName?: string; downloadUrl?: string; analysisData?: unknown }[]
  thinking?: string[]
  createdAt: number
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt?: number
  messageCount: number
}

interface PublishedFile {
  file_id: string
  filename: string
  wiki_url: string | null
}

export interface RecentStrategyMemoryScope {
  type: string
  conversation_id?: string | number | null
  project_id?: string | null
}

interface ChatState {
  ownerUserId: string | null
  conversations: Conversation[]
  currentId: string | null
  messages: ChatMessage[]
  streaming: boolean
  sidebarOpen: boolean
  detailOpen: boolean

  // Agent state (full snapshot from server)
  agentState: AgentState | null
  strategyCheckpointHistory: ApiRecord[]
  recentStrategyMemory: ApiRecord[]
  recentStrategyMemoryScope: RecentStrategyMemoryScope | null
  recentStrategyMemoryLoading: boolean
  recentStrategyMemoryError: string | null

  // Last auto-published file info (from wiki auto-publish)
  lastPublishedFile: PublishedFile | null

  // Model selection
  selectedModel: string  // stable model id exposed by the backend
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
  clearAgentState: () => void
  toggleSidebar: () => void
  toggleDetail: () => void
  setSelectedModel: (modelId: string) => void
  fetchModels: () => Promise<void>

  // Backend sync actions
  syncConversations: () => Promise<void>
  setCurrentId: (id: string) => Promise<void>
  refreshRecentStrategyMemory: (conversationId: string) => Promise<void>
  syncNewConversation: () => Promise<string>
  syncDeleteConversation: (id: string) => Promise<void>
  syncRenameConversation: (id: string, title: string) => Promise<void>
  restoreSession: () => Promise<void>
  resetUserScopedState: (ownerUserId?: string | null) => void
  updateConversationTitle: (id: string, title: string) => void
  upsertConversationSnapshot: (id: string, title?: string) => void
}

let msgId = 0
let convId = 0
let _restoring = false
let _syncPromise: Promise<void> | null = null

function genId() {
  return `${Date.now()}-${++msgId}`
}

const CURRENT_ID_KEY = 'currentConversationId'
const CURRENT_ID_SCOPED_PREFIX = 'currentConversationId:'
const USER_SCOPED_RESET_EVENT = 'protein-ai:user-scoped-reset'

function currentConversationIdKeyForUser(userId?: string | null) {
  return userId ? `${CURRENT_ID_SCOPED_PREFIX}${userId}` : null
}

function getSavedConversationId(userId?: string | null) {
  const scopedKey = currentConversationIdKeyForUser(userId)
  return localStorage.getItem(CURRENT_ID_KEY) || (scopedKey ? localStorage.getItem(scopedKey) : null)
}

function storeSavedConversationId(id: string) {
  localStorage.setItem(CURRENT_ID_KEY, id)
  const userId = useAuthStore.getState().user?.id
  const scopedKey = currentConversationIdKeyForUser(userId ? String(userId) : null)
  if (scopedKey) {
    localStorage.setItem(scopedKey, id)
  }
}

function clearSavedConversationId(userId?: string | null) {
  localStorage.removeItem(CURRENT_ID_KEY)
  const scopedKey = currentConversationIdKeyForUser(userId)
  if (scopedKey) {
    localStorage.removeItem(scopedKey)
  }
}

function parseToolCalls(raw: unknown): ToolCall[] {
  if (!raw) return []
  if (Array.isArray(raw)) return raw as ToolCall[]
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) as ToolCall[] } catch { return [] }
  }
  return []
}

function normalizeMessageFiles(raw: unknown) {
  if (!Array.isArray(raw)) return []

  return raw.map((file) => {
    if (!file || typeof file !== 'object') return file
    const normalized = file as {
      objectName?: string
      object_name?: string
      downloadUrl?: string
      download_url?: string
    }
    const objectName = normalized.objectName || normalized.object_name
    const downloadUrl = normalizeFileDownloadUrl(
      normalized.downloadUrl || normalized.download_url,
      objectName
    )

    return {
      ...normalized,
      objectName,
      downloadUrl,
    }
  })
}

function normalizeAgentState(raw: ApiAgentState | null | undefined): AgentState | null {
  if (!raw) return null
  const plan = Array.isArray(raw.plan) ? raw.plan : []
  const stepResults = Array.isArray(raw.step_results) ? raw.step_results : []
  return {
    stage: raw.stage,
    plan: plan.map((step) => ({
      id: step.id,
      tool_name: step.tool_name,
      description: step.description,
      params: step.params,
      status: step.status,
    })),
    current_step: raw.current_step || 0,
    step_results: stepResults.map((item) => ({
      step: Number(item.step || 0),
      tool: String(item.tool || ''),
      status: String(item.status || ''),
      result_preview: typeof item.result_preview === 'string' ? item.result_preview : undefined,
      raw_result: typeof item.raw_result === 'string' ? item.raw_result : undefined,
      error: typeof item.error === 'string' ? item.error : undefined,
      duration: typeof item.duration === 'number' ? item.duration : undefined,
    })),
    research_notes: raw.research_notes || '',
    waiting_for: raw.waiting_for || null,
    strategy_signature: raw.strategy_signature || null,
    task_fingerprint: raw.task_fingerprint || null,
    next_action: raw.next_action || null,
    artifacts: raw.artifacts || {},
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  ownerUserId: null,
  conversations: [],
  currentId: null,
  messages: [],
  streaming: false,
  sidebarOpen: true,
  detailOpen: false,
  agentState: null,
  strategyCheckpointHistory: [],
  recentStrategyMemory: [],
  recentStrategyMemoryScope: null,
  recentStrategyMemoryLoading: false,
  recentStrategyMemoryError: null,
  lastPublishedFile: null,
  selectedModel: (() => {
    const saved = localStorage.getItem('selectedModel')
    if (saved === 'gpt55' && !localStorage.getItem('selectedModelExplicitChoice')) {
      localStorage.setItem('selectedModel', 'gpt6-sol')
      return 'gpt6-sol'
    }
    return saved || 'gpt6-sol'
  })(),
  availableModels: [],

  newConversation: () => {
    const id = `conv-${++convId}`
    set((s) => ({
      conversations: [
        { id, title: 'New Conversation', messages: [], createdAt: Date.now(), messageCount: 0 },
        ...s.conversations,
      ],
      currentId: id,
      messages: [],
      agentState: null,
      strategyCheckpointHistory: [],
      recentStrategyMemory: [],
      recentStrategyMemoryScope: null,
      recentStrategyMemoryLoading: false,
      recentStrategyMemoryError: null,
    }))
  },

  selectConversation: (id) => {
    const conv = get().conversations.find((c) => c.id === id)
    if (conv) {
      set({
        currentId: id,
        messages: conv.messages,
        agentState: null,
        strategyCheckpointHistory: [],
        recentStrategyMemory: [],
        recentStrategyMemoryScope: null,
        recentStrategyMemoryLoading: false,
        recentStrategyMemoryError: null,
      })
    }
  },

  deleteConversation: (id) => {
    set((s) => {
      const conversations = s.conversations.filter((c) => c.id !== id)
      const currentId = s.currentId === id ? null : s.currentId
      const messages = currentId
        ? conversations.find((c) => c.id === currentId)?.messages || []
        : []
      return {
        conversations,
        currentId,
        messages,
        ...(s.currentId === id
          ? {
              recentStrategyMemory: [],
              recentStrategyMemoryScope: null,
              recentStrategyMemoryLoading: false,
              recentStrategyMemoryError: null,
            }
          : {}),
      }
    })
  },

  addMessage: (msg) => {
    const full: ChatMessage = { ...msg, id: genId(), createdAt: Date.now() }
    set((s) => {
      const messages = [...s.messages, full]

      // Also update the message list in the current conversation
      const conversations = s.conversations.map((c) => {
        if (c.id === s.currentId) {
          return { ...c, messages, messageCount: messages.length, updatedAt: Date.now() }
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
          return { ...c, messages, messageCount: messages.length, updatedAt: Date.now() }
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
  clearAgentState: () => set({ agentState: null }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleDetail: () => set((s) => ({ detailOpen: !s.detailOpen })),

  updateConversationTitle: (id: string, title: string) => {
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }))
  },

  upsertConversationSnapshot: (id: string, title?: string) => {
    set((s) => {
      const existing = s.conversations.find((c) => c.id === id)
      const snapshot: Conversation = {
        id,
        title: title?.trim() || existing?.title || 'New Conversation',
        messages: s.messages,
        createdAt: existing?.createdAt || s.messages[0]?.createdAt || Date.now(),
        updatedAt: Date.now(),
        messageCount: s.messages.length,
      }

      if (existing) {
        return {
          currentId: id,
          conversations: s.conversations.map((c) => (c.id === id ? { ...c, ...snapshot } : c)),
        }
      }

      return {
        currentId: id,
        conversations: [snapshot, ...s.conversations],
      }
    })
  },

  setSelectedModel: (modelId: string) => {
    localStorage.setItem('selectedModel', modelId)
    localStorage.setItem('selectedModelExplicitChoice', '1')
    set({ selectedModel: modelId })
  },

  fetchModels: async () => {
    try {
      const models = await api.getModels()
      const currentSelected = get().selectedModel
      const selectedKnown = models.some((m) => m.id === currentSelected && m.available)
      const preferred =
        models.find((m) => m.id === 'gpt6-sol' && m.available)
        || models.find((m) => m.available)
        || null

      if (!selectedKnown && preferred) {
        localStorage.setItem('selectedModel', preferred.id)
        set({ availableModels: models, selectedModel: preferred.id })
        return
      }

      set({ availableModels: models })
    } catch (err) {
      console.error('Failed to fetch models:', err)
    }
  },

  // --- Backend sync actions ---

  resetUserScopedState: (ownerUserId = null) => {
    localStorage.removeItem(CURRENT_ID_KEY)
    set({
      ownerUserId: ownerUserId ? String(ownerUserId) : null,
      conversations: [],
      currentId: null,
      messages: [],
      agentState: null,
      strategyCheckpointHistory: [],
      recentStrategyMemory: [],
      recentStrategyMemoryScope: null,
      recentStrategyMemoryLoading: false,
      recentStrategyMemoryError: null,
      lastPublishedFile: null,
      streaming: false,
    })
  },

  syncConversations: async () => {
    if (_syncPromise) return _syncPromise

    _syncPromise = (async () => {
      const authUserId = useAuthStore.getState().user?.id
      const ownerUserId = authUserId ? String(authUserId) : null
      if (!ownerUserId) {
        get().resetUserScopedState(null)
        return
      }
      if (get().ownerUserId !== ownerUserId) {
        get().resetUserScopedState(ownerUserId)
      }
      const hadConversations = get().conversations.length > 0
      useUIStore.getState().setConversationsLoading(!hadConversations)
      try {
        const data = await api.getConversations()
        const currentId = get().currentId
        const currentMessages = get().messages
        const existingById = new Map(get().conversations.map((c) => [String(c.id), c]))
        const seen = new Set<string>()
        const conversations: Conversation[] = []
        for (const c of data) {
          const conversationId = String(c.id)
          if (seen.has(conversationId)) continue
          seen.add(conversationId)
          const existing = existingById.get(conversationId)
          const messages =
            currentId === conversationId && currentMessages.length > 0
              ? currentMessages
              : existing?.messages || []
          conversations.push({
            id: conversationId,
            title: c.title || existing?.title || 'Untitled',
            messages,
            createdAt: c.created_at ? new Date(c.created_at).getTime() : (existing?.createdAt || Date.now()),
            updatedAt: c.updated_at ? new Date(c.updated_at).getTime() : existing?.updatedAt,
            messageCount: typeof c.message_count === 'number' ? c.message_count : messages.length,
          })
        }
        set({ ownerUserId, conversations })
      } catch (err) {
        if (isUnauthorizedError(err)) {
          localStorage.removeItem(CURRENT_ID_KEY)
          set({
            conversations: [],
            currentId: null,
            messages: [],
            agentState: null,
            strategyCheckpointHistory: [],
            recentStrategyMemory: [],
            recentStrategyMemoryScope: null,
            recentStrategyMemoryLoading: false,
            recentStrategyMemoryError: null,
          })
          useAuthStore.getState().logout()
          return
        }
        console.error('Failed to sync conversations:', err)
      } finally {
        useUIStore.getState().setConversationsLoading(false)
      }
    })()

    try {
      return await _syncPromise
    } finally {
      _syncPromise = null
    }
  },

  refreshRecentStrategyMemory: async (conversationId: string) => {
    const requestedConversationId = String(conversationId)
    if (!requestedConversationId) return

    set({
      recentStrategyMemory: [],
      recentStrategyMemoryScope: null,
      recentStrategyMemoryLoading: true,
      recentStrategyMemoryError: null,
    })

    try {
      const data = await api.getRecentStrategyMemory({
        conversationId: requestedConversationId,
        limit: 10,
      })
      if (get().currentId !== requestedConversationId) return
      set({
        recentStrategyMemory: data.records || [],
        recentStrategyMemoryScope: data.scope || null,
        recentStrategyMemoryError: null,
      })
    } catch (err) {
      if (get().currentId !== requestedConversationId) return
      set({
        recentStrategyMemory: [],
        recentStrategyMemoryScope: null,
        recentStrategyMemoryError: err instanceof Error ? err.message : '策略记忆暂时不可用',
      })
      console.error('Failed to load recent strategy memory:', err)
    } finally {
      if (get().currentId === requestedConversationId) {
        set({ recentStrategyMemoryLoading: false })
      }
    }
  },

  setCurrentId: async (id: string) => {
    storeSavedConversationId(id)
    try {
      const data = await api.getConversation(id)
      const messages: ChatMessage[] = (data.messages || []).map((m: ApiConversationMessage) => ({
        id: m.id || genId(),
        role: m.role,
        content: m.content || '',
        toolCalls: parseToolCalls(m.tool_calls || m.toolCalls),
        files: normalizeMessageFiles(m.files),
        thinking: m.thinking || [],
        createdAt: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
      }))

      // Update or add this conversation in the list
      set((s) => {
        const existing = s.conversations.find((c) => c.id === id)
        const conversations = existing
          ? s.conversations.map((c) =>
              c.id === id
                ? {
                    ...c,
                    messages,
                    title: data.title || c.title,
                    updatedAt: data.updated_at ? new Date(data.updated_at).getTime() : c.updatedAt,
                    messageCount: messages.length,
                  }
                : c
            )
          : [
              {
                id,
                title: data.title || 'Untitled',
                messages,
                createdAt: data.created_at
                  ? new Date(data.created_at).getTime()
                  : Date.now(),
                updatedAt: data.updated_at ? new Date(data.updated_at).getTime() : undefined,
                messageCount: messages.length,
              },
              ...s.conversations,
            ]
        return {
          currentId: id,
          messages,
          conversations,
          agentState: null,
          strategyCheckpointHistory: [],
          recentStrategyMemory: [],
          recentStrategyMemoryScope: null,
          recentStrategyMemoryLoading: false,
          recentStrategyMemoryError: null,
        }
      })
      void get().refreshRecentStrategyMemory(id)
      try {
        const [checkpoint, history] = await Promise.all([
          api.getActiveStrategyCheckpoint(id),
          api.getStrategyCheckpointHistory(id),
        ])
        const restoredState = normalizeAgentState(checkpoint.agent_state)
        if (restoredState && get().currentId === id) {
          set({ agentState: restoredState, strategyCheckpointHistory: history.records || [] })
        } else if (get().currentId === id) {
          set({ agentState: null, strategyCheckpointHistory: history.records || [] })
        }
      } catch (err) {
        if (isUnauthorizedError(err)) {
          clearSavedConversationId(useAuthStore.getState().user?.id)
          set({
            currentId: null,
            messages: [],
            agentState: null,
            strategyCheckpointHistory: [],
            recentStrategyMemory: [],
            recentStrategyMemoryScope: null,
            recentStrategyMemoryLoading: false,
            recentStrategyMemoryError: null,
          })
          useAuthStore.getState().logout()
        }
      }
    } catch (err) {
      if (isUnauthorizedError(err)) {
        clearSavedConversationId(useAuthStore.getState().user?.id)
        set({
          currentId: null,
          messages: [],
          agentState: null,
          strategyCheckpointHistory: [],
          recentStrategyMemory: [],
          recentStrategyMemoryScope: null,
          recentStrategyMemoryLoading: false,
          recentStrategyMemoryError: null,
        })
        useAuthStore.getState().logout()
        return
      }
      if (err instanceof ApiError && err.status === 404) {
        clearSavedConversationId(useAuthStore.getState().user?.id)
        set((s) => ({
          conversations: s.conversations.filter((c) => c.id !== id),
          currentId: s.currentId === id ? null : s.currentId,
          messages: s.currentId === id ? [] : s.messages,
          agentState: null,
          strategyCheckpointHistory: [],
          recentStrategyMemory: [],
          recentStrategyMemoryScope: null,
          recentStrategyMemoryLoading: false,
          recentStrategyMemoryError: null,
        }))
        return
      }
      console.error('Failed to load conversation:', err)
    }
  },

  syncNewConversation: async () => {
    try {
      const data = await api.createConversation()
      const conversationId = String(data.id)
      const conv: Conversation = {
        id: conversationId,
        title: data.title || 'New Conversation',
        messages: [],
        createdAt: data.created_at ? new Date(data.created_at).getTime() : Date.now(),
        updatedAt: data.updated_at ? new Date(data.updated_at).getTime() : undefined,
        messageCount: 0,
      }
      set((s) => ({
        conversations: [conv, ...s.conversations],
        currentId: conv.id,
        messages: [],
        agentState: null,
        strategyCheckpointHistory: [],
        recentStrategyMemory: [],
        recentStrategyMemoryScope: null,
        recentStrategyMemoryLoading: false,
        recentStrategyMemoryError: null,
      }))
      return conversationId
    } catch (err) {
      console.error('Failed to create conversation:', err)
      // Fallback: create a local-only conversation
      const id = `conv-${++convId}`
      set((s) => ({
        conversations: [
          { id, title: 'New Conversation', messages: [], createdAt: Date.now(), messageCount: 0 },
          ...s.conversations,
        ],
        currentId: id,
        messages: [],
        agentState: null,
        strategyCheckpointHistory: [],
        recentStrategyMemory: [],
        recentStrategyMemoryScope: null,
        recentStrategyMemoryLoading: false,
        recentStrategyMemoryError: null,
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
      return {
        conversations,
        currentId,
        messages,
        ...(previousState.currentId === id
          ? {
              recentStrategyMemory: [],
              recentStrategyMemoryScope: null,
              recentStrategyMemoryLoading: false,
              recentStrategyMemoryError: null,
            }
          : {}),
      }
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
        recentStrategyMemory: previousState.recentStrategyMemory,
        recentStrategyMemoryScope: previousState.recentStrategyMemoryScope,
        recentStrategyMemoryLoading: previousState.recentStrategyMemoryLoading,
        recentStrategyMemoryError: previousState.recentStrategyMemoryError,
      })
    }
  },

  syncRenameConversation: async (id: string, title: string) => {
    const trimmed = title.trim()
    if (!trimmed) return

    const previousConversations = get().conversations
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title: trimmed, updatedAt: Date.now() } : c
      ),
    }))

    try {
      const data = await api.updateConversation(id, trimmed)
      set((s) => ({
        conversations: s.conversations.map((c) =>
          c.id === id
            ? {
                ...c,
                title: data.title || trimmed,
                updatedAt: data.updated_at ? new Date(data.updated_at).getTime() : c.updatedAt,
              }
            : c
        ),
      }))
    } catch (err) {
      console.error('Failed to rename conversation:', err)
      set({ conversations: previousConversations })
      throw err
    }
  },

  restoreSession: async () => {
    if (_restoring) return
    _restoring = true
    const savedIdBeforeReset = localStorage.getItem(CURRENT_ID_KEY)
    // Load conversations from backend (deduped, concurrent-safe)
    try {
      const user = useAuthStore.getState().user
      if (!user) {
        get().resetUserScopedState(null)
        return
      }
      const userId = String(user.id)
      if (get().ownerUserId !== userId) {
        get().resetUserScopedState(userId)
      }

      await get().syncConversations()

      // Restore last selected conversation if saved and still exists
      const savedId = savedIdBeforeReset || getSavedConversationId(userId)
      if (savedId && get().conversations.some((conv) => conv.id === savedId)) {
        try {
          await get().setCurrentId(savedId)
        } catch {
          clearSavedConversationId(userId)
        }
        return
      }

      if (savedId) {
        clearSavedConversationId(userId)
        set((s) => ({
          currentId: s.currentId === savedId ? null : s.currentId,
          messages: s.currentId === savedId ? [] : s.messages,
          agentState: null,
          strategyCheckpointHistory: [],
          recentStrategyMemory: [],
          recentStrategyMemoryScope: null,
          recentStrategyMemoryLoading: false,
          recentStrategyMemoryError: null,
        }))
      }
    } finally {
      _restoring = false
    }
  },
}))

if (typeof window !== 'undefined') {
  let lastAuthUserId = useAuthStore.getState().user?.id ? String(useAuthStore.getState().user?.id) : null
  useAuthStore.subscribe((state) => {
    const nextAuthUserId = state.user?.id ? String(state.user.id) : null
    if (nextAuthUserId === lastAuthUserId) return
    const previousAuthUserId = lastAuthUserId
    lastAuthUserId = nextAuthUserId
    const chat = useChatStore.getState()
    if (!nextAuthUserId) {
      chat.resetUserScopedState(null)
      return
    }
    if (previousAuthUserId && previousAuthUserId !== nextAuthUserId) {
      chat.resetUserScopedState(nextAuthUserId)
      return
    }
    if (chat.ownerUserId !== nextAuthUserId) {
      useChatStore.setState({ ownerUserId: nextAuthUserId })
    }
  })

  window.addEventListener('protein-ai:auth-cleared', () => {
    useChatStore.getState().resetUserScopedState(null)
  })

  window.addEventListener(USER_SCOPED_RESET_EVENT, () => {
    useChatStore.getState().resetUserScopedState(null)
  })
}
