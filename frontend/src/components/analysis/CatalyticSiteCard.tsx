import { ShieldAlert, ShieldCheck, Target, FlaskConical } from 'lucide-react'
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

interface CatalyticResidue {
  position: number
  residue: string
  role: string
  confidence?: number | null
  pdb_chain?: string | null
  pdb_residue_no?: string | number | null
}

interface CuratedSite {
  source?: string | null
  mechanism_name?: string | null
  reaction_text?: string | null
  residues: CatalyticResidue[]
}

interface InferredGuardrail {
  position: number
  residue: string
  role: string
  confidence: number
  source: string
  evidence: string
}

export interface CatalyticSiteData {
  found: boolean
  error?: string
  query?: {
    uniprot_id?: string | null
    sequence_length?: number
  }
  curated_sites: CuratedSite[]
  inferred_guardrails: InferredGuardrail[]
  protected_positions: number[]
  mutation_guidance?: {
    avoid_positions?: number[]
    rule?: string
  }
  note?: string
}

function SourceTone({ source }: { source: string }) {
  const tone = source === 'curated' ? 'success' : source === 'input' ? 'info' : 'warning'
  const label = source === 'curated' ? 'Curated' : source === 'input' ? 'Input' : 'Heuristic'
  return <ReportBadge tone={tone}>{label}</ReportBadge>
}

export function CatalyticSiteCard({ data }: { data: CatalyticSiteData }) {
  const curatedCount = data.curated_sites.reduce((sum, site) => sum + site.residues.length, 0)
  const inferredCount = data.inferred_guardrails.length

  return (
    <ReportShell>
      <ReportHeader
        icon={Target}
        title="催化位点护栏"
        subtitle={`${data.query?.sequence_length ?? '-'} aa · 保护位点 ${data.protected_positions.length} 个`}
        badge={<ReportBadge tone={data.curated_sites.length > 0 ? 'success' : 'warning'}>{data.curated_sites.length > 0 ? 'Curated' : 'Heuristic'}</ReportBadge>}
      />
      <ReportBody>
        {data.error ? (
          <ReportPanel tone="danger" className="text-xs text-red-700 dark:text-red-300">
            {data.error}
          </ReportPanel>
        ) : null}

        <ReportSection title="Summary">
          <ReportMetricGrid>
            <ReportMetricCard label="保护位点" value={data.protected_positions.length} tone="danger" />
            <ReportMetricCard label="已整理残基" value={curatedCount} tone="success" />
            <ReportMetricCard label="启发式护栏" value={inferredCount} tone="warning" />
            <ReportMetricCard label="UniProt" value={data.query?.uniprot_id || 'N/A'} mono />
          </ReportMetricGrid>
        </ReportSection>

        {data.protected_positions.length > 0 ? (
          <ReportSection title="Protected Positions" icon={ShieldAlert}>
            <ReportPanel tone="danger" className="space-y-3">
              <p className="text-xs leading-6 text-muted-foreground">
                {data.mutation_guidance?.rule || '这些位点应视为高风险位点，未完成人工复核前不要进入突变设计。'}
              </p>
              <div className="flex flex-wrap gap-2">
                {data.protected_positions.map((position) => (
                  <code
                    key={position}
                    className="rounded-md border border-red-500/20 bg-background/70 px-2 py-1 font-mono text-[10px] text-red-600 dark:text-red-300"
                  >
                    {position}
                  </code>
                ))}
              </div>
            </ReportPanel>
          </ReportSection>
        ) : null}

        {data.curated_sites.length > 0 ? (
          <ReportSection title="Curated Catalytic Sites" icon={ShieldCheck}>
            <div className="space-y-3">
              {data.curated_sites.map((site, index) => (
                <ReportPanel key={`${site.source || 'site'}-${index}`} tone="success" className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <SourceTone source="curated" />
                    {site.source ? <ReportBadge tone="neutral">{site.source}</ReportBadge> : null}
                    {site.mechanism_name ? <span className="text-xs font-medium">{site.mechanism_name}</span> : null}
                  </div>
                  {site.reaction_text ? (
                    <p className="text-xs leading-6 text-muted-foreground">{site.reaction_text}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {site.residues.map((residue) => (
                      <div
                        key={`${residue.position}-${residue.role}`}
                        className="rounded-xl border border-emerald-500/15 bg-background/70 px-3 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <code className="font-mono text-[11px] text-emerald-700 dark:text-emerald-300">
                            {residue.residue}
                            {residue.position}
                          </code>
                          <span className="text-[10px] text-muted-foreground">{residue.role}</span>
                        </div>
                        {typeof residue.confidence === 'number' ? (
                          <div className="mt-1 text-[10px] text-muted-foreground">
                            confidence {(residue.confidence * 100).toFixed(0)}%
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        ) : null}

        {data.inferred_guardrails.length > 0 ? (
          <ReportSection title="Heuristic Guardrails" icon={FlaskConical}>
            <div className="space-y-2">
              {data.inferred_guardrails.map((item) => (
                <ReportPanel key={`${item.position}-${item.role}`} tone="warning" className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-[11px] text-amber-700 dark:text-amber-300">
                      {item.residue}
                      {item.position}
                    </code>
                    <span className="text-xs font-medium">{item.role}</span>
                    <SourceTone source={item.source} />
                    <ReportBadge tone="neutral">confidence {(item.confidence * 100).toFixed(0)}%</ReportBadge>
                  </div>
                  <p className="text-xs leading-6 text-muted-foreground">{item.evidence}</p>
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
