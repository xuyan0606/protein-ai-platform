import { useState, useMemo } from 'react'
import type { ReactElement } from 'react'
import type { ToolCall } from '@/stores/chat'
import { Loader2, CheckCircle2, XCircle, Clock, Dna, ChevronDown, ChevronUp } from 'lucide-react'
import { ProteinViewer } from '@/components/viewer/ProteinViewer'
import { BenchmarkReport } from '@/components/analysis/BenchmarkReport'
import { MutationScoreCard } from '@/components/analysis/MutationScoreCard'
import { BlastResultView } from '@/components/analysis/BlastResultView'
import { MDResultView } from '@/components/analysis/MDResultView'
import { RFdiffusionResult } from '@/components/analysis/RFdiffusionResult'
import { AnnotationBundleCard } from '@/components/analysis/AnnotationBundleCard'
import { CatalyticSiteCard } from '@/components/analysis/CatalyticSiteCard'
import { SignalPeptideCard } from '@/components/analysis/SignalPeptideCard'
import { InterProAnnotationCard } from '@/components/analysis/InterProAnnotationCard'
import { SiteStructureFunctionFeaturesCard } from '@/components/analysis/SiteStructureFunctionFeaturesCard'
import {
  isAnnotationBundleResult,
  isBenchmarkResult,
  isBlastResult,
  isCatalyticSiteResult,
  isInterProAnnotationResult,
  isMDResult,
  isMutationScoreResult,
  isRFdiffusionResult,
  isSignalPeptideResult,
  isSiteStructureFunctionFeaturesResult,
} from '@/components/analysis/resultGuards'

interface Props {
  toolCall: ToolCall
}

interface EvidenceSource {
  status?: string
  mode?: string
  source?: string
  reason?: string
  live_query_executed?: boolean
}

const FOLDING_TOOLS = ['esmfold_folding', 'alphafold_folding', 'alphafold2_folding', 'rosettafold_folding']

