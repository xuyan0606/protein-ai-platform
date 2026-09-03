import { useRef, useEffect, useLayoutEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import { useChatStore, type ChatMessage } from '@/stores/chat'
import { useChatStream } from '@/hooks/useChatStream'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { Dna } from 'lucide-react'

export function MessageList() {
  const [searchParams] = useSearchParams()
  const projectId = searchParams.get('projectId')
  const { t } = useTranslation()
  const { messages, streaming, currentId } = useChatStore(useShallow((s) => ({
    messages: s.messages,
    streaming: s.streaming,
    currentId: s.currentId,
  })))
  const { sendMessage } = useChatStream()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const prevMessageCountRef = useRef(0)
  const prevScrollHeightRef = useRef(0)
  const autoScrollFrameRef = useRef<number | null>(null)
  const lastAutoScrollAtRef = useRef(0)
  const lastMessage = messages[messages.length - 1]

  useEffect(() => {
    const scroller = scrollRef.current
    if (!scroller) return

    const handleScroll = () => {
      const distanceToBottom =
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight
      shouldStickToBottomRef.current = distanceToBottom < 80
    }

    handleScroll()
    scroller.addEventListener('scroll', handleScroll, { passive: true })
    return () => scroller.removeEventListener('scroll', handleScroll)
  }, [])

  useLayoutEffect(() => {
    const scroller = scrollRef.current
    if (!scroller) return

    const messageCountChanged = prevMessageCountRef.current !== messages.length
    prevMessageCountRef.current = messages.length
    const targetTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
    const heightDelta = scroller.scrollHeight - prevScrollHeightRef.current
    prevScrollHeightRef.current = scroller.scrollHeight

    if (!shouldStickToBottomRef.current) return

    const distanceToBottom = targetTop - scroller.scrollTop
    const shouldAdjust =
      messageCountChanged ||
      heightDelta > (streaming ? 56 : 24) ||
      distanceToBottom > (streaming ? 14 : 6)

    if (!shouldAdjust) return

    const now = performance.now()
    const shouldThrottle =
      streaming &&
      !messageCountChanged &&
      heightDelta < 120 &&
      now - lastAutoScrollAtRef.current < 120

    if (shouldThrottle) return

    if (autoScrollFrameRef.current !== null) {
      cancelAnimationFrame(autoScrollFrameRef.current)
    }

    autoScrollFrameRef.current = requestAnimationFrame(() => {
      autoScrollFrameRef.current = null
      const latestTargetTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
      if (Math.abs(latestTargetTop - scroller.scrollTop) <= 4) return
      scroller.scrollTop = latestTargetTop
      lastAutoScrollAtRef.current = performance.now()
    })
  }, [messages.length, lastMessage?.content, streaming])

  useEffect(() => {
    return () => {
      if (autoScrollFrameRef.current !== null) {
        cancelAnimationFrame(autoScrollFrameRef.current)
        autoScrollFrameRef.current = null
      }
    }
  }, [])

  const suggestions: string[] = (t('chat.suggestions', { returnObjects: true }) as unknown) as string[]

  const handleSuggestionClick = (suggestion: string) => {
    if (streaming) return

    useChatStore.getState().addMessage({
      role: 'user',
      content: suggestion,
    })

    const convId = useChatStore.getState().currentId ?? undefined
    sendMessage(suggestion, convId)
  }

  if (messages.length === 0) {
    return (
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto max-w-[920px] pt-8">
          <section className="rounded-[32px] border border-border/65 bg-background/72 px-5 py-6 shadow-[0_18px_60px_rgba(15,23,42,0.05)] backdrop-blur sm:px-7 sm:py-7">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-[18px] border border-primary/15 bg-primary/8 text-primary">
                <Dna className="h-5 w-5" />
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  Suggested Starts
                </p>
                <h3 className="mt-1 text-lg font-semibold">Choose a workflow and start directly</h3>
              </div>
            </div>

            <div className="grid gap-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="rounded-[24px] border border-border/75 bg-card/72 px-4 py-4 text-left text-sm leading-7 transition-all hover:-translate-y-0.5 hover:border-primary/25 hover:bg-primary/5"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto px-4 py-5 sm:px-6"
      style={{ overflowAnchor: 'none', overscrollBehavior: 'contain' }}
    >
      <div className="mx-auto max-w-[1120px] space-y-10">
        {messages.map((msg: ChatMessage, index) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            conversationId={currentId}
            projectId={projectId}
            isStreaming={streaming && index === messages.length - 1 && msg.role === 'assistant'}
          />
        ))}
        {streaming && (
          <div className="mx-auto flex w-fit items-center gap-2 rounded-full border border-border/80 bg-card/90 px-4 py-2 text-sm text-muted-foreground shadow-sm">
            <span className="w-2 h-2 rounded-full bg-primary/90" />
            <span className="w-2 h-2 rounded-full bg-primary/65" />
            <span className="w-2 h-2 rounded-full bg-primary/40" />
            Agent is responding
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
