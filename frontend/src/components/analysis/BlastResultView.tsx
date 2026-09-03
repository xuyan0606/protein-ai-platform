import { Search, ExternalLink, Download, Printer } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'
import { ReportBadge, ReportBody, ReportHeader, ReportPanel, ReportSection, ReportShell } from '@/components/analysis/ReportShell'

interface Hsp {
  query_from?: number
  query_to?: number
  hit_from?: number
  hit_to?: number
  identity_percent?: number
  e_value?: string
  align_length?: number
}

interface BlastHit {
  hit_num: number
  accession: string
  id: string
  definition: string
  organism?: string
  hit_length: number
  best_identity_percent: number
  best_e_value: string
  total_hsps: number
  hsps?: Hsp[]
}

export interface BlastResult {
  query_length: number
  program: string
  database: string
  results_count: number
  query_preview?: string
  results: BlastHit[]
}

function EValueBadge({ e }: { e: string }) {
  const val = parseFloat(e)
  let tone: 'success' | 'warning' | 'danger' = 'success'
  if (isNaN(val) || val > 1e-5) tone = 'warning'
  if (val > 0.01) tone = 'danger'
  return <ReportBadge tone={tone}>{e}</ReportBadge>
}

function IdentityBar({ pct }: { pct: number }) {
  const color = pct > 80 ? 'bg-emerald-400' : pct > 50 ? 'bg-amber-400' : pct > 30 ? 'bg-orange-400' : 'bg-red-400'
  const textColor = pct > 80 ? 'text-emerald-500' : pct > 50 ? 'text-amber-500' : pct > 30 ? 'text-orange-500' : 'text-red-500'
  return (
    <div className="flex items-center gap-3">
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-secondary">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className={`w-12 text-right font-mono text-[10px] font-medium ${textColor}`}>
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

export function BlastResultView({ data }: { data: BlastResult }) {
  const { results, results_count, program, database, query_length } = data

  return (
    <ReportShell>
      <ReportHeader
        icon={Search}
        title="BLAST Results"
        subtitle={`${program} against ${database} · ${query_length} aa query · ${results_count} hits`}
        actions={
          <>
            <button onClick={() => downloadReport('blast', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Download HTML report">
              <Download className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => printReport('blast', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Print report">
              <Printer className="w-3.5 h-3.5" />
            </button>
          </>
        }
      />
      <ReportBody>
        <ReportSection title="Top Hits">
          <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
            {results.map((hit) => (
              <ReportPanel key={`${hit.accession}-${hit.hit_num}`} className="transition-colors hover:border-primary/20">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <ReportBadge tone="neutral">#{hit.hit_num}</ReportBadge>
                      <span className="truncate text-xs font-medium">{hit.definition}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                      <code className="font-mono">{hit.accession}</code>
                      {hit.organism && <span>{hit.organism}</span>}
                      <span>{hit.hit_length} aa</span>
                      <span>{hit.total_hsps} HSPs</span>
                    </div>
                  </div>
                  <a
                    href={`https://www.ncbi.nlm.nih.gov/protein/${hit.accession}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-md p-1 text-muted-foreground hover:bg-secondary"
                    title="View on NCBI"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <IdentityBar pct={hit.best_identity_percent} />
                  </div>
                  <EValueBadge e={hit.best_e_value} />
                </div>
              </ReportPanel>
            ))}

            {results.length === 0 && (
              <ReportPanel className="py-8 text-center text-xs text-muted-foreground">
                No significant hits found in {database}
              </ReportPanel>
            )}
          </div>
        </ReportSection>
      </ReportBody>
    </ReportShell>
  )
}
