import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle2, CircleOff, Database, FlaskConical, Target } from 'lucide-react'
import { api, type BenchmarkCase, type BenchmarkPathInfo } from '@/lib/api'

const PATH_LABELS: Array<{ key: keyof BenchmarkCase['paths']; label: string }> = [
  { key: 'source_bundle_dir', label: '原始项目目录' },
  { key: 'incoming_alphafold_dir', label: '待放 AlphaFold 目录' },
  { key: 'incoming_sifts_dir', label: '待放 SIFTS 目录' },
  { key: 'incoming_annotations_dir', label: '待放注释目录' },
  { key: 'incoming_reference_docs_dir', label: '待放参考文档目录' },
  { key: 'incoming_reference_doc_manifest_file', label: '参考文档选择清单' },
  { key: 'discovery_report_file', label: '本地发现清单' },
  { key: 'background_file', label: '背景说明文件' },
  { key: 'sequence_file', label: '序列文件' },
  { key: 'original_structure_file', label: '原始结构文件' },
  { key: 'deploy_structure_file', label: 'deploy_data 结构文件' },
  { key: 'deploy_alphafold_dir', label: 'deploy_data AlphaFold 目录' },
  { key: 'deploy_sifts_dir', label: 'deploy_data SIFTS 目录' },
  { key: 'deploy_annotations_dir', label: 'deploy_data 注释目录' },
  { key: 'deploy_bundle_dir', label: 'deploy_data bundle 目录' },
  { key: 'deploy_bundle_manifest_file', label: 'bundle 清单文件' },
  { key: 'deploy_bundle_archive_file', label: 'bundle 压缩包' },
]

function PathCard({ label, pathInfo }: { label: string; pathInfo: BenchmarkPathInfo }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{label}</div>
        <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${pathInfo.exists ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
          {pathInfo.exists ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleOff className="h-3.5 w-3.5" />}
          {pathInfo.exists ? '已存在' : '未发现'}
        </div>
      </div>
      <div className="mt-3 rounded-xl bg-secondary/60 p-3 font-mono text-xs leading-6 text-muted-foreground">
        {pathInfo.absolute_path}
      </div>
    </div>
  )
}

