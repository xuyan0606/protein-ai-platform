import { useMemo, useState } from 'react'
import { Dna, Layers, Ruler, Zap, Grid3X3, Copy, Check, Target } from 'lucide-react'
import { ProteinViewer } from '@/components/viewer/ProteinViewer'
import { MarkdownView } from '@/components/chat/MarkdownView'
import { ReportBadge, ReportBody, ReportHeader, ReportMetricCard, ReportMetricGrid, ReportPanel, ReportSection, ReportShell } from '@/components/analysis/ReportShell'

interface ChainData {
  chain_id: string
  sequence: string
  residue_count: number
  atom_count: number
  residue_range: [number, number] | null
}

export interface PDBAnalysisData {
  header?: { title?: string }
  chains: ChainData[]
  resolution?: number | null
  r_factor?: number | null
  space_group?: string | null
  unit_cell?: Record<string, number> | null
  b_factor_stats?: { mean: number; min: number; max: number } | null
  total_atoms: number
  total_residues: number
  seqres_sequence?: string | null
  method?: string | null
  deposited_date?: string | null
  object_name?: string
  download_url?: string
  file_name?: string
  file_size?: number
  ai_summary?: string
  summary_model?: string
  summary_model_id?: string
  lipaseEvidenceContext?: {
    status?: string
    counts?: {
      exact_mutation_matches?: number
      position_matches?: number
      search_matches?: number
    }
    strongest_evidence_level?: string
    recommended_use?: string
    requested_mutations?: string[]
    requested_positions?: number[]
  }
}

interface Props {
  data: PDBAnalysisData
  pdbContent?: string
  highlightResidues?: Array<{
    chainId?: string | null
    residueNumber: number
    color?: string
    source?: 'curated' | 'inferred' | 'lipase'
  }>
  highlightRanges?: Array<{
    chainId?: string | null
    startResidue: number
    endResidue: number
    color?: string
    source?: 'signal_h' | 'signal_c' | 'interpro' | 'pfam'
  }>
  highlightSummary?: {
    protectedCount: number
    mappedCount: number
    curatedCount?: number
    inferredCount?: number
    lipaseCount?: number
    lipaseEvidencePositionCount?: number
    signalRegionCount?: number
    domainRegionCount?: number
    mappingSource?: string | null
    mappingLimitations?: number
    chainId?: string | null
  } | null
}

type OverlayLayerKey = 'curated' | 'inferred' | 'lipase' | 'signal' | 'domain'

const OVERLAY_LAYER_META: Array<{
  key: OverlayLayerKey
  label: string
  accentClass: string
}> = [
  { key: 'curated', label: 'Curated sites', accentClass: 'bg-emerald-500' },
  { key: 'inferred', label: 'Inferred sites', accentClass: 'bg-red-500' },
  { key: 'lipase', label: 'Lipase evidence', accentClass: 'bg-teal-500' },
  { key: 'signal', label: 'Signal regions', accentClass: 'bg-sky-500' },
  { key: 'domain', label: 'Domain regions', accentClass: 'bg-amber-500' },
]

function getResidueLayer(source?: 'curated' | 'inferred' | 'lipase'): OverlayLayerKey | null {
  if (source === 'curated' || source === 'inferred' || source === 'lipase') return source
  return null
}

function getRangeLayer(source?: 'signal_h' | 'signal_c' | 'interpro' | 'pfam'): OverlayLayerKey | null {
  if (source === 'signal_h' || source === 'signal_c') return 'signal'
  if (source === 'interpro' || source === 'pfam') return 'domain'
  return null
}

