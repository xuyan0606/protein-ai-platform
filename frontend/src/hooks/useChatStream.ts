import { useChatStore, AgentState, ToolCall } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

export function useChatStream() {
  const { addMessage, updateLastAssistant, addToolCall, updateToolCall, setStreaming, setAgentState } =
    useChatStore()

  const sendMessage = async (content: string, conversationId?: string) => {
    setStreaming(true)

    // Add placeholder assistant message
    addMessage({
      role: 'assistant',
      content: '',
      toolCalls: [],
      thinking: [],
    })

    try {
      const token = localStorage.getItem('token')

      // Build history from last 10 messages (role + content only)
      const store = useChatStore.getState()
      const history: { role: string; content: string }[] = store.messages
        .slice(-11, -1) // exclude the placeholder assistant message we just added
        .slice(-10)
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }))

      const selectedModel = useChatStore.getState().selectedModel

      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId || null,
          history,
          model: selectedModel,
        }),
      })

      if (response.status === 401) {
        useAuthStore.getState().logout()
        updateLastAssistant({
          content: 'Session expired. Please log in again.',
        })
        return
      }

      if (!response.ok) throw new Error('Stream connection failed')

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              // Handle done event — persist conversation_id
              if (data.type === 'done' && data.conversation_id) {
                localStorage.setItem('currentConversationId', String(data.conversation_id))
                useChatStore.setState({ currentId: String(data.conversation_id) })
              }

              // Handle title event — update sidebar in real time
              if (data.type === 'title' && data.conversation_id && data.title) {
                useChatStore.getState().updateConversationTitle(
                  String(data.conversation_id), data.title
                )
              }

              handleSSEEvent(data)
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
        }
      }
    } catch (err) {
      updateLastAssistant({
        content: `Error: ${err instanceof Error ? err.message : 'Connection failed'}`,
      })
    } finally {
      setStreaming(false)
      // Refresh conversations list from backend after streaming completes
      try {
        await useChatStore.getState().syncConversations()
      } catch {
        // Silently ignore refresh errors
      }
    }
  }

  return { sendMessage }
}

interface SSEEvent {
  type: 'text' | 'tool_call' | 'tool_update' | 'thinking' | 'state' | 'done' | 'error' | 'title'
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
    error?: string
    duration?: number
  }>
  research_notes?: string
  waiting_for?: string | null
  tool_call?: { id: string; name: string }
  tool_update?: { id: string; status: string; duration?: number; error?: string }
  thinking?: string
  conversation_id?: string
}

function handleSSEEvent(data: SSEEvent) {
  const store = useChatStore.getState()

  switch (data.type) {
    case 'state': {
      // Full agent state snapshot (VenusFactory2 pattern)
      setAgentState({
        stage: (data.stage as AgentState['stage']) || 'router',
        plan: (data.plan || []).map((p) => ({
          id: p.id,
          tool_name: p.tool_name,
          description: p.description,
          params: p.params,
          status: p.status as AgentState['plan'][0]['status'],
        })),
        current_step: data.current_step || 0,
        step_results: data.step_results || [],
        research_notes: data.research_notes || '',
        waiting_for: data.waiting_for || null,
      })

      // Sync tool calls from plan steps so ToolCallCard shows in the chat
      if (data.plan && data.plan.length > 0) {
        const msgs = store.messages
        const last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant') {
          const existing = last.toolCalls || []
          // Build a map of existing tool calls by id
          const byId = new Map(existing.map((tc) => [tc.id, tc]))

          for (const step of data.plan) {
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
      if (data.step_results) {
        const msgs = store.messages
        const last = msgs[msgs.length - 1]
        if (last?.toolCalls) {
          for (const sr of data.step_results) {
            // Use step number to find matching tool call by plan index
            const planStep = data.plan?.find((p) => p.id === sr.step)
            const tcId = `plan-${sr.step}`
            const match = last.toolCalls.find(
              (tc) => tc.id === tcId && tc.status === 'completed' && !tc.resultPreview
            )
            if (match && sr.result_preview) {
              store.updateToolCall(tcId, { resultPreview: sr.result_preview })
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
          status: data.tool_update.status as 'running' | 'completed' | 'failed',
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
      break

    case 'error':
      store.updateLastAssistant({
        content: (store.messages[store.messages.length - 1]?.content || '') +
          `\n\n❌ ${data.content || 'An error occurred'}`,
      })
      break
  }
}

function setAgentState(state: AgentState) {
  useChatStore.getState().setAgentState(state)
}
