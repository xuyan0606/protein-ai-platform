import { useShallow } from 'zustand/react/shallow'
import { useChatStore, AgentState, ToolCall } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { api, authFetch, isUnauthorizedError } from '@/lib/api'

export type AnalysisDepth = 'fast' | 'standard' | 'deep'
export type AgentControl = 'plan_only' | 'execute_confirmed' | 'revise_plan'
export interface ConfirmedStrategyCheckpoint {
  confirmed_plan: AgentState['plan']
  strategy_signature?: string | null
  task_fingerprint?: string | null
}

let activeStreamController: AbortController | null = null
let activeStopRequested = false

export function stopActiveChatStream() {
  if (!activeStreamController) return
  activeStopRequested = true
  activeStreamController.abort()
}

export function useChatStream() {
  const { addMessage, updateLastAssistant, setStreaming, upsertConversationSnapshot } =
    useChatStore(useShallow((s) => ({
      addMessage: s.addMessage,
      updateLastAssistant: s.updateLastAssistant,
      setStreaming: s.setStreaming,
      upsertConversationSnapshot: s.upsertConversationSnapshot,
    })))

  const sendMessage = async (
    content: string,
    conversationId?: string,
    projectId?: string,
    files?: Array<{name?: string; objectName?: string; downloadUrl?: string; analysisData?: unknown}>,
    analysisDepth: AnalysisDepth = 'standard',
    agentControl: AgentControl = 'plan_only',
    checkpoint?: ConfirmedStrategyCheckpoint
  ) => {
    // Zustand updates synchronously. This closes the render-gap where a rapid
    // second click/Enter could start another request before React re-rendered.
    const chat = useChatStore.getState()
    if (chat.streaming || chat.conversationLoading || chat.conversationLoadError) return
    const initialConversationId = conversationId ?? useChatStore.getState().currentId ?? undefined
    const displayedCheckpoint = useChatStore.getState().agentState
    setStreaming(true)
    let streamFinished = false
    const controller = new AbortController()
    activeStreamController = controller
    activeStopRequested = false

    // Add placeholder assistant message
    addMessage({
      role: 'assistant',
      content: '',
      toolCalls: [],
      thinking: [],
    })

    try {
      // Build history from last 10 messages (role + content only)
      const store = useChatStore.getState()
      const history: { role: string; content: string }[] = store.messages
        .slice(-11, -1) // exclude the placeholder assistant message we just added
        .slice(-10)
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))

      const selectedModel = useChatStore.getState().selectedModel

      const response = await authFetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: files && files.length > 0
            ? content + '\n\n[Attached files:\n' + files.map(f => {
                const parts = []
                if (f.name) parts.push('name: ' + f.name)
                if (f.objectName) parts.push('object_name: ' + f.objectName)
                if (f.downloadUrl) parts.push('download_url: ' + f.downloadUrl)
                if (f.analysisData) parts.push('analysis: ' + JSON.stringify(f.analysisData))
                return '- ' + parts.join(', ')
              }).join('\n') + ']'
            : content,
          conversation_id: initialConversationId || null,
          project_id: projectId || null,
          history,
          model: selectedModel,
          analysis_depth: analysisDepth,
          agent_control: agentControl,
          ...(agentControl !== 'plan_only' && checkpoint ? checkpoint : {}),
        }),
        signal: controller.signal,
      })

      if (response.status === 401) {
        useAuthStore.getState().logout()
        updateLastAssistant({
          content: 'Session expired. Please log in again.',
        })
        streamFinished = true
        return
      }

      if (response.status === 409) {
        updateLastAssistant({
          content: '分析策略已更新，请刷新查看最新策略后再次确认；本次未执行工具。',
        })
        streamFinished = true
        return
      }

      if (!response.ok) throw new Error(`Stream connection failed (${response.status})`)

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let buffer = ''

      const processDataLine = (line: string) => {
        if (!line.startsWith('data: ')) return

        try {
          const data = JSON.parse(line.slice(6))

          // Handle done event — persist conversation_id
          if (data.type === 'done' && data.conversation_id) {
            localStorage.setItem('currentConversationId', String(data.conversation_id))
            upsertConversationSnapshot(String(data.conversation_id))
          }

          // Handle title event — update sidebar in real time
          if (data.type === 'title' && data.conversation_id && data.title) {
            useChatStore.getState().updateConversationTitle(
              String(data.conversation_id), data.title
            )
            upsertConversationSnapshot(String(data.conversation_id), data.title)
          }

          // Handle published event — report auto-published to wiki
          if (data.type === 'published') {
            useChatStore.setState({ lastPublishedFile: {
              file_id: data.file_id,
              filename: data.filename,
              wiki_url: data.wiki_url,
            }})
          }

          handleSSEEvent(data)
          if (data.type === 'done' || data.type === 'error') {
            streamFinished = true
          }
        } catch {
          // Partial chunk or incomplete JSON — append as raw text
          const text = line.slice(6)
          if (text.trim() && !text.trim().startsWith('{')) {
            const store = useChatStore.getState()
            const msgs = store.messages
            if (msgs.length > 0) {
              store.updateLastAssistant({
                content: (msgs[msgs.length - 1]?.content || '') + text,
              })
            }
          }
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          buffer += decoder.decode()
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          processDataLine(line)
        }

      }

      if (!streamFinished && buffer.trim()) {
        for (const line of buffer.split('\n')) {
          processDataLine(line.trimEnd())
        }
      }
    } catch (err) {
      const store = useChatStore.getState()
      const lastMsg = store.messages[store.messages.length - 1]
      const existingContent = lastMsg?.content?.trim() || ''
      const hasToolCalls = Boolean(lastMsg?.toolCalls && lastMsg.toolCalls.length > 0)
      const rawMessage = err instanceof Error ? err.message : 'Connection failed'
      const stoppedByUser = activeStopRequested || (err instanceof DOMException && err.name === 'AbortError')
      if (stoppedByUser) {
        streamFinished = true
        updateLastAssistant({
          content: `${existingContent}\n\n已停止执行。`.trim(),
        })
        return
      }
      const isNetworkLike = rawMessage.toLowerCase().includes('network')
        || rawMessage.toLowerCase().includes('fetch')
        || rawMessage.toLowerCase().includes('connection')
        || rawMessage.toLowerCase().includes('reader')
      const message = isNetworkLike
        ? '服务暂不可用，请稍后重试。已保留当前收到的分析结果。'
        : `服务暂不可用，请稍后重试。(${rawMessage})`
      updateLastAssistant({
        content: existingContent || hasToolCalls ? `${existingContent}\n\n${message}`.trim() : message,
      })
    } finally {
      if (activeStreamController === controller) {
        activeStreamController = null
        activeStopRequested = false
      }
      const currentConversationId = useChatStore.getState().currentId
      const finalState = useChatStore.getState().agentState
      if (
        agentControl === 'plan_only'
        && currentConversationId === initialConversationId
        && ['conversation_review', 'report_quality_review_followup', 'p0_followup_review', 'same_problem_synthesis_followup'].includes(finalState?.research_notes || '')
        && displayedCheckpoint?.waiting_for === 'plan_confirmation'
        && displayedCheckpoint.strategy_signature
        && displayedCheckpoint.plan.length > 0
      ) {
        // A discussion turn does not consume consent or silently adopt a newer
        // plan. Keep the exact checkpoint already shown on this page.
        useChatStore.getState().setAgentState(displayedCheckpoint)
      }
      if (currentConversationId) {
        useChatStore.getState().upsertConversationSnapshot(currentConversationId)
      }
      setStreaming(false)
      if (currentConversationId) {
        try {
          const [history, memory] = await Promise.all([
            api.getStrategyCheckpointHistory(currentConversationId),
            api.getRecentStrategyMemory({ conversationId: currentConversationId, limit: 10 }),
          ])
          if (useChatStore.getState().currentId === currentConversationId) {
            useChatStore.setState({
              strategyCheckpointHistory: history.records || [],
              recentStrategyMemory: memory.records || [],
              recentStrategyMemoryScope: memory.scope || null,
              recentStrategyMemoryLoading: false,
              recentStrategyMemoryError: null,
            })
          }
        } catch (err) {
          if (isUnauthorizedError(err)) {
            useAuthStore.getState().logout()
          } else if (useChatStore.getState().currentId === currentConversationId) {
            useChatStore.setState({
              recentStrategyMemory: [],
              recentStrategyMemoryScope: null,
              recentStrategyMemoryLoading: false,
              recentStrategyMemoryError: err instanceof Error ? err.message : '策略记忆暂时不可用',
            })
          }
        }
      }
      // Refresh sidebar summaries after streaming completes, but avoid
      // replacing the current message list with a full conversation reload.
      try {
        if (!initialConversationId && streamFinished) {
          await new Promise((resolve) => setTimeout(resolve, 300))
          await useChatStore.getState().syncConversations()
        }
      } catch (err) {
        if (isUnauthorizedError(err)) {
          useAuthStore.getState().logout()
        }
        // Silently ignore refresh errors
      }
    }
  }

  return { sendMessage, stopStreaming: stopActiveChatStream }
}

