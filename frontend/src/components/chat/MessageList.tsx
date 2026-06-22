import { useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useChatStore, type ChatMessage } from '@/stores/chat'
import { useChatStream } from '@/hooks/useChatStream'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { Dna } from 'lucide-react'

export function MessageList() {
  const { t } = useTranslation()
  const { messages, streaming } = useChatStore()
  const { sendMessage } = useChatStream()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const suggestions: string[] = t('chat.suggestions', { returnObjects: true })

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
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <Dna className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold mb-2">{t('chat.welcome')}</h2>
        <p className="text-muted-foreground max-w-md text-sm">
          {t('chat.welcomeHint')}
        </p>
        <div className="mt-8 grid grid-cols-2 gap-3 max-w-lg">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSuggestionClick(suggestion)}
              className="p-3 text-left text-xs border border-border rounded-lg hover:bg-secondary transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.map((msg: ChatMessage) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {streaming && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm pl-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-primary animate-bounce delay-75" />
            <span className="w-2 h-2 rounded-full bg-primary animate-bounce delay-150" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
