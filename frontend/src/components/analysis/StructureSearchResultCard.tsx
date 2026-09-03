import { Boxes, Database, Search, ShieldAlert } from 'lucide-react'
import {
  ReportBadge,
  ReportBody,
  ReportHeader,
  ReportMetricCard,
  ReportMetricGrid,
  ReportPanel,
  ReportSection,
  ReportShell,
} from '@/components/analysis/ReportShell'

interface QueryStructureSummary {
  chain_count?: number
  total_residues?: number
  total_atoms?: number
}

interface StructureSearchResult {
  target_id?: string | null
  template_id?: string | null
  title?: string | null
  source?: string | null
  score?: number | string | null
  rmsd?: number | string | null
  tm_score?: number | string | null
  identity?: number | string | null
  description?: string | null
}

export interface StructureSearchData {
  found: boolean
  status: string
  error_code?: string
  warning?: string
  database?: string
  backend?: string
  database_path?: string
  results_count?: number
  results: StructureSearchResult[]
  query_structure?: QueryStructureSummary
  cache?: {
    hit?: boolean
    stale?: boolean
  }
}

function renderHitTitle(hit: StructureSearchResult, index: number) {
  return hit.title || hit.template_id || hit.target_id || `Hit ${index + 1}`
}

export function StructureSearchResultCard({ data }: { data: StructureSearchData }) {
  return (
    <ReportShell>
      <ReportHeader
        icon={Search}
        title="Structure Search"
        subtitle={`${data.database || 'unknown database'} · ${data.status}`}
        badge={
          <ReportBadge tone={data.found ? 'success' : data.status === 'degraded' ? 'warning' : 'neutral'}>
            {data.results_count ?? data.results.length} hits
          </ReportBadge>
        }
      />
      <ReportBody>
        {data.warning ? (
          <ReportPanel tone="warning" className="text-xs leading-6 text-muted-foreground">
            {data.warning}
          </ReportPanel>
        ) : null}

        <ReportSection title="Query Structure" icon={Database}>
          <ReportMetricGrid>
            <ReportMetricCard label="Chains" value={data.query_structure?.chain_count ?? 0} tone="info" />
            <ReportMetricCard label="Residues" value={data.query_structure?.total_residues ?? 0} />
            <ReportMetricCard label="Atoms" value={data.query_structure?.total_atoms ?? 0} />
            <ReportMetricCard
              label="Backend"
              value={data.backend || 'unknown'}
              tone={data.backend === 'summary_only' ? 'warning' : data.backend === 'local_cli' ? 'success' : 'info'}
            />
            <ReportMetricCard
              label="Cache"
              value={data.cache?.stale ? 'Stale' : data.cache?.hit ? 'Hit' : 'Fresh'}
              tone={data.cache?.stale ? 'warning' : data.cache?.hit ? 'info' : 'neutral'}
            />
          </ReportMetricGrid>
        </ReportSection>

        {data.database_path ? (
          <ReportPanel tone="info" className="text-xs leading-6 text-muted-foreground">
            Foldseek DB path: <code className="font-mono">{data.database_path}</code>
          </ReportPanel>
        ) : null}

        {data.results.length > 0 ? (
          <ReportSection title="Top Hits" icon={Boxes}>
            <div className="space-y-3">
              {data.results.slice(0, 5).map((hit, index) => (
                <ReportPanel key={`${hit.template_id || hit.target_id || index}`} tone="success" className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{renderHitTitle(hit, index)}</span>
                    {hit.source ? <ReportBadge tone="info">{hit.source}</ReportBadge> : null}
                    {hit.template_id ? <ReportBadge tone="neutral">{hit.template_id}</ReportBadge> : null}
                  </div>
                  <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                    <div>score: {hit.score ?? 'N/A'}</div>
                    <div>TM-score: {hit.tm_score ?? 'N/A'}</div>
                    <div>RMSD: {hit.rmsd ?? 'N/A'}</div>
                    <div>identity: {hit.identity ?? 'N/A'}</div>
                  </div>
                  {hit.description ? (
                    <p className="text-xs leading-6 text-muted-foreground">{hit.description}</p>
                  ) : null}
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        ) : null}

        {data.results.length === 0 ? (
          <ReportSection title="Current Status" icon={ShieldAlert}>
            <ReportPanel tone={data.status === 'degraded' ? 'warning' : 'neutral'} className="text-xs leading-6 text-muted-foreground">
              No structural hits were returned yet.
              {data.backend === 'summary_only'
                ? ' Current response is summary-only fallback, which means the structure was parsed but Foldseek search was not executed.'
                : ' Foldseek ran but did not return a matching hit in the current database.'}
            </ReportPanel>
          </ReportSection>
        ) : null}
      </ReportBody>
    </ReportShell>
  )
}
