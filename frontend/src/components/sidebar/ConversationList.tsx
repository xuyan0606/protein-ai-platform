import { useEffect, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useShallow } from 'zustand/react/shallow'
import { useChatStore } from '@/stores/chat'
import { useUIStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { BrandLogo } from '@/components/BrandLogo'
import { Check, Pencil, Plus, Trash2, MessageSquare, X } from 'lucide-react'

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
    syncRenameConversation,
  } = useChatStore(useShallow((s) => ({
    conversations: s.conversations,
    currentId: s.currentId,
    setCurrentId: s.setCurrentId,
    syncConversations: s.syncConversations,
    syncNewConversation: s.syncNewConversation,
    syncDeleteConversation: s.syncDeleteConversation,
    syncRenameConversation: s.syncRenameConversation,
  })))
  const user = useAuthStore((s) => s.user)
  const conversationsLoading = useUIStore((s) => s.conversationsLoading)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  // Fetch conversations for the active user. Do not rely on existing store
  // contents because a browser may switch between platform accounts.
  useEffect(() => {
    if (user?.id) {
      void syncConversations()
    }
  }, [user?.id, syncConversations])

  const handleNewConversation = async () => {
    try {
      await syncNewConversation()
    } catch {
      // Creation failure is displayed by the chat store, with the draft intact.
    }
  }

  const handleSelectConversation = async (id: string) => {
    await setCurrentId(id)
  }

  const handleDeleteConversation = async (id: string) => {
    await syncDeleteConversation(id)
  }

  const startRename = (id: string, title: string) => {
    setEditingId(id)
    setEditingTitle(title)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingTitle('')
  }

  const submitRename = async () => {
    if (!editingId) return
    const title = editingTitle.trim()
    if (!title) return
    await syncRenameConversation(editingId, title)
    cancelRename()
  }

  const handleRenameKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      void submitRename()
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      cancelRename()
    }
  }

  const formatDate = (timestamp: number) =>
    new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
    }).format(new Date(timestamp))

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/70 px-5 py-5">
        <div className="flex min-w-0 items-center gap-2">
          <BrandLogo size="xs" />
          <h2 className="min-w-0 flex-1 truncate text-sm font-semibold leading-none">Conversations</h2>
        </div>
      </div>

      <div className="p-4 pb-3">
        <button
          onClick={handleNewConversation}
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-primary/20 bg-primary px-3 py-3 text-sm font-medium text-primary-foreground shadow-[0_16px_40px_rgba(37,99,235,0.24)] transition-all hover:-translate-y-0.5 hover:bg-primary/92"
        >
          <Plus className="w-4 h-4" />
          {t('sidebar.newChat')}
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {conversationsLoading && conversations.length === 0 ? (
          <div className="space-y-1 pt-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => {
                  if (editingId !== conv.id) void handleSelectConversation(conv.id)
                }}
                className={`group cursor-pointer rounded-[22px] border px-3.5 py-3 text-sm transition-all ${
                  conv.id === currentId
                    ? 'border-primary/20 bg-primary/10 text-foreground shadow-[0_14px_34px_rgba(37,99,235,0.12)]'
                    : 'border-transparent bg-transparent text-muted-foreground hover:border-border/80 hover:bg-card/80 hover:text-foreground'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border ${
                    conv.id === currentId
                      ? 'border-primary/20 bg-primary/10 text-primary'
                      : 'border-border/80 bg-background/90 text-muted-foreground'
                  }`}>
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      {editingId === conv.id ? (
                        <input
                          value={editingTitle}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                          onChange={(event) => setEditingTitle(event.target.value)}
                          onKeyDown={handleRenameKeyDown}
                          className="min-w-0 flex-1 rounded-xl border border-border/80 bg-background px-2 py-1 text-sm font-medium leading-5 outline-none focus:border-primary"
                        />
                      ) : (
                        <span className="line-clamp-2 font-medium leading-6">{conv.title}</span>
                      )}
                      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-all group-hover:opacity-100">
                        {editingId === conv.id ? (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                void submitRename()
                              }}
                              className="rounded-xl p-1.5 transition-all hover:bg-background/80"
                              title="保存名称"
                            >
                              <Check className="h-3.5 w-3.5 text-emerald-600" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                cancelRename()
                              }}
                              className="rounded-xl p-1.5 transition-all hover:bg-background/80"
                              title="取消"
                            >
                              <X className="h-3.5 w-3.5 text-muted-foreground" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                startRename(conv.id, conv.title)
                              }}
                              className="rounded-xl p-1.5 transition-all hover:bg-background/80"
                              title="重命名"
                            >
                              <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                void handleDeleteConversation(conv.id)
                              }}
                              className="rounded-xl p-1.5 transition-all hover:bg-background/80"
                              title="删除"
                            >
                              <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{formatDate(conv.createdAt)}</span>
                      <span className="h-1 w-1 rounded-full bg-muted-foreground/50" />
                      <span>{conv.messageCount} msgs</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