function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`
  }
  return `${size} B`
}

export function BenchmarkCasePage() {
  const { caseId = '' } = useParams()
  const [benchmark, setBenchmark] = useState<BenchmarkCase | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setLoading(true)
      api.getBenchmark(caseId)
        .then((payload) => {
          if (cancelled) return
          setBenchmark(payload)
          setError('')
        })
        .catch((err: unknown) => {
          if (cancelled) return
          setError(err instanceof Error ? err.message : '加载案例失败')
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false)
          }
        })
      })

    return () => {
      cancelled = true
    }
  }, [caseId])

  if (loading) {
    return (
      <div className="min-h-screen bg-background px-4 py-10 sm:px-6">
        <div className="mx-auto max-w-5xl rounded-3xl border border-border bg-card p-8 text-base text-muted-foreground">
          正在加载案例详情...
        </div>
      </div>
    )
  }

  if (error || !benchmark) {
    return (
      <div className="min-h-screen bg-background px-4 py-10 sm:px-6">
        <div className="mx-auto max-w-5xl rounded-3xl border border-red-200 bg-red-50 p-8 text-base text-red-700">
          {error || '案例不存在'}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <section className="border-b border-border bg-gradient-to-br from-slate-50 via-white to-orange-50">
        <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
          <Link to="/benchmarks" className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            返回基准案例列表
          </Link>

          <div className="mt-5 flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-3xl">
              <div className="text-sm font-medium text-muted-foreground">{benchmark.program || benchmark.id}</div>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                {benchmark.title}
              </h1>
              <p className="mt-4 text-base leading-8 text-muted-foreground sm:text-lg">
                {benchmark.source_summary}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/pdb"
                className="inline-flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
              >
                进入 PDB 页
              </Link>
              <Link
                to="/chat/agent"
                className="inline-flex items-center gap-2 rounded-2xl bg-foreground px-4 py-3 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
              >
                发起分析
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-white/70 bg-white/85 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Target className="h-4 w-4" />
                目标 pH
              </div>
              <div className="mt-2 text-2xl font-semibold text-foreground">
                {benchmark.target_ph_range.min}-{benchmark.target_ph_range.max}
              </div>
            </div>
            <div className="rounded-2xl border border-white/70 bg-white/85 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FlaskConical className="h-4 w-4" />
                候选突变
              </div>
              <div className="mt-2 text-2xl font-semibold text-foreground">
                {benchmark.candidate_mutations.length} 个
              </div>
            </div>
            <div className="rounded-2xl border border-white/70 bg-white/85 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Database className="h-4 w-4" />
                序列长度
              </div>
              <div className="mt-2 text-2xl font-semibold text-foreground">
                {benchmark.sequence_length} aa
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-8">
            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">案例目标</h2>
              <p className="mt-4 text-base leading-8 text-muted-foreground">{benchmark.objective}</p>
              <div className="mt-5 space-y-3">
                {benchmark.analysis_highlights.map((item) => (
                  <div key={item} className="rounded-2xl bg-secondary/60 px-4 py-3 text-sm leading-7 text-foreground">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">候选突变位点</h2>
              <div className="mt-5 grid gap-4">
                {benchmark.candidate_mutations.map((item) => (
                  <div key={item.mutation} className="rounded-2xl border border-border p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-xl font-semibold text-foreground">{item.mutation}</div>
                      <div className="rounded-full bg-secondary px-3 py-1 text-sm font-medium text-muted-foreground">
                        位点 {item.position} | {item.wild_type}→{item.mutant}
                      </div>
                    </div>
                    <p className="mt-3 text-sm leading-7 text-muted-foreground">{item.hypothesis}</p>
                    {item.evidence_goal ? (
                      <div className="mt-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-900">
                        目标证据：{item.evidence_goal}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">希望回答的问题</h2>
              <div className="mt-5 grid gap-3">
                {benchmark.evidence_goals.map((item) => (
                  <div key={item} className="rounded-2xl bg-secondary/60 px-4 py-3 text-sm leading-7 text-foreground">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">资产状态</h2>
              <div className="mt-5 space-y-3 text-sm">
                {[
                  { label: 'PDB 已落到 deploy_data', ready: benchmark.status.pdb_staged && benchmark.paths.deploy_structure_file.exists },
                  { label: 'Foldseek DB 已纳入', ready: benchmark.status.foldseek_indexed },
                  { label: 'AlphaFold 资产已补齐', ready: benchmark.status.alphafold_ready },
                  { label: '真实 SIFTS 已接入', ready: benchmark.status.sifts_ready },
                  { label: '真实 annotations 已接入', ready: benchmark.status.annotations_ready },
                  { label: '参考文档已接入', ready: benchmark.status.reference_docs_ready },
                  { label: '参考文档清单已生成', ready: benchmark.status.reference_doc_manifest_ready },
                  { label: '案例 bundle 已生成', ready: benchmark.status.bundle_ready },
                  { label: '案例压缩包已生成', ready: benchmark.status.bundle_archive_ready },
                  { label: '本地候选清单已生成', ready: benchmark.status.discovery_report_ready },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between gap-3 rounded-2xl bg-secondary/60 px-4 py-3">
                    <span className="text-foreground">{item.label}</span>
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${item.ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                      {item.ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleOff className="h-3.5 w-3.5" />}
                      {item.ready ? '已完成' : '待继续'}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {[
                  { label: 'AlphaFold 文件数', value: benchmark.status.asset_counts.alphafold_structures },
                  { label: 'SIFTS 文件数', value: benchmark.status.asset_counts.sifts_mappings },
                  { label: '注释文件数', value: benchmark.status.asset_counts.annotation_files },
                  { label: '参考文档数', value: benchmark.status.asset_counts.reference_doc_files },
                  { label: 'Foldseek PDB 命中', value: benchmark.status.asset_counts.foldseek_pdb_entries },
                  { label: 'Bundle 文件数', value: benchmark.status.asset_counts.bundle_files },
                  { label: 'Bundle 压缩包大小', value: formatSize(benchmark.status.asset_counts.bundle_archive_size_bytes) },
                  { label: '发现的参考文档', value: benchmark.status.asset_counts.discovered_reference_docs },
                  { label: '发现的候选结构', value: benchmark.status.asset_counts.discovered_structures },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl bg-secondary/60 px-4 py-3">
                    <div className="text-xs text-muted-foreground">{item.label}</div>
                    <div className="mt-1 text-xl font-semibold text-foreground">{item.value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">真实路径</h2>
              <div className="mt-5 space-y-4">
                {PATH_LABELS.map((item) => (
                  <PathCard key={item.key} label={item.label} pathInfo={benchmark.paths[item.key]} />
                ))}
              </div>
            </div>

            {benchmark.bundle ? (
              <div className="rounded-3xl border border-border bg-card p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-foreground">交付清单</h2>
                    <p className="mt-2 text-sm leading-7 text-muted-foreground">
                      这个区块展示当前可直接交付的 bundle 内容和下载入口。
                    </p>
                  </div>
                  {benchmark.bundle.download_url ? (
                    <a
                      href={benchmark.bundle.download_url}
                      className="inline-flex items-center gap-2 rounded-2xl bg-foreground px-4 py-3 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
                    >
                      下载案例包
                      <ArrowRight className="h-4 w-4" />
                    </a>
                  ) : null}
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {Object.entries(benchmark.bundle.bundle_contents).map(([key, value]) => (
                    <div key={key} className="rounded-2xl bg-secondary/60 px-4 py-3">
                      <div className="text-xs text-muted-foreground">{key}</div>
                      <div className="mt-1 text-xl font-semibold text-foreground">{value}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-5 rounded-2xl bg-secondary/60 px-4 py-3 text-sm text-foreground">
                  压缩包大小：{formatSize(benchmark.bundle.archive_size_bytes)}
                </div>
              </div>
            ) : null}

            {benchmark.selected_reference_docs ? (
              <div className="rounded-3xl border border-border bg-card p-6">
                <h2 className="text-xl font-semibold text-foreground">已选参考文档</h2>
                <p className="mt-2 text-sm leading-7 text-muted-foreground">
                  系统已自动挑选 {benchmark.selected_reference_docs.selected_count} 份文档进入案例包。
                </p>
                <div className="mt-5 space-y-3">
                  {benchmark.selected_reference_docs.preview.map((item) => (
                    <div key={item.staged_path} className="rounded-2xl border border-border p-4">
                      <div className="truncate font-mono text-xs text-foreground">{item.source_path}</div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        分值 {item.score} | {formatSize(item.size_bytes)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {benchmark.discovery ? (
              <div className="rounded-3xl border border-border bg-card p-6">
                <h2 className="text-xl font-semibold text-foreground">本地候选资产</h2>
                <div className="mt-4 rounded-2xl bg-secondary/60 px-4 py-3 text-sm leading-7 text-foreground">
                  这是本机扫描出的候选文件预览，完整清单在 `incoming/discovery/asset_inventory.json`。
                </div>
                <div className="mt-5 space-y-4">
                  {[
                    { key: 'structures', label: '候选结构' },
                    { key: 'reference_docs', label: '候选文档' },
                    { key: 'alphafold', label: '候选 AlphaFold' },
                    { key: 'sifts', label: '候选 SIFTS' },
                    { key: 'annotations', label: '候选注释' },
                  ].map((section) => {
                    const items = benchmark.discovery?.preview[section.key] || []
                    const count = benchmark.discovery?.counts[section.key] || 0
                    return (
                      <div key={section.key} className="rounded-2xl border border-border p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-base font-medium text-foreground">{section.label}</div>
                          <div className="text-xs text-muted-foreground">{count} 个</div>
                        </div>
                        {items.length > 0 ? (
                          <div className="mt-3 space-y-2">
                            {items.map((item) => (
                              <div key={item.path} className="rounded-xl bg-secondary/60 px-3 py-2">
                                <div className="truncate font-mono text-xs text-foreground">{item.path}</div>
                                <div className="mt-1 text-[11px] text-muted-foreground">
                                  分值 {item.score} | {formatSize(item.size_bytes)}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="mt-3 text-sm text-muted-foreground">当前没有发现。</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="text-xl font-semibold text-foreground">下一步动作</h2>
              <div className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-900">
                后续你只要把真实文件放进 `Venus-15B淀粉酶项目/incoming/` 对应目录，然后运行
                <span className="mx-1 rounded bg-white/80 px-2 py-0.5 font-mono text-xs">python3 scripts/sync_benchmark_case.py --case-id venus-15b --rebuild-foldseek</span>
                就会自动同步到 `deploy_data/`。
              </div>
              <div className="mt-4 rounded-2xl bg-secondary/60 px-4 py-3 text-sm leading-7 text-foreground">
                如果你想先看看本机还有哪些候选文件可利用，运行
                <span className="mx-1 rounded bg-white/80 px-2 py-0.5 font-mono text-xs">python3 scripts/discover_benchmark_assets.py --case-id venus-15b --search-root /Users/xuyan/科为博</span>
                ，系统会把清单写到 `incoming/discovery/asset_inventory.json`。
              </div>
              <div className="mt-4 rounded-2xl bg-secondary/60 px-4 py-3 text-sm leading-7 text-foreground">
                如果想自动挑选最相关的业务文档进入案例包，运行
                <span className="mx-1 rounded bg-white/80 px-2 py-0.5 font-mono text-xs">python3 scripts/select_benchmark_reference_docs.py --case-id venus-15b</span>
                ，系统会把选中的文件放到 `incoming/reference_docs/auto_selected/` 并生成 `selected_manifest.json`。
              </div>
              <div className="mt-5 grid gap-3">
                {benchmark.recommended_actions.map((item) => (
                  <Link
                    key={item.title}
                    to={item.href || '/home'}
                    className="rounded-2xl border border-border p-4 transition-colors hover:bg-secondary/60"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-base font-medium text-foreground">{item.title}</div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="mt-2 text-sm leading-7 text-muted-foreground">{item.description}</p>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
