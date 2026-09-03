import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, ArrowLeft, Ban, Download, Loader2, RefreshCw } from 'lucide-react'
import { api, buildToolTaskArtifactBundleUrl, type ToolTaskAudit } from '@/lib/api'

const TERMINAL_STATUSES = new Set(['completed', 'success', 'failed', 'failure', 'canceled', 'revoked'])

function statusTone(status: string) {
  const normalized = status.toLowerCase()
  if (normalized === 'completed' || normalized === 'success') return 'text-emerald-600 dark:text-emerald-300'
  if (normalized === 'failed' || normalized === 'failure') return 'text-red-500 dark:text-red-300'
  if (normalized === 'canceled' || normalized === 'revoked') return 'text-amber-600 dark:text-amber-300'
  return 'text-blue-600 dark:text-blue-300'
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function compactJson(value: unknown) {
  if (!value || typeof value !== 'object') return ''
  try {
    return JSON.stringify(value).slice(0, 180)
  } catch {
    return ''
  }
}

export function TaskCenterPage() {
  const navigate = useNavigate()
  const [audits, setAudits] = useState<ToolTaskAudit[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)

  const activeCount = useMemo(() => (
    audits.filter((audit) => !TERMINAL_STATUSES.has(audit.status.toLowerCase())).length
  ), [audits])

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listToolTaskAudits(80)
      setAudits(result.audits)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) void load()
    })
    return () => {
      cancelled = true
    }
  }, [])

  const cancelTask = async (taskId: string) => {
    setCancelling(taskId)
    setError(null)
    try {
      await api.cancelToolTask(taskId)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel task')
    } finally {
      setCancelling(null)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/85 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <button
            onClick={() => navigate('/chat/agent')}
            className="rounded-2xl border border-border/80 bg-background p-2 text-muted-foreground transition-colors hover:bg-secondary"
            aria-label="Back to chat"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold">任务中心</h1>
            <p className="text-xs text-muted-foreground">{activeCount} active · {audits.length} recent</p>
          </div>
          <button
            onClick={() => { void load() }}
            className="flex items-center gap-2 rounded-2xl border border-border/80 bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary"
          >
            <RefreshCw className="h-4 w-4" />
            刷新
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-5 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading tasks
          </div>
        ) : audits.length === 0 ? (
          <div className="rounded-lg border border-border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
            No async tool tasks yet.
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="grid grid-cols-[1.1fr_0.8fr_0.8fr_1fr_0.9fr] gap-3 border-b border-border bg-secondary/60 px-4 py-2 text-xs font-medium text-muted-foreground">
              <div>Task</div>
              <div>Status</div>
              <div>Queue</div>
              <div>Updated</div>
              <div className="text-right">Actions</div>
            </div>
            {audits.map((audit) => {
              const normalized = audit.status.toLowerCase()
              const isTerminal = TERMINAL_STATUSES.has(normalized)
              const canDownload = normalized === 'completed' || normalized === 'success'
              const preview = compactJson(audit.result_summary || audit.input_summary)
              return (
                <div key={audit.id || audit.task_id} className="grid grid-cols-[1.1fr_0.8fr_0.8fr_1fr_0.9fr] gap-3 border-b border-border px-4 py-3 text-sm last:border-b-0">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate font-medium">{audit.tool}</span>
                    </div>
                    <div className="mt-1 truncate font-mono text-xs text-muted-foreground">{audit.task_id}</div>
                    {preview && <div className="mt-1 truncate text-xs text-muted-foreground">{preview}</div>}
                  </div>
                  <div>
                    <span className={`font-medium ${statusTone(audit.status)}`}>{audit.status}</span>
                    {typeof audit.progress === 'number' && <div className="mt-1 text-xs text-muted-foreground">{Math.round(audit.progress)}%</div>}
                  </div>
                  <div className="text-muted-foreground">{audit.queue || '-'}</div>
                  <div className="text-xs text-muted-foreground">
                    <div>{formatTime(audit.updated_at)}</div>
                    {audit.duration_seconds !== null && audit.duration_seconds !== undefined && (
                      <div className="mt-1">{audit.duration_seconds}s</div>
                    )}
                  </div>
                  <div className="flex justify-end gap-2">
                    {canDownload && (
                      <a
                        href={buildToolTaskArtifactBundleUrl(audit.task_id)}
                        className="rounded-xl border border-border/80 bg-background p-2 text-muted-foreground transition-colors hover:bg-secondary"
                        aria-label="Download artifacts"
                        title="Download artifacts"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    )}
                    {!isTerminal && (
                      <button
                        onClick={() => { void cancelTask(audit.task_id) }}
                        disabled={cancelling === audit.task_id}
                        className="rounded-xl border border-border/80 bg-background p-2 text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-50"
                        aria-label="Cancel task"
                        title="Cancel task"
                      >
                        {cancelling === audit.task_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Ban className="h-4 w-4" />}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
