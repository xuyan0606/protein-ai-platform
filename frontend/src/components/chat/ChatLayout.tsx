import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useShallow } from 'zustand/react/shallow'
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
import { Menu, PanelRightClose, PanelRight, User, LogOut, Sun, Moon, Home, FileText, FolderKanban, Database, Dna, BookOpen, Activity, FileDown, Package } from 'lucide-react'
import type { AgentState } from '@/stores/chat'
import { collectResults, downloadConversationReport } from '@/lib/conversation-report'
import { StrategyMemoryPanel } from '@/components/chat/StrategyMemoryPanel'

const STAGE_LABELS: Record<AgentState['stage'], string> = {
  router: 'Routing',
  research: 'Researching',
  plan: 'Planning',
  execute: 'Executing',
  synthesize: 'Synthesizing',
  done: 'Complete',
}

const STAGE_COLORS: Record<AgentState['stage'], string> = {
  router: 'text-blue-600 font-semibold',
  research: 'text-purple-600 font-semibold',
  plan: 'text-amber-600 font-semibold',
  execute: 'text-emerald-600 font-semibold',
  synthesize: 'text-rose-600 font-semibold',
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
  running: 'text-amber-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
}

const STAGE_PROGRESS: Record<AgentState['stage'], string> = {
  router: '10%',
  research: '30%',
  plan: '50%',
  execute: '75%',
  synthesize: '90%',
  done: '100%',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function artifactHandoffs(artifacts: Record<string, unknown> | undefined) {
  const handoffs = artifacts?.handoffs
  return Array.isArray(handoffs) ? handoffs.map(asRecord) : []
}

function artifactItems(handoff: Record<string, unknown>) {
  const items = handoff.items
  return Array.isArray(items) ? items.map(asRecord) : []
}

function PipelinePanel() {
  const agentState = useChatStore((s) => s.agentState)

  if (!agentState) {
    return (
      <div className="space-y-4">
        <div className="rounded-[24px] border border-border/80 bg-card/75 p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-medium">Tool Activity</h3>
          <p className="text-xs leading-6 text-muted-foreground">
            Tool calls and agent reasoning will appear here.
          </p>
        </div>
        <StrategyMemoryPanel />
      </div>
    )
  }

  const { stage, plan, current_step, step_results, research_notes, artifacts } = agentState
  const handoffs = artifactHandoffs(artifacts)

  return (
    <div className="space-y-4">
      <div className="rounded-[24px] border border-border/80 bg-card/80 p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-primary">Agent Pipeline</p>
            <h3 className="mt-1 text-base font-semibold">{STAGE_LABELS[stage]}</h3>
          </div>
          <div className="rounded-full border border-border/80 bg-background/80 px-3 py-1 text-[11px] text-muted-foreground">
            {plan.length} steps
          </div>
        </div>

        <div className="mb-2 flex items-center gap-2">
          <span className={`text-xs font-semibold uppercase tracking-wider ${STAGE_COLORS[stage]}`}>
            {STAGE_LABELS[stage]}
          </span>
          <div className="h-0.5 flex-1 overflow-hidden rounded-full bg-border">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: STAGE_PROGRESS[stage] }}
            />
          </div>
        </div>
        <p className="text-xs leading-6 text-muted-foreground">
          {research_notes || 'The agent will surface routing, execution, and synthesis details here.'}
        </p>
      </div>

      {/* Plan steps */}
      {plan.length > 0 && (
        <div className="rounded-[24px] border border-border/80 bg-card/75 p-4 shadow-sm">
          <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Execution Plan
          </h4>
          <div className="space-y-2">
            {plan.map((step) => (
              <div
                key={step.id}
                className={`rounded-2xl border px-3 py-2.5 text-xs transition-colors ${
                  step.id === current_step
                    ? 'border-primary/20 bg-primary/10'
                    : 'border-border/70 bg-background/70'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={STATUS_CLASS[step.status]}>
                    {STATUS_ICON[step.status] || '○'}
                  </span>
                  <span className="flex-1 truncate font-medium">{step.tool_name}</span>
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {step.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step results */}
      {step_results.length > 0 && (
        <div className="rounded-[24px] border border-border/80 bg-card/75 p-4 shadow-sm">
          <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Results
          </h4>
          <div className="space-y-3">
            {step_results.map((r) => (
              <div key={r.step} className="rounded-2xl border border-border/70 bg-background/75 p-3 text-xs">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="font-medium">Step {r.step}: {r.tool}</span>
                  <span className={STATUS_CLASS[r.status]}>
                    {STATUS_ICON[r.status]} {r.duration ? `${r.duration?.toFixed(1)}s` : ''}
                  </span>
                </div>
                {r.result_preview && (
                  <div className="font-mono text-[11px] text-muted-foreground line-clamp-4 break-all">
                    {r.result_preview}
                  </div>
                )}
                {r.error && (
                  <div className="mt-1 text-[11px] text-red-400">{r.error}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {handoffs.length > 0 && (
        <div className="rounded-[8px] border border-border/80 bg-card/75 p-4 shadow-sm">
          <h4 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            <Package className="h-3.5 w-3.5" />
            Artifact Handoff
          </h4>
          <div className="space-y-2">
            {handoffs.slice(0, 8).map((handoff, index) => (
              <div key={`${String(handoff.step ?? index)}-${String(handoff.tool ?? 'tool')}`} className="rounded-[8px] border border-border/70 bg-background/75 p-3 text-xs">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium">Step {String(handoff.step ?? '?')}: {String(handoff.tool ?? 'unknown')}</span>
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {String(handoff.handoff_status ?? handoff.status ?? 'unknown')}
                  </span>
                </div>
                <div className="space-y-1">
                  {artifactItems(handoff).length > 0 ? artifactItems(handoff).slice(0, 5).map((item, itemIndex) => {
                    const name = String(item.name ?? item.object_name ?? item.task_id ?? `artifact-${itemIndex + 1}`)
                    const downloadUrl = typeof item.download_url === 'string' ? item.download_url : null
                    const statusUrl = typeof item.status_url === 'string' ? item.status_url : null
                    return (
                      <div key={`${name}-${itemIndex}`} className="flex items-center gap-2 text-[11px] text-muted-foreground">
                        <FileDown className="h-3 w-3 shrink-0" />
                        <span className="min-w-0 flex-1 truncate">{name}</span>
                        {downloadUrl && (
                          <a className="text-primary hover:underline" href={downloadUrl} target="_blank" rel="noreferrer">file</a>
                        )}
                        {statusUrl && (
                          <a className="text-primary hover:underline" href={statusUrl} target="_blank" rel="noreferrer">task</a>
                        )}
                      </div>
                    )
                  }) : (
                    <div className="text-[11px] text-muted-foreground">No file artifact emitted.</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <StrategyMemoryPanel />

      {research_notes && (
        <div className="rounded-[24px] border border-border/80 bg-card/75 p-4 shadow-sm">
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Research Notes
          </h4>
          <div className="whitespace-pre-wrap rounded-2xl border border-border/70 bg-background/75 p-3 text-xs leading-6 text-muted-foreground">
            {research_notes}
          </div>
        </div>
      )}
    </div>
  )
}

export function ChatLayout() {
  const { t } = useTranslation()
  const { sidebarOpen, toggleSidebar, detailOpen, toggleDetail, restoreSession } = useChatStore(useShallow((s) => ({
    sidebarOpen: s.sidebarOpen,
    toggleSidebar: s.toggleSidebar,
    detailOpen: s.detailOpen,
    toggleDetail: s.toggleDetail,
    restoreSession: s.restoreSession,
  })))
  const { user, initialized, logout } = useAuthStore(useShallow((s) => ({
    user: s.user,
    initialized: s.initialized,
    logout: s.logout,
  })))
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
    if (initialized && user) {
      void restoreSession()
    }
  }, [initialized, user, restoreSession])

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

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="relative flex h-screen overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.12),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.08),transparent_28%)] dark:bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.16),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.1),transparent_30%)]" />
      </div>

      {/* Mobile / Tablet sidebar overlay */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={closeSidebar}
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-80 p-2 lg:hidden animate-slide-in-left">
            <div className="h-full overflow-hidden rounded-[30px] border border-white/60 bg-sidebar/95 shadow-[0_24px_80px_rgba(15,23,42,0.22)] backdrop-blur-xl dark:border-white/10">
              <ConversationList />
            </div>
          </aside>
        </>
      )}

      {/* Desktop sidebar — always rendered, width animates */}
      <aside
        className={`relative z-10 hidden lg:block ${
          sidebarOpen ? 'w-72' : 'w-0'
        } overflow-hidden transition-all duration-300 shrink-0`}
      >
        <div className="flex h-full w-72 flex-col p-4 pr-0">
          <div className="h-full overflow-hidden rounded-[30px] border border-white/60 bg-sidebar/90 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl dark:border-white/10">
            <ConversationList />
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="relative z-10 flex min-w-0 flex-1 flex-col p-2 sm:p-3 lg:p-4">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[30px] border border-white/50 bg-card/74 shadow-[0_22px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl dark:border-white/10 dark:bg-card/90">
        {/* Header */}
        <header className="shrink-0 border-b border-border/70 px-3 py-3 sm:px-5">
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={toggleSidebar}
              className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
              aria-label="Toggle sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="hidden shrink-0 items-center gap-2 sm:flex">
              <button
                onClick={() => navigate('/home')}
                className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Go home"
                title="Home"
              >
                <Home className="h-4 w-4" />
              </button>
              <button
                onClick={() => navigate('/projects')}
                className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Projects"
                title="Projects"
              >
                <FolderKanban className="h-4 w-4" />
              </button>
              <button
                onClick={() => navigate('/data')}
                className="hidden rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary lg:block"
                aria-label="Data"
                title="Data"
              >
                <Database className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => navigate('/pdb')}
                className="hidden rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary lg:block"
                aria-label="PDB"
                title="PDB"
              >
                <Dna className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => navigate('/kb')}
                className="hidden rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary lg:block"
                aria-label="Wiki"
                title="Wiki"
              >
                <BookOpen className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => navigate('/tasks')}
                className="hidden rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary lg:block"
                aria-label="Tasks"
                title="Tasks"
              >
                <Activity className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="flex-1" />

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <button
                onClick={cycleTheme}
                className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? (
                  <Moon className="h-4 w-4" />
                ) : (
                  <Sun className="h-4 w-4" />
                )}
              </button>

              <LanguageSwitch />

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
                className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Export report"
                title={t('home.downloadReport') || 'Download full report'}
              >
                <FileText className="h-4 w-4" />
              </button>

              {user && (
                <div className="relative">
                  <button
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    className="flex items-center gap-1.5 rounded-2xl border border-border/80 bg-background/80 px-2 py-1.5 text-sm transition-colors hover:bg-secondary"
                    aria-label="User menu"
                  >
                    <User className="w-4 h-4" />
                    <span className="hidden sm:inline max-w-[80px] truncate">
                      {user.name}
                    </span>
                  </button>

                  {userMenuOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setUserMenuOpen(false)}
                      />
                      <div className="absolute right-0 top-full z-20 mt-1 w-52 rounded-2xl border border-border bg-card py-1 shadow-lg">
                        <div className="border-b border-border px-3 py-2">
                          <p className="truncate text-sm font-medium">{user.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {user.email}
                          </p>
                        </div>
                        <button
                          onClick={handleLogout}
                          className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-500 transition-colors hover:bg-secondary"
                        >
                          <LogOut className="w-4 h-4" />
                          {t('auth.signOut')}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}

              <button
                onClick={toggleDetail}
                className="rounded-2xl border border-border/80 bg-background/80 p-2 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Toggle detail panel"
                title="Toggle detail panel"
              >
                {detailOpen ? (
                  <PanelRightClose className="h-5 w-5" />
                ) : (
                  <PanelRight className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>
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

        <div className="flex min-h-0 flex-1 flex-col p-2 sm:p-3 lg:p-4">
          <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[28px] bg-background/62 dark:bg-background/34">
            <MessageList />
            <ChatInput />
          </section>
        </div>
        </div>
      </main>

      {/* Detail Panel — responsive */}
      {detailOpen && (
        <>
          {/* Mobile overlay */}
          <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={toggleDetail} />
          <aside className="fixed right-0 top-0 bottom-0 z-50 flex w-80 flex-col p-2 md:relative md:z-10 md:w-[360px] md:p-4 md:pl-0">
            <div className="flex h-full flex-col overflow-hidden rounded-[30px] border border-white/60 bg-sidebar/92 p-4 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl dark:border-white/10">
            {/* Tabs */}
            <div className="mb-4 flex shrink-0 items-center gap-0.5 rounded-2xl bg-secondary p-0.5">
              <button
                onClick={() => setDetailTab('tools')}
                className={`flex-1 rounded-xl py-2 text-[11px] font-medium transition-colors ${
                  detailTab === 'tools' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Tools
              </button>
              <button
                onClick={() => setDetailTab('pipeline')}
                className={`flex-1 rounded-xl py-2 text-[11px] font-medium transition-colors ${
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
