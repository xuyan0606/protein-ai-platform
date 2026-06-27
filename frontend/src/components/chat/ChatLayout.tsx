import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ConversationList } from '@/components/sidebar/ConversationList'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'
import { ToolPanel } from '@/components/chat/ToolPanel'
import { SearchDialog } from '@/components/sidebar/SearchDialog'
import { LanguageSwitch } from '@/components/LanguageSwitch'
import { ToastContainer } from '@/components/ui/Toast'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'
import { useTheme } from '@/hooks/useTheme'
import { Menu, PanelRightClose, PanelRight, User, LogOut, Sun, Moon, Home, FileText, FolderKanban } from 'lucide-react'
import type { AgentState } from '@/stores/chat'
import { collectResults, downloadConversationReport } from '@/lib/conversation-report'

const STAGE_LABELS: Record<AgentState['stage'], string> = {
  router: 'Routing',
  research: 'Researching',
  plan: 'Planning',
  execute: 'Executing',
  synthesize: 'Synthesizing',
  done: 'Complete',
}

const STAGE_COLORS: Record<AgentState['stage'], string> = {
  router: 'text-blue-400',
  research: 'text-purple-400',
  plan: 'text-amber-400',
  execute: 'text-emerald-400',
  synthesize: 'text-rose-400',
  done: 'text-muted-foreground',
}

const STATUS_ICON: Record<string, string> = {
  pending: '○',
  running: '◉',
  completed: '✓',
  failed: '✗',
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'text-muted-foreground',
  running: 'text-amber-400 animate-pulse',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
}

