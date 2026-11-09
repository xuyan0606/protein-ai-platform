import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Database, FileText, Loader2, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import { api, type ResearchEvidence } from '@/lib/api'

function gateTone(ready: boolean) {
  return ready
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300'
    : 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'
}

function statusLabel(ready: boolean) {
  return ready ? 'ready' : 'blocked'
}

function GateCard({ title, ready, detail }: { title: string; ready: boolean; detail: string }) {
  return (
    <div className={`rounded-lg border px-4 py-3 ${gateTone(ready)}`}>
      <div className="flex items-center gap-2">
        {ready ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
        <span className="text-sm font-semibold">{title}</span>
      </div>
      <div className="mt-2 font-mono text-xs">{statusLabel(ready)}</div>
      <div className="mt-1 text-xs opacity-85">{detail}</div>
    </div>
  )
}

export function ResearchEvidencePage() {
  const navigate = useNavigate()
  const [data, setData] = useState<ResearchEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.getResearchEvidence('all'))
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载研究证据失败')
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

  const gates = useMemo(() => {
    if (!data) return []
    return [
      {
        title: '训练接入',
        ready: Boolean(data.training?.training_execution_allowed),
        detail: `${data.training?.training_import_eligible_rows ?? 0} eligible rows`,
      },
      {
        title: '模型声明',
        ready: Boolean(data.model_claim?.safe_for_model_claim),
        detail: `${data.model_claim?.claims_allowed ?? 0} allowed claims`,
      },
      {
        title: '客户交付',
        ready: Boolean(data.customer_delivery?.ready),
        detail: data.customer_delivery?.status || 'internal_review_only',
      },
      {
        title: 'Release',
        ready: Boolean(data.release?.release_ready),
        detail: data.release?.local_only ? 'local only' : 'non-local',
      },
      {
        title: 'Human target',
        ready: Boolean(data.human_target?.source_runtime_validation_success) && (data.human_target?.ready_sources ?? 0) > 0,
        detail: `${data.human_target?.blocked_sources ?? 0} blocked sources`,
      },
    ]
  }, [data])

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/85 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3">
          <button
            onClick={() => navigate('/chat/agent')}
            className="rounded-lg border border-border/80 bg-background p-2 text-muted-foreground transition-colors hover:bg-secondary"
            aria-label="返回"
            title="返回"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold">研究证据门控</h1>
            <p className="text-xs text-muted-foreground">训练、模型声明、客户交付、release 和 human target 的同源只读状态</p>
          </div>
          <button
            onClick={() => { void load() }}
            className="flex items-center gap-2 rounded-lg border border-border/80 bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary"
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
            Loading evidence
          </div>
        ) : data ? (
          <div className="space-y-5">
            <section className="grid gap-3 md:grid-cols-4">
              {gates.map((gate) => <GateCard key={gate.title} {...gate} />)}
            </section>

            <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div className="rounded-lg border border-border bg-card p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  Clean-room 训练候选
                </div>
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <dt className="text-muted-foreground">validated</dt>
                  <dd className="font-mono">{String(data.training?.cleanroom_kinetics_candidate?.validation_success ?? false)}</dd>
                  <dt className="text-muted-foreground">training eligible</dt>
                  <dd className="font-mono">{String(data.training?.cleanroom_kinetics_candidate?.training_eligible ?? false)}</dd>
                  <dt className="text-muted-foreground">written rows</dt>
                  <dd className="font-mono">{data.training?.cleanroom_kinetics_candidate?.training_import_written_rows ?? 0}</dd>
                </dl>
              </div>

              <div className="rounded-lg border border-border bg-card p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                  禁止动作
                </div>
                <div className="flex flex-wrap gap-2">
                  {(data.forbidden_side_effects || []).map((item) => (
                    <span key={item} className="rounded-md border border-border bg-secondary px-2 py-1 font-mono text-xs text-muted-foreground">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                人类靶点 / 抗体源与运行时
              </div>
              <dl className="mb-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                <dt className="text-muted-foreground">status</dt>
                <dd className="font-mono">{data.human_target?.status || 'blocked'}</dd>
                <dt className="text-muted-foreground">validated</dt>
                <dd className="font-mono">{String(data.human_target?.source_runtime_validation_success ?? false)}</dd>
                <dt className="text-muted-foreground">split validated</dt>
                <dd className="font-mono">{String(data.human_target?.split_manifest_validation_success ?? false)}</dd>
                <dt className="text-muted-foreground">total sources</dt>
                <dd className="font-mono">{data.human_target?.total_sources ?? 0}</dd>
                <dt className="text-muted-foreground">ready sources</dt>
                <dd className="font-mono">{data.human_target?.ready_sources ?? 0}</dd>
                <dt className="text-muted-foreground">blocked sources</dt>
                <dd className="font-mono">{data.human_target?.blocked_sources ?? 0}</dd>
                <dt className="text-muted-foreground">claim</dt>
                <dd className="font-mono">{String(data.human_target?.safe_for_model_claim ?? false)}</dd>
                <dt className="text-muted-foreground">customer</dt>
                <dd className="font-mono">{String(data.human_target?.customer_ready ?? false)}</dd>
                <dt className="text-muted-foreground">release</dt>
                <dd className="font-mono">{String(data.human_target?.release_ready ?? false)}</dd>
                <dt className="text-muted-foreground">schema</dt>
                <dd className="font-mono text-xs">{data.human_target?.schema_contract_status || 'schema_only'}</dd>
              </dl>
              <div className="mb-3 rounded-md border border-amber-200 bg-amber-50/70 px-3 py-3 dark:border-amber-900/60 dark:bg-amber-950/20">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm font-semibold">
                  <span>源解锁清单</span>
                  <span className="font-mono text-xs text-amber-800 dark:text-amber-300">
                    {data.human_target?.unlock_checklist?.ready_to_unlock_rows ?? 0}/
                    {data.human_target?.unlock_checklist?.checklist_rows ?? 0} ready
                  </span>
                </div>
                <div className="mt-1 text-xs text-amber-800/80 dark:text-amber-300/80">
                  机器校验通过不等于源已解锁；当前所有条目仍需真实 source/runtime receipt 和人工确认。
                </div>
                <div className="mt-2 grid gap-2">
                  {(data.human_target?.unlock_checklist?.rows || []).map((row) => (
                    <div key={row.checklist_id || row.source_id} className="rounded border border-amber-200/80 bg-background px-2 py-2 text-xs dark:border-amber-900/50">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">{row.source_id || row.checklist_id || 'unknown source'}</span>
                        <span className="font-mono text-amber-800 dark:text-amber-300">{row.current_status}</span>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                        missing: {(row.missing_steps || []).join(', ') || 'none'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid gap-2">
                {(data.human_target?.sources || []).map((source) => (
                  <div key={source.source_id} className="rounded-md border border-border bg-secondary px-3 py-2 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{source.display_name}</span>
                      <span className="font-mono text-amber-700 dark:text-amber-300">{source.status}</span>
                    </div>
                    <div className="mt-1 font-mono text-muted-foreground">{source.blocked_reason || 'blocked'}</div>
                    {source.split_manifest_path && (
                      <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{source.split_manifest_path}</div>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(source.required_artifacts || []).map((artifact) => (
                        <span key={artifact} className="rounded border border-border bg-background px-2 py-1 font-mono text-[11px] text-muted-foreground">
                          {artifact}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-[11px] text-muted-foreground md:grid-cols-4">
                      <span>runtime:{String(source.runtime_signal?.present ?? false)}</span>
                      <span>source:{String(source.source_ready)}</span>
                      <span>claim:{String(source.claim_eligible)}</span>
                      <span>release:{String(source.release_ready)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <FileText className="h-4 w-4 text-muted-foreground" />
                证据路径
              </div>
              <div className="grid gap-2 text-xs text-muted-foreground">
                {(data.evidence_paths || []).map((path) => (
                  <div key={path} className="truncate rounded-md bg-secondary px-3 py-2 font-mono">{path}</div>
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </main>
    </div>
  )
}
