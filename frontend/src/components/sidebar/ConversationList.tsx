import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import { useUIStore } from '@/stores/ui'
import { Plus, Search, Trash2, MessageSquare } from 'lucide-react'

function SkeletonRow() {
  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <div className="w-4 h-4 rounded bg-secondary animate-skeleton-pulse" />
      <div className="flex-1 h-3 rounded bg-secondary animate-skeleton-pulse" />
    </div>
  )
}

export function ConversationList() {
  const { t } = useTranslation()
  const {
    conversations,
    currentId,
    setCurrentId,
    syncConversations,
    syncNewConversation,
    syncDeleteConversation,
  } = useChatStore()
  const conversationsLoading = useUIStore((s) => s.conversationsLoading)
  const [search, setSearch] = useState('')

  // Fetch conversations on mount only if the store is empty
  // (restoreSession in ChatLayout already loads them — this is a fallback)
  useEffect(() => {
    if (conversations.length === 0) {
      syncConversations()
    }
  }, [syncConversations, conversations.length])

  const handleNewConversation = async () => {
    await syncNewConversation()
  }

  const handleSelectConversation = async (id: string) => {
    await setCurrentId(id)
  }

  const handleDeleteConversation = async (id: string) => {
    await syncDeleteConversation(id)
  }

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      {/* New chat button */}
      <div className="p-3">
        <button
          onClick={handleNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:bg-secondary text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          {t('sidebar.newChat')}
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('sidebar.search')}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-secondary rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2">
        {conversationsLoading ? (
          <div className="space-y-1 pt-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : (
          filtered.map((conv) => (
            <div
              key={conv.id}
              onClick={() => handleSelectConversation(conv.id)}
              className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
                conv.id === currentId
                  ? 'bg-secondary text-foreground'
                  : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
              }`}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate flex-1">{conv.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteConversation(conv.id)
                }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-background transition-all"
              >
                <Trash2 className="w-3.5 h-3.5 text-muted-foreground" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <div className="text-[11px] text-muted-foreground text-center">
          {t('sidebar.conversations', { count: conversations.length })}
        </div>
      </div>
    </div>
  )
}