function extractPdbData(resultPreview: string): string | null {
  // Try to find PDB content in the result preview
  if (resultPreview.includes('ATOM') || resultPreview.includes('HEADER')) return resultPreview
  // Try parsing as JSON and looking for pdb/pdb_content/pdb_data fields
  try {
    const obj = JSON.parse(resultPreview.replace(/'/g, '"'))
    const pdb = obj.pdb || obj.pdb_content || obj.pdb_data || obj.structure
    if (typeof pdb === 'string' && (pdb.includes('ATOM') || pdb.includes('HEADER'))) return pdb
  } catch { /* not JSON */ }
  return null
}

function tryParseResult(preview: string | undefined): unknown | null {
  if (!preview) return null
  try {
    return JSON.parse(preview.replace(/'/g, '"'))
  } catch {
    return null
  }
}

function extractEvidenceSource(data: unknown): EvidenceSource | null {
  if (!data || typeof data !== 'object') return null
  const record = data as Record<string, unknown>
  const source = record.evidence_source
  if (!source || typeof source !== 'object') return null
  return source as EvidenceSource
}

function evidenceBadgeStyle(status?: string): string {
  if (status === 'live') return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
  if (status === 'blocked') return 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300'
  if (status === 'degraded') return 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300'
  return 'border-border/70 bg-secondary/55 text-muted-foreground'
}

function evidenceBadgeLabel(source: EvidenceSource): string {
  if (source.status === 'live' && source.live_query_executed) return 'Live'
  if (source.status === 'degraded') return 'Degraded'
  if (source.status === 'blocked') return 'Blocked'
  return source.status || 'Evidence'
}

const ANALYSIS_TOOLS = [
  'protein_benchmark',
  'mutation_priority_score',
  'rosetta_ddg',
  'blast_search',
  'sequence_search',
  'interpro_live_lookup',
  'literature_live_search',
  'gromacs_md',
  'rfdiffusion_design',
  'catalytic_site_lookup',
  'signal_peptide_predict',
  'interpro_annotation',
  'annotation_bundle',
  'build_site_structure_function_features',
]

function isRosettaResult(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return record.tool === 'rosetta_ddg' || 'requested_mutations' in record || 'scorefile_rows' in record
}

function RosettaDdgCard({ data }: { data: Record<string, unknown> }) {
  const results = Array.isArray(data.results) ? data.results as Array<Record<string, unknown>> : []
  const missing = Array.isArray(data.missing) ? data.missing.map(String).join(', ') : ''
  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-[10px] uppercase text-muted-foreground">Status</p>
          <p className="font-medium">{String(data.status || 'unknown')}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-muted-foreground">Real Rosetta</p>
          <p className="font-medium">{data.is_real_rosetta ? 'yes' : 'no'}</p>
        </div>
      </div>
      {Boolean(data.reason) && <p className="text-amber-600">Blocked: {String(data.reason)}</p>}
      {missing && <p className="text-muted-foreground">Missing: {missing}</p>}
      {results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-border">
                <th className="py-1 pr-3 font-medium">Mutation</th>
                <th className="py-1 pr-3 font-medium">ΔΔG</th>
                <th className="py-1 pr-3 font-medium">Class</th>
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 8).map((item, idx) => (
                <tr key={idx} className="border-b border-border/50">
                  <td className="py-1 pr-3 font-mono">{String(item.mutation || '-')}</td>
                  <td className="py-1 pr-3 font-mono">{String(item.ddg_kcal_mol ?? '-')}</td>
                  <td className="py-1 pr-3">{String(item.ddg_label || '-')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-muted-foreground">负值表示更稳定；正值表示更不稳定。所有候选都需要人工核实编号、链映射和活性位点影响。</p>
    </div>
  )
}

const ANALYSIS_RENDERERS = {
  protein_benchmark: (data: unknown) => isBenchmarkResult(data) ? <BenchmarkReport data={data} /> : null,
  mutation_priority_score: (data: unknown) => isMutationScoreResult(data) ? <MutationScoreCard data={data} /> : null,
  rosetta_ddg: (data: unknown) => isRosettaResult(data) ? <RosettaDdgCard data={data} /> : null,
  blast_search: (data: unknown) => isBlastResult(data) ? <BlastResultView data={data} /> : null,
  gromacs_md: (data: unknown) => isMDResult(data) ? <MDResultView data={data} /> : null,
  rfdiffusion_design: (data: unknown) => isRFdiffusionResult(data) ? <RFdiffusionResult data={data} /> : null,
  catalytic_site_lookup: (data: unknown) => isCatalyticSiteResult(data) ? <CatalyticSiteCard data={data} /> : null,
  signal_peptide_predict: (data: unknown) => isSignalPeptideResult(data) ? <SignalPeptideCard data={data} /> : null,
  interpro_annotation: (data: unknown) => isInterProAnnotationResult(data) ? <InterProAnnotationCard data={data} /> : null,
  annotation_bundle: (data: unknown) => isAnnotationBundleResult(data) ? <AnnotationBundleCard data={data} /> : null,
  build_site_structure_function_features: (data: unknown) => isSiteStructureFunctionFeaturesResult(data) ? <SiteStructureFunctionFeaturesCard data={data} /> : null,
} satisfies Record<string, (data: unknown) => ReactElement | null>

export function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false)
  const statusIcon = {
    pending: <Clock className="w-4 h-4 text-muted-foreground" />,
    running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
    submitted: <Clock className="w-4 h-4 text-blue-500" />,
    completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
    failed: <XCircle className="w-4 h-4 text-red-500" />,
  }

  const isFolding = FOLDING_TOOLS.includes(toolCall.name)
  const pdbData = toolCall.resultPreview ? extractPdbData(toolCall.resultPreview) : null
  const hasStructure = isFolding && toolCall.status === 'completed' && pdbData
  const parsedResult = useMemo(() => {
    if (toolCall.status !== 'completed') return null
    return tryParseResult(toolCall.resultPreview)
  }, [toolCall.status, toolCall.resultPreview])
  const evidenceSource = useMemo(() => extractEvidenceSource(parsedResult), [parsedResult])

  // Parse result for analysis tools
  const analysisResult = useMemo(() => {
    if (!ANALYSIS_TOOLS.includes(toolCall.name) || toolCall.status !== 'completed') return null
    return parsedResult
  }, [parsedResult, toolCall.name, toolCall.status])

  const analysisView = useMemo(() => {
    if (!analysisResult) return null
    const renderer = ANALYSIS_RENDERERS[toolCall.name as keyof typeof ANALYSIS_RENDERERS]
    return renderer ? renderer(analysisResult) : null
  }, [analysisResult, toolCall.name])

  const hasAnalysisView = analysisView !== null
  const hasRawPreview = Boolean(toolCall.resultPreview && !hasStructure && !hasAnalysisView)
  const hasRawToolResult = Boolean(toolCall.rawResult)
  const hasExpandable = hasStructure || hasAnalysisView || hasRawPreview || hasRawToolResult
  const statusLabel = {
    pending: 'Pending',
    running: 'Running',
    submitted: 'Submitted',
    completed: 'Complete',
    failed: 'Failed',
  }[toolCall.status]

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/55 shadow-[0_6px_20px_rgba(15,23,42,0.03)]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-secondary/15"
      >
        {statusIcon[toolCall.status]}
        <span className="flex items-center gap-1.5 text-[13px] font-medium text-foreground/88">
          {toolCall.name}
          {hasStructure && <Dna className="w-3 h-3 text-blue-400" />}
        </span>
        <span className="rounded-full bg-secondary/80 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          {statusLabel}
        </span>
        {evidenceSource && (
          <span
            className={`max-w-[170px] truncate rounded-full border px-2 py-0.5 text-[10px] font-medium ${evidenceBadgeStyle(evidenceSource.status)}`}
            title={`${evidenceSource.source || 'evidence'} · ${evidenceSource.mode || 'unknown'}${evidenceSource.reason ? ` · ${evidenceSource.reason}` : ''}`}
          >
            {evidenceBadgeLabel(evidenceSource)}
          </span>
        )}
        {toolCall.duration && (
          <span className="text-[11px] text-muted-foreground">
            {toolCall.duration}s
          </span>
        )}
        <div className="flex-1" />
        {hasExpandable && (
          expanded ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />
        )}
      </button>

      {toolCall.status === 'running' && (
        <div className="px-3 pb-2">
          <div className="w-full bg-secondary rounded-full h-1 overflow-hidden">
            <div className="bg-blue-500/85 h-1 rounded-full w-2/3" />
          </div>
        </div>
      )}

      {toolCall.error && (
        <p className="px-3 pb-2 text-xs text-red-500">{toolCall.error}</p>
      )}

      {expanded && hasStructure && (
        <div className="px-3 pb-3">
          <ProteinViewer pdbData={pdbData!} height={250} />
        </div>
      )}

      {expanded && hasAnalysisView && !hasStructure && (
        <div className="px-3 pb-3">
          {analysisView}
        </div>
      )}

      {expanded && hasRawPreview && (
        <pre className="mx-3 mb-3 max-h-56 overflow-auto rounded-md bg-secondary/40 p-3 text-xs leading-relaxed text-muted-foreground">
          {toolCall.resultPreview}
        </pre>
      )}

      {expanded && hasRawToolResult && (
        <div className="mx-3 mb-3">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Raw tool response
          </div>
          <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-100">
            {toolCall.rawResult}
          </pre>
        </div>
      )}
    </div>
  )
}
