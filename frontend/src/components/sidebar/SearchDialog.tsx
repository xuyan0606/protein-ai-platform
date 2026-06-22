import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, MessageSquare } from 'lucide-react'
import { useChatStore } from '@/stores/chat'

interface Props {
  open: boolean
  onClose: () => void
}

export function SearchDialog({ open, onClose }: Props) {
  const { t } = useTranslation()
  const conversations = useChatStore((s) => s.conversations)
  const selectConversation = useChatStore((s) => s.selectConversation)
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')

  // Focus input and reset query when opened
  useEffect(() => {
    if (open) {
      setQuery('')
      // Small delay to ensure the input is rendered
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  // Close on Escape (handled by keydown)
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const filtered = query.trim()
    ? conversations.filter((c) =>
        c.title.toLowerCase().includes(query.toLowerCase())
      )
    : conversations.slice(0, 5)

  const handleSelect = (id: string) => {
    selectConversation(id)
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />

      <div className="relative bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Search className="w-4 h-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('search.placeholder')}
            className="flex-1 bg-transparent text-sm focus:outline-none"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground font-mono shrink-0">
            ESC
          </kbd>
        </div>

        {/* Results */}
        {filtered.length > 0 ? (
          <div className="max-h-64 overflow-y-auto">
            {!query.trim() && (
              <div className="px-4 py-2 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                {t('search.recentConversations')}
              </div>
            )}
            {filtered.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelect(conv.id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-secondary transition-colors text-left"
              >
                <MessageSquare className="w-4 h-4 text-muted-foreground shrink-0" />
                <span className="truncate">{conv.title}</span>
              </button>
            ))}
          </div>
        ) : query.trim() ? (
          <div className="p-6 text-center">
            <p className="text-sm text-muted-foreground">
              {t('search.noResults')}
            </p>
          </div>
        ) : (
          <div className="p-4 text-xs text-muted-foreground text-center">
            {t('search.hint')}
          </div>
        )}
      </div>
    </div>
  )
}
