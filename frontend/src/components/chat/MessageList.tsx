import { useRef, useEffect, useLayoutEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import { useChatStore, type ChatMessage } from '@/stores/chat'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { Dna } from 'lucide-react'

export function MessageList() {
  const [searchParams] = useSearchParams()
  const projectId = searchParams.get('projectId')
  const { messages, streaming, currentId } = useChatStore(useShallow((s) => ({
    messages: s.messages,
    streaming: s.streaming,
    currentId: s.currentId,
  })))
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
                  从你的研发目标开始
                </p>
                <h3 className="mt-1 text-lg font-semibold">选择上方模板，补充条件后发送</h3>
              </div>
            </div>

            <p className="text-sm leading-7 text-muted-foreground">写清楚“想改善什么、当前结果、目标结果、测定条件和已有资料”。只有序列或结构也可以开始，不清楚的信息请写“未知”。</p>
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