export function PDBAnalysisCard({ data, pdbContent, highlightResidues = [], highlightRanges = [], highlightSummary = null }: Props) {
  const [copiedChain, setCopiedChain] = useState<string | null>(null)
  const [activeLayers, setActiveLayers] = useState<Record<OverlayLayerKey, boolean>>({
    curated: true,
    inferred: true,
    lipase: true,
    signal: true,
    domain: true,
  })

  const overlayCounts = useMemo(() => ({
    curated: highlightResidues.filter((item) => getResidueLayer(item.source) === 'curated').length,
    inferred: highlightResidues.filter((item) => getResidueLayer(item.source) === 'inferred').length,
    lipase: highlightResidues.filter((item) => getResidueLayer(item.source) === 'lipase').length,
    signal: highlightRanges.filter((item) => getRangeLayer(item.source) === 'signal').length,
    domain: highlightRanges.filter((item) => getRangeLayer(item.source) === 'domain').length,
  }), [highlightRanges, highlightResidues])

  const filteredHighlightResidues = useMemo(
    () => highlightResidues.filter((item) => {
      const layer = getResidueLayer(item.source)
      return layer ? activeLayers[layer] !== false : true
    }),
    [activeLayers, highlightResidues],
  )

  const filteredHighlightRanges = useMemo(
    () => highlightRanges.filter((item) => {
      const layer = getRangeLayer(item.source)
      return layer ? activeLayers[layer] !== false : true
    }),
    [activeLayers, highlightRanges],
  )

  const totalOverlayCount = highlightResidues.length + highlightRanges.length
  const activeOverlayCount = filteredHighlightResidues.length + filteredHighlightRanges.length
  const hasOverlayData = totalOverlayCount > 0
  const visibleChains = useMemo(() => {
    const chains = new Set<string>()
    for (const item of filteredHighlightResidues) {
      if (item.chainId) chains.add(item.chainId)
    }
    for (const item of filteredHighlightRanges) {
      if (item.chainId) chains.add(item.chainId)
    }
    return Array.from(chains).sort()
  }, [filteredHighlightRanges, filteredHighlightResidues])
  const overlaySummary = (
    highlightSummary && (
      highlightSummary.protectedCount > 0 ||
      highlightSummary.signalRegionCount ||
      highlightSummary.domainRegionCount ||
      highlightSummary.lipaseCount ||
      highlightSummary.mappedCount > 0
    )
  ) ? highlightSummary : null

  const copySequence = async (seq: string, chainId: string) => {
    await navigator.clipboard.writeText(seq)
    setCopiedChain(chainId)
    setTimeout(() => setCopiedChain(null), 2000)
  }

  return (
    <ReportShell>
      <ReportHeader
        icon={Dna}
        title={data.header?.title || data.file_name || 'PDB Structure'}
        subtitle={
          <>
            {data.method && `${data.method} · `}
            {data.deposited_date && `${data.deposited_date} · `}
            {data.total_residues} residues · {data.total_atoms} atoms
          </>
        }
        badge={<ReportBadge tone="info">Structure Report</ReportBadge>}
      />

      {/* 3D Viewer */}
      {pdbContent && (
        <div className="border-b border-border/70 bg-secondary/10 px-4 py-4 sm:px-6">
          <ProteinViewer
            pdbData={pdbContent}
            height={320}
            highlightResidues={filteredHighlightResidues}
            highlightRanges={filteredHighlightRanges}
          />
        </div>
      )}

      <ReportBody>
        <ReportSection title="Core Metrics">
          <ReportMetricGrid>
            {data.resolution && (
              <Metric icon={Ruler} label="Resolution" value={`${data.resolution} Å`} />
            )}
            {data.r_factor && (
              <Metric icon={Layers} label="R-factor" value={`${data.r_factor}`} />
            )}
            {data.space_group && (
              <Metric icon={Grid3X3} label="Space Group" value={data.space_group} />
            )}
            {data.b_factor_stats && (
              <Metric
                icon={Zap}
                label="B-factor"
                value={`${data.b_factor_stats.mean}`}
                meta={`${data.b_factor_stats.min} - ${data.b_factor_stats.max}`}
              />
            )}
          </ReportMetricGrid>
        </ReportSection>

        {overlaySummary ? (
          <ReportSection title="Structure Overlay" icon={Target}>
            <ReportPanel tone={overlaySummary.mappedCount > 0 ? 'success' : 'warning'} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ReportBadge tone={overlaySummary.mappedCount > 0 ? 'success' : 'warning'}>
                  {activeOverlayCount > 0 ? 'Highlights Active' : 'Layers Hidden'}
                </ReportBadge>
                {hasOverlayData ? <ReportBadge tone="neutral">visible {activeOverlayCount} / {totalOverlayCount}</ReportBadge> : null}
                {visibleChains.map((chainId) => (
                  <ReportBadge key={chainId} tone="info">Chain {chainId}</ReportBadge>
                ))}
                {overlaySummary.mappingSource ? <ReportBadge tone="neutral">{overlaySummary.mappingSource}</ReportBadge> : null}
              </div>
              <p className="text-xs leading-6 text-muted-foreground">
                {overlaySummary.protectedCount > 0
                  ? `${overlaySummary.mappedCount} / ${overlaySummary.protectedCount} protected positions are mapped onto the displayed structure.`
                  : overlaySummary.lipaseCount
                    ? `${overlaySummary.lipaseCount} / ${overlaySummary.lipaseEvidencePositionCount ?? overlaySummary.lipaseCount} lipase evidence positions are mapped onto the displayed structure.`
                    : 'Region overlays are available for the displayed structure.'}
              </p>
              {overlaySummary.mappingLimitations ? (
                <p className="text-xs leading-6 text-muted-foreground">
                  Mapping returned {overlaySummary.mappingLimitations} limitation note(s); treat inferred overlays as guidance, not residue-exact truth.
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <ReportBadge tone="success">curated {overlaySummary.curatedCount ?? 0}</ReportBadge>
                <ReportBadge tone="danger">inferred {overlaySummary.inferredCount ?? 0}</ReportBadge>
                <ReportBadge tone="success">lipase {overlaySummary.lipaseCount ?? 0}</ReportBadge>
                <ReportBadge tone="info">signal regions {overlaySummary.signalRegionCount ?? 0}</ReportBadge>
                <ReportBadge tone="warning">domain regions {overlaySummary.domainRegionCount ?? 0}</ReportBadge>
              </div>
              {hasOverlayData ? (
                <>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      onClick={() => setActiveLayers({ curated: true, inferred: true, lipase: true, signal: true, domain: true })}
                      className="rounded-lg border border-border/70 px-2.5 py-1 text-xs text-foreground/80 transition-colors hover:bg-background/70"
                    >
                      Show all
                    </button>
                    <button
                      onClick={() => setActiveLayers({ curated: false, inferred: false, lipase: false, signal: false, domain: false })}
                      className="rounded-lg border border-border/70 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-background/70"
                    >
                      Hide all
                    </button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {OVERLAY_LAYER_META.filter((layer) => overlayCounts[layer.key] > 0).map((layer) => (
                      <button
                        key={layer.key}
                        onClick={() => setActiveLayers((previous) => ({ ...previous, [layer.key]: !previous[layer.key] }))}
                        className={`flex items-center justify-between rounded-xl border px-3 py-2 text-left transition-colors ${
                          activeLayers[layer.key]
                            ? 'border-border bg-background/80 text-foreground'
                            : 'border-border/50 bg-secondary/20 text-muted-foreground'
                        }`}
                      >
                        <span className="inline-flex items-center gap-2 text-sm font-medium">
                          <span className={`h-2.5 w-2.5 rounded-full ${layer.accentClass}`} />
                          {layer.label}
                        </span>
                        <span className="text-xs">{overlayCounts[layer.key]}</span>
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
            </ReportPanel>
          </ReportSection>
        ) : null}

        {data.lipaseEvidenceContext ? (
          <ReportSection title="KWB Lipase Evidence" icon={Target}>
            <ReportPanel tone={(data.lipaseEvidenceContext.counts?.exact_mutation_matches || 0) > 0 ? 'success' : 'neutral'} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ReportBadge tone="info">{data.lipaseEvidenceContext.status || 'unknown'}</ReportBadge>
                <ReportBadge tone="success">exact {data.lipaseEvidenceContext.counts?.exact_mutation_matches ?? 0}</ReportBadge>
                <ReportBadge tone="warning">position {data.lipaseEvidenceContext.counts?.position_matches ?? 0}</ReportBadge>
                <ReportBadge tone="neutral">search {data.lipaseEvidenceContext.counts?.search_matches ?? 0}</ReportBadge>
                {data.lipaseEvidenceContext.strongest_evidence_level ? (
                  <ReportBadge tone="neutral">{data.lipaseEvidenceContext.strongest_evidence_level}</ReportBadge>
                ) : null}
              </div>
              <p className="text-xs leading-6 text-muted-foreground">
                {data.lipaseEvidenceContext.recommended_use || 'Use exact mutation matches as curated evidence; treat position-only matches as weak context until numbering is confirmed.'}
              </p>
            </ReportPanel>
          </ReportSection>
        ) : null}

        {data.unit_cell && (
          <ReportSection title="Unit Cell">
            <ReportPanel tone="neutral" className="text-sm leading-7 text-foreground/82">
              <span className="font-medium text-foreground">a</span>={data.unit_cell.a} {'  '}
              <span className="font-medium text-foreground">b</span>={data.unit_cell.b} {'  '}
              <span className="font-medium text-foreground">c</span>={data.unit_cell.c} {'  '}
              <span className="font-medium text-foreground">α</span>={data.unit_cell.alpha}° {'  '}
              <span className="font-medium text-foreground">β</span>={data.unit_cell.beta}° {'  '}
              <span className="font-medium text-foreground">γ</span>={data.unit_cell.gamma}°
            </ReportPanel>
          </ReportSection>
        )}

        {data.ai_summary && (
          <ReportSection
            title="AI Summary"
            action={data.summary_model ? <ReportBadge tone="info">{data.summary_model}</ReportBadge> : null}
          >
            <ReportPanel tone="info">
              <MarkdownView content={data.ai_summary} />
            </ReportPanel>
          </ReportSection>
        )}

        <ReportSection title={`Chains (${data.chains.length})`}>
          {data.chains.map((chain) => (
            <div
              key={chain.chain_id}
              className="space-y-3 rounded-2xl border border-border/70 bg-secondary/20 p-3.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-primary/15 bg-primary/10 text-xs font-bold text-primary">
                    {chain.chain_id}
                  </span>
                  <span className="text-sm font-medium tracking-[0.01em]">
                    Chain {chain.chain_id}
                  </span>
                </div>
                <span className="text-[11px] leading-5 text-muted-foreground">
                  {chain.residue_count} residues · {chain.atom_count} atoms
                  {chain.residue_range && ` · ${chain.residue_range[0]}-${chain.residue_range[1]}`}
                </span>
              </div>

              <div className="relative">
                <pre className="max-h-28 overflow-x-auto overflow-y-auto rounded-xl border border-border/60 bg-background/70 p-3 text-[11px] leading-6 text-foreground/85 whitespace-pre-wrap break-all font-mono">
                  {chain.sequence}
                </pre>
                <button
                  onClick={() => copySequence(chain.sequence, chain.chain_id)}
                  className="absolute right-2 top-2 rounded-lg border border-border/60 bg-card/80 p-1 text-muted-foreground transition-colors hover:text-foreground"
                  title="Copy sequence"
                >
                  {copiedChain === chain.chain_id ? (
                    <Check className="w-3 h-3 text-green-500" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>
            </div>
          ))}
        </ReportSection>
      </ReportBody>
    </ReportShell>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
  meta,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  meta?: string
}) {
  return (
    <ReportMetricCard
      label={
        <span className="inline-flex items-center gap-1.5">
          <Icon className="h-3 w-3 text-primary" />
          {label}
        </span>
      }
      value={value}
      meta={meta}
      mono
    />
  )
}
