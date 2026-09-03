import { History, Package, ShieldCheck } from 'lucide-react'
import { useChatStore } from '@/stores/chat'
import type { ApiRecord } from '@/lib/api'

interface Props {
  compact?: boolean
}

function asRecord(value: unknown): ApiRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as ApiRecord : {}
}

function asRecordArray(value: unknown): ApiRecord[] {
  return Array.isArray(value) ? value.map(asRecord) : []
}

function shortToken(value: unknown) {
  const text = typeof value === 'string' ? value : ''
  if (!text) return '—'
  return text.length > 14 ? `${text.slice(0, 10)}...${text.slice(-4)}` : text
}

function statusLabel(value: unknown) {
  const status = typeof value === 'string' ? value : 'unknown'
  const labels: Record<string, string> = {
    awaiting_confirmation: '等待确认',
    executing: '已确认执行',
    completed: '已完成',
  }
  return labels[status] || status
}

function memoryTools(record: ApiRecord) {
  return asRecordArray(record.plan_payload)
    .map((step) => String(step.tool_name || step.tool || '').trim())
    .filter(Boolean)
}

function handoffCount(record: ApiRecord) {
  return asRecordArray(asRecord(record.artifacts).handoffs).length
}

function evidencePreview(record: ApiRecord) {
  const evidence = asRecord(record.evidence_state)
  const direct =
    evidence.evidence_level
    || evidence.calibration_level
    || evidence.support_level
    || evidence.status
  if (direct) return String(direct)

  const entries = Object.entries(evidence)
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value)}`)
  return entries.length ? entries.join('；') : '未记录证据等级'
}

export function StrategyMemoryPanel({ compact = false }: Props) {
  const memory = useChatStore((s) => s.recentStrategyMemory)
  const scope = useChatStore((s) => s.recentStrategyMemoryScope)
  const loading = useChatStore((s) => s.recentStrategyMemoryLoading)
  const error = useChatStore((s) => s.recentStrategyMemoryError)

  if (!loading && !error && memory.length === 0) return null

  const wrapperClass = compact
    ? 'border-t border-border px-3 py-2'
    : 'rounded-[8px] border border-border/80 bg-card/75 p-4 shadow-sm'
  const itemClass = compact
    ? 'rounded border border-border/70 px-2 py-1.5'
    : 'rounded-[8px] border border-border/70 bg-background/75 p-3'
  const scopeText = scope?.type === 'project' && scope.project_id
    ? `项目 ${scope.project_id}`
    : scope?.conversation_id
      ? `会话 ${scope.conversation_id}`
      : '当前会话'

  return (
    <div className={wrapperClass}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <History className="h-3.5 w-3.5" />
          同项目策略记忆
        </h4>
        <span className="shrink-0 text-[10px] text-muted-foreground">{scopeText}</span>
      </div>
      <div className="mb-2 flex items-start gap-1.5 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
        <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />
        <span>仅作为历史策略背景，不代表本轮重新执行；项目级湿实验校准不等于候选级直接验证。</span>
      </div>

      {loading && (
        <div className="text-[11px] text-muted-foreground">策略记忆加载中...</div>
      )}
      {error && !loading && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-700 dark:text-amber-300">
          策略记忆暂时不可用，已清空旧记忆：{error}
        </div>
      )}
      {!loading && !error && memory.length > 0 && (
        <div className="space-y-2">
          {memory.slice(0, compact ? 3 : 6).map((record, index) => {
            const tools = memoryTools(record)
            return (
              <div key={String(record.id ?? index)} className={itemClass}>
                <div className="mb-1 flex items-center gap-2 text-[11px]">
                  <span className="font-mono text-foreground">r{String(record.revision ?? '?')}</span>
                  <span className="text-muted-foreground">{statusLabel(record.status)}</span>
                  {record.next_action ? (
                    <span className="min-w-0 truncate text-muted-foreground">next: {String(record.next_action)}</span>
                  ) : null}
                </div>
                <div className="mb-1 flex flex-wrap gap-1 text-[10px] text-muted-foreground">
                  <span className="rounded border border-border/70 px-1.5 py-0.5">sig {shortToken(record.strategy_signature)}</span>
                  <span className="rounded border border-border/70 px-1.5 py-0.5">task {shortToken(record.task_fingerprint)}</span>
                  <span className="inline-flex items-center gap-1 rounded border border-border/70 px-1.5 py-0.5">
                    <Package className="h-3 w-3" />
                    handoff {handoffCount(record)}
                  </span>
                </div>
                {tools.length > 0 && (
                  <div className="mb-1 flex flex-wrap gap-1">
                    {tools.slice(0, 5).map((tool) => (
                      <span key={tool} className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                <div className="line-clamp-2 text-[11px] leading-5 text-muted-foreground">
                  证据预览：{evidencePreview(record)}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
