import { Search, ExternalLink } from 'lucide-react'

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

interface BlastResult {
  query_length: number
  program: string
  database: string
  results_count: number
  query_preview?: string
  results: BlastHit[]
}

function EValueBadge({ e }: { e: string }) {
  const val = parseFloat(e)
  let color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  if (isNaN(val) || val > 1e-5) color = 'bg-amber-500/10 text-amber-400 border-amber-500/20'
  if (val > 0.01) color = 'bg-red-500/10 text-red-400 border-red-500/20'

  return (
    <code className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded border ${color}`}>
      {e}
    </code>
  )
}

function IdentityBar({ pct }: { pct: number }) {
  const color = pct > 80 ? 'bg-emerald-400' : pct > 50 ? 'bg-amber-400' : pct > 30 ? 'bg-orange-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="text-[10px] font-mono font-medium w-12 text-right" style={{ color: pct > 80 ? '#34d399' : pct > 50 ? '#fbbf24' : '#fb923c' }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

export function BlastResultView({ data }: { data: BlastResult }) {
  const { results, results_count, program, database, query_length } = data

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <Search className="w-4 h-4 text-primary" />
        <h3 className="font-semibold">BLAST Results</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        {program} against {database} · {query_length} aa query · {results_count} hits
      </p>

      {/* Results */}
      <div className="space-y-1.5 max-h-96 overflow-y-auto">
        {results.map((hit) => (
          <div key={`${hit.accession}-${hit.hit_num}`} className="bg-secondary/30 border border-border rounded-lg p-3 hover:border-ring/30 transition-colors">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] text-muted-foreground font-mono">#{hit.hit_num}</span>
                  <span className="text-xs font-medium truncate">{hit.definition}</span>
                </div>
                <div className="text-[10px] text-muted-foreground flex items-center gap-2 flex-wrap">
                  <code className="font-mono">{hit.accession}</code>
                  {hit.organism && <span>{hit.organism}</span>}
                  <span>·</span>
                  <span>{hit.hit_length} aa</span>
                  <span>·</span>
                  <span>{hit.total_hsps} HSPs</span>
                </div>
              </div>
              <a
                href={`https://www.ncbi.nlm.nih.gov/protein/${hit.accession}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 rounded hover:bg-secondary text-muted-foreground shrink-0"
                title="View on NCBI"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex-1">
                <IdentityBar pct={hit.best_identity_percent} />
              </div>
              <EValueBadge e={hit.best_e_value} />
            </div>
          </div>
        ))}

        {results.length === 0 && (
          <div className="text-center py-8 text-muted-foreground text-xs">
            No significant hits found in {database}
          </div>
        )}
      </div>
    </div>
  )
}

export function isBlastResult(data: unknown): data is BlastResult {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'results' in d && 'program' in d && 'database' in d
}
