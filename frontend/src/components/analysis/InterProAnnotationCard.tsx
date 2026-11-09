import { BookOpen, Layers3, Link2, Sparkles } from 'lucide-react'
import {
  ReportBadge,
  ReportBody,
  ReportDataTable,
  ReportHeader,
  ReportMetricCard,
  ReportMetricGrid,
  ReportPanel,
  ReportSection,
  ReportShell,
} from '@/components/analysis/ReportShell'

interface AnnotationRegion {
  start: number
  end: number
}

interface AnnotationEntry {
  interpro_id?: string | null
  name: string
  entry_type: string
  source: string
  pfam_id?: string | null
  go_terms?: string[]
  regions: AnnotationRegion[]
  score?: number | string | null
  evidence?: string | null
  notes?: string | null
}

export interface InterProAnnotationData {
  found: boolean
  error?: string
  query?: {
    uniprot_id?: string | null
    sequence_length?: number
  }
  summary: {
    curated_interpro_count: number
    pfam_domain_count: number
    heuristic_count: number
  }
  annotations: AnnotationEntry[]
  note?: string
}

function sourceTone(source: string): 'success' | 'info' | 'warning' | 'neutral' {
  if (source === 'interpro') return 'success'
  if (source === 'pfam') return 'info'
  if (source === 'heuristic') return 'warning'
  return 'neutral'
}

function entryTypeLabel(type: string): string {
  const map: Record<string, string> = {
    family: '家族',
    domain: '结构域',
    repeat: '重复单元',
    site: '功能位点',
  }
  return map[type] || type
}

function formatRegions(regions: AnnotationRegion[]): string {
  if (!regions.length) return 'N/A'
  return regions.map((region) => `${region.start}-${region.end}`).join(', ')
}

export function InterProAnnotationCard({ data }: { data: InterProAnnotationData }) {
  const curatedAnnotations = data.annotations.filter((item) => item.source === 'interpro')
  const domainAnnotations = data.annotations.filter((item) => item.entry_type === 'domain' || item.source === 'pfam')
  const heuristicAnnotations = data.annotations.filter((item) => item.source === 'heuristic')

  return (
    <ReportShell>
      <ReportHeader
        icon={BookOpen}
        title="InterPro 功能注释"
        subtitle={`${data.query?.sequence_length ?? '-'} aa · ${data.query?.uniprot_id || 'sequence mode'}`}
        badge={<ReportBadge tone={data.found ? 'success' : 'neutral'}>{data.found ? 'Annotated' : 'No Hit'}</ReportBadge>}
      />
      <ReportBody>
        {data.error ? (
          <ReportPanel tone="danger" className="text-xs text-red-700 dark:text-red-300">
            {data.error}
          </ReportPanel>
        ) : null}

        <ReportSection title="Summary">
          <ReportMetricGrid>
            <ReportMetricCard label="Curated InterPro" value={data.summary.curated_interpro_count} tone="success" />
            <ReportMetricCard label="Pfam Domains" value={data.summary.pfam_domain_count} tone="info" />
            <ReportMetricCard label="Heuristic Hints" value={data.summary.heuristic_count} tone="warning" />
            <ReportMetricCard label="Total Entries" value={data.annotations.length} />
          </ReportMetricGrid>
        </ReportSection>

        {curatedAnnotations.length > 0 ? (
          <ReportSection title="Curated Entries" icon={Sparkles}>
            <div className="space-y-2">
              {curatedAnnotations.map((item, index) => (
                <ReportPanel key={`${item.interpro_id || item.name}-${index}`} tone="success" className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {item.interpro_id ? <code className="font-mono text-[11px] text-emerald-700 dark:text-emerald-300">{item.interpro_id}</code> : null}
                    <span className="text-sm font-medium">{item.name}</span>
                    <ReportBadge tone="success">{entryTypeLabel(item.entry_type)}</ReportBadge>
                    <ReportBadge tone={sourceTone(item.source)}>{item.source}</ReportBadge>
                  </div>
                  <div className="text-xs text-muted-foreground">区域: {formatRegions(item.regions)}</div>
                  {item.go_terms && item.go_terms.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {item.go_terms.map((term) => (
                        <ReportBadge key={term} tone="neutral">
                          {term}
                        </ReportBadge>
                      ))}
                    </div>
                  ) : null}
                  {item.evidence ? <p className="text-xs leading-6 text-muted-foreground">{item.evidence}</p> : null}
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        ) : null}

        {domainAnnotations.length > 0 ? (
          <ReportSection title="Domain Architecture" icon={Layers3}>
            <ReportDataTable>
              <thead>
                <tr className="border-b border-border/70 text-left text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Region</th>
                  <th className="px-4 py-3 font-medium">ID</th>
                </tr>
              </thead>
              <tbody>
                {domainAnnotations.map((item, index) => (
                  <tr key={`${item.name}-${index}`} className="border-b border-border/50 last:border-b-0">
                    <td className="px-4 py-3 text-sm">{item.name}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{entryTypeLabel(item.entry_type)}</td>
                    <td className="px-4 py-3">
                      <ReportBadge tone={sourceTone(item.source)}>{item.source}</ReportBadge>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{formatRegions(item.regions)}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{item.pfam_id || item.interpro_id || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </ReportDataTable>
          </ReportSection>
        ) : null}

        {heuristicAnnotations.length > 0 ? (
          <ReportSection title="Heuristic Functional Hints" icon={Link2}>
            <div className="space-y-2">
              {heuristicAnnotations.map((item, index) => (
                <ReportPanel key={`${item.name}-${index}`} tone="warning" className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {item.interpro_id ? <code className="font-mono text-[11px] text-amber-700 dark:text-amber-300">{item.interpro_id}</code> : null}
                    <span className="text-sm font-medium">{item.name}</span>
                    <ReportBadge tone="warning">{entryTypeLabel(item.entry_type)}</ReportBadge>
                  </div>
                  <div className="text-xs text-muted-foreground">命中区域: {formatRegions(item.regions)}</div>
                  {item.notes ? <p className="text-xs leading-6 text-muted-foreground">{item.notes}</p> : null}
                  {item.go_terms && item.go_terms.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {item.go_terms.map((term) => (
                        <ReportBadge key={term} tone="neutral">
                          {term}
                        </ReportBadge>
                      ))}
                    </div>
                  ) : null}
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        ) : null}

        {data.note ? (
          <ReportPanel tone="neutral" className="text-xs leading-6 text-muted-foreground">
            {data.note}
          </ReportPanel>
        ) : null}
      </ReportBody>
    </ReportShell>
  )
}