interface SSEEvent {
  type: 'text' | 'tool_call' | 'tool_update' | 'thinking' | 'state' | 'done' | 'error' | 'title' | 'published'
  content?: string
  stage?: string
  plan?: Array<{
    id: number
    tool_name: string
    description: string
    params?: Record<string, unknown>
    status: string
  }>
  current_step?: number
  step_results?: Array<{
    step: number
    tool: string
    status: string
    result_preview?: string
    raw_result?: string
    analysis_state?: Record<string, string>
    error?: string
    duration?: number
  }>
  research_notes?: string
  waiting_for?: string | null
  strategy_signature?: string | null
  task_fingerprint?: string | null
  next_action?: string | null
  artifacts?: Record<string, unknown>
  tool_call?: { id: string; name: string }
  tool_update?: { id: string; status: string; duration?: number; error?: string }
  thinking?: string
  conversation_id?: string
  status?: string
  // Published event fields
  file_id?: string
  filename?: string
  wiki_url?: string
}

function handleSSEEvent(data: SSEEvent) {
  const store = useChatStore.getState()

  switch (data.type) {
    case 'state': {
      const plan = Array.isArray(data.plan) ? data.plan : []
      const stepResults = Array.isArray(data.step_results) ? data.step_results : []
      // Full agent state snapshot (VenusFactory2 pattern)
      store.setAgentState({
        stage: (data.stage as AgentState['stage']) || 'router',
        plan: plan.map((p) => ({
          id: p.id,
          tool_name: p.tool_name,
          description: p.description,
          params: p.params,
          status: p.status as AgentState['plan'][0]['status'],
        })),
        current_step: data.current_step || 0,
        step_results: stepResults,
        research_notes: data.research_notes || '',
        waiting_for: data.waiting_for || null,
        strategy_signature: data.strategy_signature || null,
        task_fingerprint: data.task_fingerprint || null,
        next_action: data.next_action || null,
        artifacts: data.artifacts || {},
      })

      // Sync tool calls from plan steps so ToolCallCard shows in the chat
      if (plan.length > 0) {
        const msgs = store.messages
        const last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant') {
          const existing = last.toolCalls || []
          // Build a map of existing tool calls by id
          const byId = new Map(existing.map((tc) => [tc.id, tc]))

          for (const step of plan) {
            const tcId = `plan-${step.id}`
            const existingTc = byId.get(tcId)

            if (existingTc) {
              // Update if status changed
              if (existingTc.status !== step.status) {
                store.updateToolCall(tcId, {
                  status: step.status as ToolCall['status'],
                })
              }
            } else if (step.status !== 'pending') {
              // Create new tool call for this plan step
              store.addToolCall({
                id: tcId,
                name: step.tool_name,
                status: step.status as ToolCall['status'],
              })
            }
          }
        }
      }

      // Link step_results to tool calls for result preview / PDB visualization
      if (stepResults.length > 0) {
        const msgs = useChatStore.getState().messages
        const last = msgs[msgs.length - 1]
        if (last?.toolCalls) {
          for (const sr of stepResults) {
            const tcId = `plan-${sr.step}`
            const match = last.toolCalls.find(
              (tc) => tc.id === tcId && (tc.status === 'completed' || tc.status === 'submitted')
            )
            if (match && (sr.result_preview || sr.raw_result)) {
              store.updateToolCall(tcId, {
                ...(sr.result_preview ? { resultPreview: sr.result_preview } : {}),
                ...(sr.raw_result ? { rawResult: sr.raw_result } : {}),
                ...(sr.analysis_state ? { analysisState: sr.analysis_state as Record<string, string> } : {}),
              })
            }
          }
        }
      }
      break
    }

    case 'text':
      {
        const lastMsg = store.messages[store.messages.length - 1]
        store.updateLastAssistant({
          content: (lastMsg?.content || '') + (data.content || ''),
        })
      }
      break

    case 'tool_call':
      if (data.tool_call) {
        store.addToolCall({
          id: data.tool_call.id,
          name: data.tool_call.name,
          status: 'pending',
        })
      }
      break

    case 'tool_update':
      if (data.tool_update) {
        store.updateToolCall(data.tool_update.id, {
          status: data.tool_update.status as ToolCall['status'],
          duration: data.tool_update.duration,
          error: data.tool_update.error,
        })
      }
      break

    case 'thinking':
      if (data.thinking) {
        store.updateLastAssistant({
          thinking: [
            ...(store.messages[store.messages.length - 1]?.thinking || []),
            data.thinking,
          ],
        })
      }
      break

    case 'done':
      // Streaming completed — conversation_id is handled in sendMessage loop
      if (data.status === 'timeout') {
        const state = store.agentState
        if (state) {
          store.setAgentState({
            ...state,
            stage: 'done',
            plan: state.plan.map((step) => step.status === 'running'
              ? { ...step, status: 'failed' }
              : step),
            step_results: state.step_results.map((result) => result.status === 'running'
              ? { ...result, status: 'timeout', error: 'Execution time limit reached' }
              : result),
          })
        }
        const lastMessage = store.messages[store.messages.length - 1]
        for (const toolCall of lastMessage?.toolCalls || []) {
          if (toolCall.status === 'running') {
            store.updateToolCall(toolCall.id, {
              status: 'failed',
              error: 'Execution time limit reached',
            })
          }
        }
      }
      break

    case 'error':
      store.updateLastAssistant({
        content: (store.messages[store.messages.length - 1]?.content || '') +
          `\n\n❌ ${data.content || 'An error occurred'}`,
      })
      break
  }
}