function PipelinePanel() {
  const agentState = useChatStore((s) => s.agentState)

  if (!agentState) {
    return (
      <>
        <h3 className="font-medium text-sm mb-3">Tool Activity</h3>
        <p className="text-xs text-muted-foreground">
          Tool calls and agent reasoning will appear here.
        </p>
      </>
    )
  }

  const { stage, plan, current_step, step_results, research_notes } = agentState

  return (
    <>
      <h3 className="font-medium text-sm mb-3">Agent Pipeline</h3>

      {/* Stage indicator */}
      <div className="flex items-center gap-2 mb-4">
        <span className={`text-xs font-semibold uppercase tracking-wider ${STAGE_COLORS[stage]}`}>
          {STAGE_LABELS[stage]}
        </span>
        <div className="flex-1 h-0.5 bg-border rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: stage === 'done' ? '100%' : stage === 'router' ? '10%' : stage === 'research' ? '30%' : stage === 'plan' ? '50%' : stage === 'execute' ? '75%' : '90%' }}
          />
        </div>
      </div>

      {/* Plan steps */}
      {plan.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Execution Plan
          </h4>
          <div className="space-y-1.5">
            {plan.map((step) => (
              <div
                key={step.id}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs ${
                  step.id === current_step
                    ? 'bg-primary/10 border border-primary/20'
                    : 'bg-secondary/50'
                }`}
              >
                <span className={STATUS_CLASS[step.status]}>
                  {STATUS_ICON[step.status] || '○'}
                </span>
                <span className="flex-1 truncate">{step.tool_name}</span>
                <span className="text-[10px] text-muted-foreground">
                  {step.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step results */}
      {step_results.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Results
          </h4>
          <div className="space-y-2">
            {step_results.map((r) => (
              <div key={r.step} className="bg-secondary/50 rounded-md p-2.5 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium">Step {r.step}: {r.tool}</span>
                  <span className={STATUS_CLASS[r.status]}>
                    {STATUS_ICON[r.status]} {r.duration ? `${r.duration?.toFixed(1)}s` : ''}
                  </span>
                </div>
                {r.result_preview && (
                  <div className="text-[11px] text-muted-foreground line-clamp-3 font-mono break-all">
                    {r.result_preview}
                  </div>
                )}
                {r.error && (
                  <div className="text-[11px] text-red-400 mt-1">{r.error}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Research notes */}
      {research_notes && (
        <div>
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Research Notes
          </h4>
          <div className="text-xs text-muted-foreground bg-secondary/50 rounded-md p-2.5 whitespace-pre-wrap">
            {research_notes}
          </div>
        </div>
      )}
    </>
  )
}

export function ChatLayout() {
  const { t } = useTranslation()
  const { sidebarOpen, toggleSidebar, detailOpen, toggleDetail, restoreSession } = useChatStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { theme, setTheme } = useTheme()
  const streamError = useUIStore((s) => s.streamError)
  const isOffline = useUIStore((s) => s.isOffline)
  const setIsOffline = useUIStore((s) => s.setIsOffline)

  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [detailTab, setDetailTab] = useState<'pipeline' | 'tools'>('tools')

  // Restore session on mount
  useEffect(() => {
    restoreSession()
  }, [restoreSession])

  // Network online/offline detection
  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [setIsOffline])

  // Cmd+K / Ctrl+K to open search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setSearchOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const closeSidebar = useCallback(() => {
    const store = useChatStore.getState()
    if (store.sidebarOpen) store.toggleSidebar()
  }, [])

  const cycleTheme = () => {
    const order: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system']
    const idx = order.indexOf(theme)
    setTheme(order[(idx + 1) % order.length])
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile / Tablet sidebar overlay */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={closeSidebar}
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-72 border-r border-border bg-sidebar lg:hidden animate-slide-in-left">
            <ConversationList />
          </aside>
        </>
      )}

      {/* Desktop sidebar — always rendered, width animates */}
      <aside
        className={`hidden lg:block ${
          sidebarOpen ? 'w-72' : 'w-0'
        } border-r border-border bg-sidebar transition-all duration-300 overflow-hidden shrink-0`}
      >
        <div className="w-72 h-full flex flex-col">
          <ConversationList />
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-border flex items-center px-2 sm:px-4 gap-1 sm:gap-3 shrink-0">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            aria-label="Toggle sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          <button
            onClick={() => navigate('/home')}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            aria-label="Go home"
            title="Home"
          >
            <Home className="w-4 h-4" />
          </button>
          <button
            onClick={() => navigate('/projects')}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            aria-label="Projects"
            title="Projects"
          >
            <FolderKanban className="w-4 h-4" />
          </button>
          <span className="font-semibold text-xs sm:text-sm truncate">
            {t('app.title')}
          </span>
          <div className="flex-1" />

          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground transition-colors"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Moon className="w-4 h-4" />
            ) : (
              <Sun className="w-4 h-4" />
            )}
          </button>

          {/* Language switch */}
          <LanguageSwitch />

          {/* Export Conversation Report */}
          <button
            onClick={() => {
              const store = useChatStore.getState()
              const msgs = store.messages
              const results = msgs.flatMap((m) => {
                if (m.role === 'assistant' && m.toolCalls?.length) {
                  return collectResults(m.content, m.toolCalls)
                }
                return []
              })
              if (results.length === 0) return
              const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant')
              const title = store.conversations.find((c) => c.id === store.currentId)?.title || 'Analysis Report'
              downloadConversationReport(title, results, lastAssistant?.content)
            }}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            aria-label="Export report"
            title={t('home.downloadReport') || 'Download full report'}
          >
            <FileText className="w-4 h-4" />
          </button>

          {/* User Menu */}
          {user && (
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-1.5 sm:gap-2 px-1.5 sm:px-2 py-1.5 rounded-lg hover:bg-secondary text-sm transition-colors"
                aria-label="User menu"
              >
                <User className="w-4 h-4" />
                <span className="hidden sm:inline max-w-[80px] sm:max-w-[120px] truncate">
                  {user.name}
                </span>
              </button>

              {userMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setUserMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 w-48 bg-card border border-border rounded-lg shadow-lg z-20 py-1">
                    <div className="px-3 py-2 border-b border-border">
                      <p className="text-sm font-medium truncate">{user.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {user.email}
                      </p>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-secondary transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      {t('auth.signOut')}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Detail panel toggle — visible on all screens that can fit it */}
          <button
            onClick={toggleDetail}
            className="p-2 rounded-md hover:bg-secondary text-muted-foreground"
            aria-label="Toggle detail panel"
            title="Toggle detail panel"
          >
            {detailOpen ? (
              <PanelRightClose className="w-5 h-5" />
            ) : (
              <PanelRight className="w-5 h-5" />
            )}
          </button>
        </header>

        {/* Offline banner */}
        {isOffline && (
          <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-center">
            <p className="text-xs text-amber-600 dark:text-amber-400 font-medium">
              {t('app.reconnecting')}
            </p>
          </div>
        )}

        {/* SSE stream error banner */}
        {streamError && (
          <div className="bg-red-500/10 border-b border-red-500/30 px-4 py-2 text-center flex items-center justify-center gap-2">
            <p className="text-xs text-red-600 dark:text-red-400 font-medium">
              {streamError}
            </p>
            <button
              onClick={() => useUIStore.getState().setStreamError(null)}
              className="text-xs text-red-500 underline hover:text-red-600"
            >
              {t('common.retry')}
            </button>
          </div>
        )}

        {/* Messages */}
        <MessageList />

        {/* Input */}
        <ChatInput />
      </main>

      {/* Detail Panel — responsive */}
      {detailOpen && (
        <>
          {/* Mobile overlay */}
          <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={toggleDetail} />
          <aside className="fixed md:relative right-0 top-0 bottom-0 z-50 md:z-0 w-72 md:w-80 border-l border-border bg-sidebar shrink-0 p-4 animate-slide-in-left flex flex-col">
            {/* Tabs */}
            <div className="flex items-center gap-0.5 mb-3 bg-secondary rounded-lg p-0.5 shrink-0">
              <button
                onClick={() => setDetailTab('tools')}
                className={`flex-1 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  detailTab === 'tools' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Tools
              </button>
              <button
                onClick={() => setDetailTab('pipeline')}
                className={`flex-1 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  detailTab === 'pipeline' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Pipeline
              </button>
            </div>
            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {detailTab === 'pipeline' ? <PipelinePanel /> : <ToolPanel />}
            </div>
          </aside>
        </>
      )}

      {/* Cmd+K Search Dialog */}
      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  )
}
