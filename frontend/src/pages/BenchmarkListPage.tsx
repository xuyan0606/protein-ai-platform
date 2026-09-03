import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Database, Download, FileArchive, FlaskConical, PackageCheck, Target } from 'lucide-react'
import { api, type BenchmarkSummary } from '@/lib/api'

function formatSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`
  }
  return `${size} B`
}

function maturityLabel(item: BenchmarkSummary) {
  switch (item.maturity) {
    case 'delivery-ready':
      return '可直接交付'
    case 'bundle-ready':
      return '已生成案例包'
    case 'structure-ready':
      return '结构链路已通'
    case 'staged':
      return '已完成结构挂接'
    default:
      return '基础种子'
  }
}

export function BenchmarkListPage() {
  const [benchmarks, setBenchmarks] = useState<BenchmarkSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.getBenchmarks()
      .then((payload) => {
        if (cancelled) return
        setBenchmarks(payload.benchmarks)
        setError('')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : '加载基准案例失败')
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="min-h-screen bg-background">
      <section className="border-b border-border bg-gradient-to-br from-slate-50 via-white to-orange-50">
        <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
          <div className="inline-flex items-center gap-2 rounded-full border border-orange-200 bg-white px-3 py-1 text-sm font-medium text-orange-700">
            <FlaskConical className="h-4 w-4" />
            Benchmark Library
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            真实项目基准案例
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-8 text-muted-foreground sm:text-lg">
            这些案例不是演示文案，而是已经接入平台的数据样本。后续可以直接拿来验证结构检索、位点映射、注释聚合和突变分析链路。
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12">
        {loading ? (
          <div className="rounded-3xl border border-border bg-card p-8 text-base text-muted-foreground">
            正在加载基准案例...
          </div>
        ) : error ? (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-base text-red-700">
            {error}
          </div>
        ) : (
          <div className="grid gap-5">
            {benchmarks.map((item) => (
              <div
                key={item.id}
                className="group rounded-3xl border border-border bg-card p-6 transition-colors hover:border-foreground/20"
              >
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="max-w-3xl">
                    <div className="text-sm font-medium text-muted-foreground">
                      {item.program || item.id}
                    </div>
                    <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                      <PackageCheck className="h-3.5 w-3.5" />
                      {maturityLabel(item)}
                    </div>
                    <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
                      {item.title}
                    </h2>
                    <p className="mt-3 text-base leading-7 text-muted-foreground">
                      {item.objective}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    {item.asset_status.bundle_archive_ready ? (
                      <a
                        href={item.bundle_download_url}
                        className="inline-flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <Download className="h-4 w-4" />
                        下载案例包
                      </a>
                    ) : null}
                    <Link
                      to={`/benchmarks/${item.id}`}
                      className="inline-flex items-center gap-2 text-sm font-medium text-foreground"
                    >
                      查看详情
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </Link>
                  </div>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-4">
                  <div className="rounded-2xl bg-secondary/60 p-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Target className="h-4 w-4" />
                      目标 pH
                    </div>
                    <div className="mt-2 text-xl font-semibold">
                      {item.target_ph_range.min}-{item.target_ph_range.max}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-secondary/60 p-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <FlaskConical className="h-4 w-4" />
                      候选突变
                    </div>
                    <div className="mt-2 text-xl font-semibold">
                      {item.candidate_mutation_count} 个位点
                    </div>
                  </div>
                  <div className="rounded-2xl bg-secondary/60 p-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Database className="h-4 w-4" />
                      资产状态
                    </div>
                    <div className="mt-2 text-sm font-medium text-foreground">
                      {item.asset_status.foldseek_indexed
                        ? '已进 Foldseek'
                        : item.asset_status.deploy_structure_ready
                          ? '结构已挂接'
                          : '结构待挂接'}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-secondary/60 p-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <FileArchive className="h-4 w-4" />
                      交付信息
                    </div>
                    <div className="mt-2 text-sm font-medium text-foreground">
                      {item.asset_status.bundle_archive_ready
                        ? `${formatSize(item.asset_counts.bundle_archive_size_bytes)} | ${item.asset_counts.reference_doc_files} 份文档`
                        : item.asset_status.bundle_ready
                          ? `${item.asset_counts.bundle_files} 个 bundle 文件`
                          : '尚未形成交付包'}
                    </div>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  {[
                    item.asset_status.reference_docs_ready ? `参考文档 ${item.asset_counts.reference_doc_files}` : '',
                    item.asset_status.alphafold_ready ? `AlphaFold ${item.asset_counts.alphafold_structures}` : '',
                    item.asset_status.sifts_ready ? `SIFTS ${item.asset_counts.sifts_mappings}` : '',
                    item.asset_status.annotations_ready ? `Annotations ${item.asset_counts.annotation_files}` : '',
                  ]
                    .filter(Boolean)
                    .map((label) => (
                      <div key={label} className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
                        {label}
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
