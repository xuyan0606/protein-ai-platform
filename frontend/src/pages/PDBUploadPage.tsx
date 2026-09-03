import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useChatStore } from '@/stores/chat'
import { Dna, Upload, CheckCircle, AlertCircle, Loader2, ArrowRight, ChevronLeft } from 'lucide-react'
import { PDBAnalysisCard, type PDBAnalysisData } from '@/components/analysis/PDBAnalysisCard'
import { MDResultView } from '@/components/analysis/MDResultView'
import { AnnotationBundleCard, StructureMappingCard, StructureSearchResultCard } from '@/components/analysis'
import { isAnnotationBundleResult, isMDResult, isStructureMappingResult, isStructureSearchResult } from '@/components/analysis/resultGuards'
import { api, authFetch, normalizeFileDownloadUrl, uploadFormWithProgress, type LigandPreprocessResult, type LipaseEvidenceContext, type MdProtocol } from '@/lib/api'

interface AnalysisResult extends PDBAnalysisData {
  object_name?: string
  download_url?: string
  lipaseEvidenceContext?: PDBAnalysisData['lipaseEvidenceContext']
}

function formatMdStatus(status: string | null) {
  const normalized = (status || '').toLowerCase()
  const labels: Record<string, string> = {
    submitting: 'Submitting',
    queued: 'Queued',
    pending: 'Pending',
    running: 'Running',
    started: 'Running',
    completed: 'Completed',
    success: 'Completed',
    failed: 'Failed',
    failure: 'Failed',
    canceled: 'Canceled',
    revoked: 'Canceled',
    cancel_requested: 'Cancel requested',
  }
  return labels[normalized] || (status || 'Unknown')
}

function mdStatusTone(status: string | null) {
  const normalized = (status || '').toLowerCase()
  if (normalized === 'completed' || normalized === 'success') return 'text-emerald-600 dark:text-emerald-300'
  if (normalized === 'failed' || normalized === 'failure') return 'text-red-500 dark:text-red-300'
  if (normalized === 'canceled' || normalized === 'revoked') return 'text-amber-600 dark:text-amber-300'
  if (normalized === 'cancel_requested') return 'text-amber-600 dark:text-amber-300'
  return 'text-blue-600 dark:text-blue-300'
}

function clampProgress(progress: number | null) {
  if (typeof progress !== 'number' || Number.isNaN(progress)) return null
  return Math.max(0, Math.min(100, Math.round(progress)))
}

function formatMdStep(currentStep: number | null, totalSteps: number | null) {
  if (typeof currentStep !== 'number' || typeof totalSteps !== 'number' || totalSteps <= 0) return null
  return `${currentStep}/${totalSteps}`
}

function formatLigandBool(value: boolean | undefined) {
  if (value === true) return 'yes'
  if (value === false) return 'no'
  return 'unknown'
}

function ligandStatusTone(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  if (normalized === 'completed' || normalized === 'ready') return 'text-emerald-600 dark:text-emerald-300'
  if (normalized === 'failed') return 'text-red-500 dark:text-red-300'
  if (normalized === 'blocked') return 'text-amber-600 dark:text-amber-300'
  return 'text-blue-600 dark:text-blue-300'
}

function isReliableStructureMapping(mappingResult: unknown) {
  if (!isStructureMappingResult(mappingResult)) return false
  const source = String(mappingResult.source || '').toLowerCase()
  if (source.includes('inferred')) return false
  return (mappingResult.limitations || []).length === 0
}

function evidenceLevelRank(level?: string | null) {
  const normalized = String(level || 'none').toLowerCase()
  const ranks: Record<string, number> = {
    none: 0,
    text_mining: 1,
    database_only: 2,
    article_level: 3,
    assay_level: 4,
    direct_assay: 5,
  }
  return ranks[normalized] ?? 1
}

function strongestEvidenceLevel(levels: Array<string | undefined>) {
  return levels.reduce((best, candidate) => (
    evidenceLevelRank(candidate) > evidenceLevelRank(best) ? candidate : best
  ), 'none')
}

function LigandPreflightCard({
  result,
  error,
}: {
  result: LigandPreprocessResult | null
  error: string | null
}) {
  if (!result && !error) return null

  const sdf = result?.sdf
  const stageResults = result?.stage_results || []
  const missingRuntime = stageResults
    .flatMap((stage) => stage.missing_requirements || [])
    .filter((item, index, items) => items.indexOf(item) === index)

  return (
    <div className="overflow-hidden rounded-2xl border border-cyan-200/80 bg-[linear-gradient(180deg,rgba(240,253,250,0.96),rgba(255,255,255,0.98))] p-4 text-sm shadow-sm dark:border-cyan-900/60 dark:bg-[linear-gradient(180deg,rgba(22,78,99,0.28),rgba(15,23,42,0.95))]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">
            Ligand Preflight
          </div>
          <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-50">
            2D SDF {'->'} docking/MD readiness
          </div>
          <div className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">
            This card is a contract check. It does not fake PDBQT, Vina docking, or topology artifacts when runtime is missing.
          </div>
        </div>
        {result && (
          <span className={`rounded-full border border-current/20 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${ligandStatusTone(result.status)}`}>
            {result.status}
          </span>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      {sdf && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl bg-white/70 px-3 py-2 dark:bg-slate-900/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Dimension</div>
            <div className="mt-1 font-semibold text-slate-900 dark:text-slate-50">
              {sdf.inferred_dimension || 'unknown'}
            </div>
            <div className="text-xs text-slate-500">2D SDF: {formatLigandBool(sdf.is_2d_sdf)}</div>
          </div>
          <div className="rounded-xl bg-white/70 px-3 py-2 dark:bg-slate-900/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Atoms / Bonds</div>
            <div className="mt-1 font-semibold text-slate-900 dark:text-slate-50">
              {sdf.atom_count ?? '—'} / {sdf.bond_count ?? '—'}
            </div>
            <div className="text-xs text-slate-500">all Z zero: {formatLigandBool(sdf.all_z_zero)}</div>
          </div>
          <div className="rounded-xl bg-white/70 px-3 py-2 dark:bg-slate-900/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Header</div>
            <div className="mt-1 font-semibold text-slate-900 dark:text-slate-50">
              {sdf.header_dimension || 'unknown'}
            </div>
            <div className="text-xs text-slate-500">source SDF inspection</div>
          </div>
          <div className="rounded-xl bg-white/70 px-3 py-2 dark:bg-slate-900/70">
            <div className="text-[11px] uppercase tracking-[0.16em] text-slate-400">Elements</div>
            <div className="mt-1 truncate font-mono text-xs text-slate-700 dark:text-slate-200">
              {sdf.element_counts ? Object.entries(sdf.element_counts).map(([key, value]) => `${key}${value}`).join(' ') : '—'}
            </div>
            <div className="text-xs text-slate-500">composition preview</div>
          </div>
        </div>
      )}

      {missingRuntime.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          Missing runtime: {missingRuntime.join(', ')}
        </div>
      )}

      {stageResults.length > 0 && (
        <div className="mt-4 space-y-2">
          {stageResults.map((stage) => (
            <div key={stage.stage} className="rounded-xl border border-slate-200 bg-white/75 px-3 py-3 dark:border-slate-800 dark:bg-slate-900/70">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-semibold text-slate-900 dark:text-slate-50">{stage.stage}</div>
                <span className={`text-xs font-semibold uppercase tracking-[0.14em] ${ligandStatusTone(stage.status)}`}>
                  {stage.status}
                </span>
              </div>
              {stage.blocked_reason && (
                <div className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  blocked: {stage.blocked_reason}
                </div>
              )}
              {stage.missing_parameters && stage.missing_parameters.length > 0 && (
                <div className="mt-2 text-xs text-slate-600 dark:text-slate-300">
                  Missing parameters: {stage.missing_parameters.join(', ')}
                </div>
              )}
              {stage.required_tools && stage.required_tools.length > 0 && (
                <div className="mt-2 text-xs text-slate-600 dark:text-slate-300">
                  Required tools: {stage.required_tools.join(', ')}
                </div>
              )}
              {stage.provided_inputs && Object.keys(stage.provided_inputs).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(stage.provided_inputs).map(([key, value]) => (
                    <span key={key} className={`rounded-full px-2 py-1 text-[11px] ${value ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'}`}>
                      {key}: {value ? 'provided' : 'missing'}
                    </span>
                  ))}
                </div>
              )}
              {stage.command_preview && (
                <div className="mt-2 rounded-lg bg-slate-950 px-3 py-2 font-mono text-[11px] leading-5 text-slate-100">
                  {stage.command_preview}
                </div>
              )}
              {stage.next_action && (
                <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{stage.next_action}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function getProtectedPositions(annotationResult: unknown): number[] {
  if (!isAnnotationBundleResult(annotationResult)) return []
  const catalytic = annotationResult.catalytic_sites as { protected_positions?: unknown } | null
  return Array.isArray(catalytic?.protected_positions)
    ? catalytic.protected_positions.filter((item): item is number => typeof item === 'number')
    : []
}

function getCuratedStructureResidues(annotationResult: unknown) {
  if (!isAnnotationBundleResult(annotationResult)) return []

  const catalytic = annotationResult.catalytic_sites as {
    curated_sites?: Array<{
      residues?: Array<{
        pdb_chain?: string | null
        pdb_residue_no?: string | number | null
      }>
    }>
  } | null

  const residues = catalytic?.curated_sites?.flatMap((site) => site.residues || []) || []

  return residues
    .map((residue) => {
      const parsedResidueNo =
        typeof residue.pdb_residue_no === 'number'
          ? residue.pdb_residue_no
          : typeof residue.pdb_residue_no === 'string'
            ? Number.parseInt(residue.pdb_residue_no, 10)
            : Number.NaN

      if (!Number.isFinite(parsedResidueNo)) return null

      return {
        chainId: residue.pdb_chain || null,
        residueNumber: parsedResidueNo,
        color: '#22c55e',
        source: 'curated' as const,
      }
    })
    .filter((item): item is { chainId: string | null; residueNumber: number; color: string; source: 'curated' } => item !== null)
}

function getSignalPeptideRanges(annotationResult: unknown) {
  if (!isAnnotationBundleResult(annotationResult)) return []

  const signal = annotationResult.signal_peptide as {
    has_signal_peptide?: boolean
    regions?: {
      h_region?: { start?: number; end?: number | null }
      c_region?: { start?: number; end?: number | null }
    }
  } | null

  if (!signal?.has_signal_peptide || !signal.regions) return []

  const ranges = [
    signal.regions.h_region ? { ...signal.regions.h_region, color: '#0ea5e9', source: 'signal_h' as const } : null,
    signal.regions.c_region ? { ...signal.regions.c_region, color: '#38bdf8', source: 'signal_c' as const } : null,
  ]

  return ranges
    .filter((item): item is { start?: number; end?: number | null; color: string; source: 'signal_h' | 'signal_c' } => item !== null)
    .filter((item) => typeof item.start === 'number' && typeof item.end === 'number' && item.end >= item.start)
    .map((item) => ({
      start: item.start as number,
      end: item.end as number,
      color: item.color,
      source: item.source,
    }))
}

function getInterproRanges(annotationResult: unknown) {
  if (!isAnnotationBundleResult(annotationResult)) return []

  const interpro = annotationResult.interpro as {
    annotations?: Array<{
      entry_type?: string
      source?: string
      regions?: Array<{ start: number; end: number }>
    }>
  } | null

  const annotations = interpro?.annotations || []

  return annotations
    .filter((item) => item.source === 'interpro' || item.source === 'pfam')
    .filter((item) => item.entry_type === 'domain' || item.entry_type === 'family' || item.entry_type === 'repeat')
    .flatMap((item) =>
      (item.regions || [])
        .filter((region) => typeof region.start === 'number' && typeof region.end === 'number' && region.end >= region.start)
        .map((region) => ({
          start: region.start,
          end: region.end,
          color: item.source === 'pfam' ? '#8b5cf6' : '#f59e0b',
          source: item.source === 'pfam' ? 'pfam' as const : 'interpro' as const,
        }))
    )
}

function buildContiguousStructureRanges(
  mappings: Array<{
    chain_id: string
    pdb_residue_no: number
    uniprot_position: number
  }>,
  range: {
    start: number
    end: number
    color: string
    source: 'signal_h' | 'signal_c' | 'interpro' | 'pfam'
  },
) {
  const rows = mappings.filter(
    (row) => row.uniprot_position >= range.start && row.uniprot_position <= range.end
  )
  if (rows.length === 0) return []

  const rowsByChain = new Map<string, number[]>()
  for (const row of rows) {
    const chainId = row.chain_id || '_'
    const residueNumbers = rowsByChain.get(chainId) || []
    residueNumbers.push(row.pdb_residue_no)
    rowsByChain.set(chainId, residueNumbers)
  }

  const mappedRanges: Array<{
    chainId?: string | null
    startResidue: number
    endResidue: number
    color?: string
    source: 'signal_h' | 'signal_c' | 'interpro' | 'pfam'
  }> = []

  for (const [chainId, residueNumbers] of rowsByChain.entries()) {
    const sortedResidues = Array.from(new Set(residueNumbers)).sort((a, b) => a - b)
    if (sortedResidues.length === 0) continue

    let segmentStart = sortedResidues[0]
    let segmentEnd = sortedResidues[0]

    for (let index = 1; index < sortedResidues.length; index += 1) {
      const residue = sortedResidues[index]
      if (residue === segmentEnd + 1) {
        segmentEnd = residue
        continue
      }

      mappedRanges.push({
        chainId: chainId === '_' ? null : chainId,
        startResidue: segmentStart,
        endResidue: segmentEnd,
        color: range.color,
        source: range.source,
      })
      segmentStart = residue
      segmentEnd = residue
    }

    mappedRanges.push({
      chainId: chainId === '_' ? null : chainId,
      startResidue: segmentStart,
      endResidue: segmentEnd,
      color: range.color,
      source: range.source,
    })
  }

  return mappedRanges
}

export function PDBUploadPage() {
  const navigate = useNavigate()
  const selectedModel = useChatStore((s) => s.selectedModel)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [pdbContent, setPdbContent] = useState<string | null>(null)
  const [mdTaskId, setMdTaskId] = useState<string | null>(null)
  const [mdLastTaskId, setMdLastTaskId] = useState<string | null>(null)
  const [mdStatus, setMdStatus] = useState<string | null>(null)
  const [mdProgress, setMdProgress] = useState<number | null>(null)
  const [mdStageMessage, setMdStageMessage] = useState<string | null>(null)
  const [mdCurrentStep, setMdCurrentStep] = useState<number | null>(null)
  const [mdTotalSteps, setMdTotalSteps] = useState<number | null>(null)
  const [mdCanceling, setMdCanceling] = useState(false)
  const [mdCancelRequestedAt, setMdCancelRequestedAt] = useState<string | null>(null)
  const [mdError, setMdError] = useState<string | null>(null)
  const [mdResult, setMdResult] = useState<unknown | null>(null)
  const [mdProtocols, setMdProtocols] = useState<MdProtocol[]>([])
  const [selectedMdProtocolId, setSelectedMdProtocolId] = useState('smoke_short')
  const [mdProtocolError, setMdProtocolError] = useState<string | null>(null)
  const [mappingLoading, setMappingLoading] = useState(false)
  const [mappingError, setMappingError] = useState<string | null>(null)
  const [mappingResult, setMappingResult] = useState<unknown | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchResult, setSearchResult] = useState<unknown | null>(null)
  const [annotationLoading, setAnnotationLoading] = useState(false)
  const [annotationError, setAnnotationError] = useState<string | null>(null)
  const [annotationResult, setAnnotationResult] = useState<unknown | null>(null)
  const [ligandLoading, setLigandLoading] = useState(false)
  const [ligandError, setLigandError] = useState<string | null>(null)
  const [ligandResult, setLigandResult] = useState<LigandPreprocessResult | null>(null)
  const [lipaseNumberingConfirmed, setLipaseNumberingConfirmed] = useState(false)
  const [lipaseLoading, setLipaseLoading] = useState(false)
  const [lipaseError, setLipaseError] = useState<string | null>(null)
  const [lipaseEvidenceContext, setLipaseEvidenceContext] = useState<LipaseEvidenceContext | null>(null)
  const mdPollTimer = useRef<number | null>(null)
  const pollMdTaskRef = useRef<((taskId: string) => Promise<void>) | null>(null)
  const analysisObjectName = analysis?.object_name ?? null
  const analysisFileName = analysis?.file_name ?? null
  const analysisTitle = analysis?.header?.title ?? null

  const structureHighlights = useMemo(() => {
    const curatedResidues = getCuratedStructureResidues(annotationResult)
    const highlights = new Map<string, { chainId?: string | null; residueNumber: number; color?: string; source: 'curated' | 'inferred' | 'lipase' }>()

    for (const residue of curatedResidues) {
      const key = `${residue.chainId || '_'}:${residue.residueNumber}`
      highlights.set(key, residue)
    }

    if (isStructureMappingResult(mappingResult)) {
      const protectedPositions = new Set(getProtectedPositions(annotationResult))
      for (const row of mappingResult.mappings) {
        if (!protectedPositions.has(row.uniprot_position)) continue
        const key = `${row.chain_id || '_'}:${row.pdb_residue_no}`
        if (highlights.has(key)) continue
        highlights.set(key, {
          chainId: row.chain_id,
          residueNumber: row.pdb_residue_no,
          color: '#ef4444',
          source: 'inferred',
        })
      }
    }

    if (lipaseNumberingConfirmed && lipaseEvidenceContext && isStructureMappingResult(mappingResult) && isReliableStructureMapping(mappingResult)) {
      const evidencePositions = new Set<number>()
      const evidenceRows = [
        ...(lipaseEvidenceContext.exact_mutation_matches || []),
        ...(lipaseEvidenceContext.position_matches || []),
      ]

      for (const row of evidenceRows) {
        const position = typeof row.position === 'number'
          ? row.position
          : typeof row.position === 'string'
            ? Number.parseInt(row.position, 10)
            : Number.NaN
        if (Number.isFinite(position)) evidencePositions.add(position)
      }

      for (const row of mappingResult.mappings) {
        if (!evidencePositions.has(row.uniprot_position)) continue
        const key = `${row.chain_id || '_'}:${row.pdb_residue_no}`
        if (highlights.has(key)) continue
        highlights.set(key, {
          chainId: row.chain_id,
          residueNumber: row.pdb_residue_no,
          color: '#14b8a6',
          source: 'lipase',
        })
      }
    }

    return Array.from(highlights.values())
  }, [annotationResult, lipaseEvidenceContext, lipaseNumberingConfirmed, mappingResult])

  const structureHighlightRanges = useMemo(() => {
    if (!isStructureMappingResult(mappingResult)) return []

    const signalRanges = getSignalPeptideRanges(annotationResult)
    const interproRanges = getInterproRanges(annotationResult)
    const allRanges = [...signalRanges, ...interproRanges]
    if (allRanges.length === 0) return []

    const mappedRanges: Array<{
      chainId?: string | null
      startResidue: number
      endResidue: number
      color?: string
      source: 'signal_h' | 'signal_c' | 'interpro' | 'pfam'
    }> = []

    for (const range of allRanges) {
      mappedRanges.push(...buildContiguousStructureRanges(mappingResult.mappings, range))
    }

    const deduped = new Map<string, typeof mappedRanges[number]>()
    for (const range of mappedRanges) {
      const key = `${range.chainId || '_'}:${range.startResidue}-${range.endResidue}:${range.source}`
      deduped.set(key, range)
    }

    return Array.from(deduped.values())
  }, [annotationResult, mappingResult])

  const structureHighlightSummary = useMemo(() => {
    const protectedCount = getProtectedPositions(annotationResult).length
    const signalRegionCount = structureHighlightRanges.length
    const curatedCount = structureHighlights.filter((item) => item.source === 'curated').length
    const inferredCount = structureHighlights.filter((item) => item.source === 'inferred').length
    const lipaseCount = structureHighlights.filter((item) => item.source === 'lipase').length
    const lipaseEvidencePositionCount = new Set([
      ...((lipaseEvidenceContext?.exact_mutation_matches || []).map((row) => row.position)),
      ...((lipaseEvidenceContext?.position_matches || []).map((row) => row.position)),
    ].map((position) => {
      if (typeof position === 'number') return position
      if (typeof position === 'string') return Number.parseInt(position, 10)
      return Number.NaN
    }).filter((position) => Number.isFinite(position))).size
    const domainRegionCount = structureHighlightRanges.filter((item) => item.source === 'interpro' || item.source === 'pfam').length
    if (protectedCount === 0 && signalRegionCount === 0 && lipaseCount === 0) return null

    return {
      protectedCount,
      mappedCount: curatedCount + inferredCount,
      curatedCount,
      inferredCount,
      lipaseCount,
      lipaseEvidencePositionCount,
      signalRegionCount,
      domainRegionCount,
      mappingSource: isStructureMappingResult(mappingResult) ? mappingResult.source || null : null,
      mappingLimitations: isStructureMappingResult(mappingResult) ? mappingResult.limitations?.length || 0 : 0,
      chainId: structureHighlights[0]?.chainId || structureHighlightRanges[0]?.chainId || analysis?.chains[0]?.chain_id || null,
    }
  }, [analysis?.chains, annotationResult, lipaseEvidenceContext, mappingResult, structureHighlightRanges, structureHighlights])

  const clearMdPollTimer = useCallback(() => {
    if (mdPollTimer.current !== null) {
      window.clearTimeout(mdPollTimer.current)
      mdPollTimer.current = null
    }
  }, [])

  const uploadAndAnalyze = useCallback(async (f: File) => {
    clearMdPollTimer()
    setFile(f)
    setUploading(true)
    setError(null)
    setAnalysis(null)
    setPdbContent(null)
    setMdTaskId(null)
    setMdLastTaskId(null)
    setMdStatus(null)
    setMdCanceling(false)
    setMdCancelRequestedAt(null)
    setMdError(null)
    setMdResult(null)
    setMappingLoading(false)
    setMappingError(null)
    setMappingResult(null)
    setSearchLoading(false)
    setSearchError(null)
    setSearchResult(null)
    setAnnotationLoading(false)
    setAnnotationError(null)
    setAnnotationResult(null)
    setLigandLoading(false)
    setLigandError(null)
    setLigandResult(null)
    setLipaseNumberingConfirmed(false)
    setLipaseLoading(false)
    setLipaseError(null)
    setLipaseEvidenceContext(null)

    const formData = new FormData()
    formData.append('file', f)

    try {
      const uploadResult = await uploadFormWithProgress<{ id: string; object_name?: string; download_url: string }>(
        '/files/upload',
        formData,
        {
          onProgress: (progress) => setUploadProgress(progress),
        },
      )

      setUploadProgress(100)

      // Analyze
      const resp = await authFetch('/api/pdb/analyze-by-name', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          object_name: uploadResult.id || uploadResult.object_name,
          model: selectedModel,
        }),
      })

      if (!resp.ok) throw new Error('Analysis failed')

      const data = await resp.json()
      const objectName = uploadResult.id || uploadResult.object_name
      const downloadUrl = normalizeFileDownloadUrl(uploadResult.download_url, objectName)
      setAnalysis({ ...data, object_name: objectName, download_url: downloadUrl, file_name: f.name, file_size: f.size })

      // Fetch PDB content for 3D viewer
      try {
        const pdbResp = await authFetch(downloadUrl)
        if (pdbResp.ok) setPdbContent(await pdbResp.text())
      } catch { /* non-critical */ }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [clearMdPollTimer, selectedModel])

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) uploadAndAnalyze(accepted[0])
  }, [uploadAndAnalyze])

  useEffect(() => {
    return () => {
      clearMdPollTimer()
    }
  }, [clearMdPollTimer])

  useEffect(() => {
    let canceled = false
    api.getMdProtocols()
      .then((payload) => {
        if (canceled) return
        setMdProtocols(payload.protocols || [])
        setSelectedMdProtocolId(payload.default_protocol_id || payload.protocols?.[0]?.id || 'smoke_short')
        setMdProtocolError(null)
      })
      .catch((e) => {
        if (canceled) return
        setMdProtocolError(e instanceof Error ? e.message : 'Failed to load MD protocols')
      })
    return () => {
      canceled = true
    }
  }, [])

  const pollMdTask = useCallback(async (taskId: string) => {
    try {
      const status = await api.getToolTask(taskId)
      const normalizedStatus = (status.status || '').toLowerCase()
      const cancelRequested = Boolean(status.cancel_requested)
      setMdLastTaskId(taskId)
      setMdStatus(status.status)
      setMdProgress(clampProgress(status.progress ?? null))
      setMdStageMessage(status.message ?? null)
      setMdCurrentStep(typeof status.current_step === 'number' ? status.current_step : null)
      setMdTotalSteps(typeof status.total_steps === 'number' ? status.total_steps : null)
      setMdCancelRequestedAt(status.cancel_requested_at ?? null)

      if (cancelRequested && !['completed', 'success', 'failed', 'failure', 'canceled', 'revoked'].includes(normalizedStatus)) {
        setMdStatus('cancel_requested')
        mdPollTimer.current = window.setTimeout(() => {
          void pollMdTaskRef.current?.(taskId)
        }, 3000)
        return
      }

      if (status.status === 'canceled' || status.status === 'revoked') {
        clearMdPollTimer()
        setMdStatus('canceled')
        setMdProgress(100)
        setMdError(status.error || null)
        setMdTaskId(null)
        setMdCanceling(false)
        return
      }

      if (status.status === 'success' || status.status === 'completed') {
        clearMdPollTimer()
        const payload = status.result?.result ?? status.result
        setMdResult(payload ?? null)
        setMdProgress(100)
        setMdStageMessage(status.message ?? 'MD workflow completed')
        setMdError(null)
        setMdTaskId(null)
        setMdCanceling(false)
        return
      }

      if (status.status === 'failure' || status.status === 'failed') {
        clearMdPollTimer()
        setMdProgress(100)
        setMdError(status.error || status.result?.error || 'MD task failed')
        setMdTaskId(null)
        setMdCanceling(false)
        return
      }

      mdPollTimer.current = window.setTimeout(() => {
        void pollMdTaskRef.current?.(taskId)
      }, 3000)
    } catch (e) {
      clearMdPollTimer()
      setMdError(e instanceof Error ? e.message : 'Failed to poll MD task')
      setMdTaskId(null)
      setMdCanceling(false)
    }
  }, [clearMdPollTimer])

  useEffect(() => {
    pollMdTaskRef.current = pollMdTask
  }, [pollMdTask])

  const startMdValidation = useCallback(async () => {
    if (!analysisObjectName) {
      setMdError('No uploaded structure object found')
      return
    }

    clearMdPollTimer()
    setMdError(null)
    setMdResult(null)
    setMdCanceling(false)
    setMdCancelRequestedAt(null)
    setMdProgress(0)
    setMdStageMessage('Submitting MD task')
    setMdCurrentStep(null)
    setMdTotalSteps(null)
    setMdStatus('submitting')

    try {
      const resolvedProtocol = await api.resolveMdProtocol(selectedMdProtocolId)
      const submitted = await api.submitTool('gromacs_md', {
        ...resolvedProtocol.parameters,
        protocol_id: resolvedProtocol.protocol_id,
        pdb_object_name: analysisObjectName,
        upload_artifacts: true,
      })
      setMdTaskId(submitted.task_id)
      setMdLastTaskId(submitted.task_id)
      setMdProgress(0)
      setMdStageMessage('Task submitted; waiting for worker')
      setMdStatus('queued')
      void pollMdTask(submitted.task_id)
    } catch (e) {
      setMdError(e instanceof Error ? e.message : 'Failed to submit MD task')
      setMdStatus('failed')
    }
  }, [analysisObjectName, clearMdPollTimer, pollMdTask, selectedMdProtocolId])

  const cancelMdValidation = useCallback(async () => {
    if (!mdTaskId) return

    setMdCanceling(true)
    setMdError(null)

    try {
      const canceled = await api.cancelToolTask(mdTaskId)
      setMdCancelRequestedAt(canceled.cancel_requested_at ?? null)
      setMdStatus(canceled.status || 'cancel_requested')
      void pollMdTask(mdTaskId)
    } catch (e) {
      setMdError(e instanceof Error ? e.message : 'Failed to cancel MD task')
    } finally {
      setMdCanceling(false)
    }
  }, [mdTaskId, pollMdTask])

  const displayedMdTaskId = mdTaskId || mdLastTaskId
  const mdStepLabel = formatMdStep(mdCurrentStep, mdTotalSteps)
  const mdActionBusy = !!mdTaskId || mdStatus === 'submitting'
  const mdActionStatus = mdTaskId
    ? typeof mdProgress === 'number'
      ? `${mdProgress}% running`
      : 'Live task'
    : mdStatus === 'submitting'
      ? 'Submitting'
      : 'GROMACS'
  const selectedMdProtocol = mdProtocols.find((protocol) => protocol.id === selectedMdProtocolId) || null

  const runResidueMapping = useCallback(async () => {
    if (!analysis?.object_name) {
      setMappingError('No uploaded structure object found')
      return
    }

    setMappingLoading(true)
    setMappingError(null)
    setMappingResult(null)

    try {
      const primaryChain = analysis.chains[0]?.chain_id || ''
      const response = await api.getPdbResidueMappingByName(analysis.object_name, primaryChain, undefined, 1)
      setMappingResult(response)
    } catch (e) {
      setMappingError(e instanceof Error ? e.message : 'Failed to build residue mapping')
    } finally {
      setMappingLoading(false)
    }
  }, [analysis])

  const runStructureSearch = useCallback(async () => {
    if (!analysis?.object_name) {
      setSearchError('No uploaded structure object found')
      return
    }

    setSearchLoading(true)
    setSearchError(null)
    setSearchResult(null)

    try {
      const response = await api.getPdbStructureSearchByName(analysis.object_name, 'pdb', 5)
      setSearchResult(response)
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : 'Failed to run structure search')
    } finally {
      setSearchLoading(false)
    }
  }, [analysis])

  const runAnnotationBundle = useCallback(async () => {
    const primarySequence = analysis?.chains[0]?.sequence || ''
    if (!primarySequence) {
      setAnnotationError('No chain sequence found in the current structure analysis')
      return
    }

    setAnnotationLoading(true)
    setAnnotationError(null)
    setAnnotationResult(null)

    try {
      const response = await api.callTool('annotation_bundle', {
        sequence: primarySequence,
      })
      setAnnotationResult(response.result ?? response)
    } catch (e) {
      setAnnotationError(e instanceof Error ? e.message : 'Failed to resolve annotation bundle')
    } finally {
      setAnnotationLoading(false)
    }
  }, [analysis])

  const runLigandPreflight = useCallback(async () => {
    if (!analysisObjectName) {
      setLigandError('Upload a ligand SDF file before running ligand preflight')
      return
    }
    const fileName = String(analysisFileName || analysisObjectName).toLowerCase()
    if (!fileName.endsWith('.sdf')) {
      setLigandError('Ligand preflight requires an uploaded SDF ligand file; the current structure upload is not used as ligand input')
      return
    }
    setLigandLoading(true)
    setLigandError(null)
    setLigandResult(null)

    try {
      const submitted = await api.submitTool('ligand_preprocess', {
        sdf_object_name: analysisObjectName,
        stages: ['preflight', 'prepare_pdbqt', 'vina_docking', 'ligand_topology'],
        store_outputs: false,
        ph: 7.4,
        protonation_policy: 'physiological_pH_manual_review',
        charge_model: 'gasteiger',
      })
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const status = await api.getToolTask(submitted.task_id)
        if (status.status === 'success' || status.status === 'completed') {
          const payload = status.result?.result ?? status.result
          if (payload && typeof payload === 'object') setLigandResult(payload as LigandPreprocessResult)
          return
        }
        if (status.status === 'failure' || status.status === 'failed') {
          setLigandError(status.error || 'Ligand preflight task failed')
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
      }
      setLigandError('Ligand preflight task is still running; check task audit for final status')
    } catch (e) {
      setLigandError(e instanceof Error ? e.message : 'Failed to run ligand preflight')
    } finally {
      setLigandLoading(false)
    }
  }, [analysisFileName, analysisObjectName])

  const runLipaseEvidenceOverlay = useCallback(async () => {
    if (!isStructureMappingResult(mappingResult)) {
      setLipaseError('Run residue mapping before applying lipase evidence overlay')
      return
    }
    if (!lipaseNumberingConfirmed) {
      setLipaseError('Confirm the numbering relationship before applying lipase evidence overlay')
      return
    }
    if (!isReliableStructureMapping(mappingResult)) {
      setLipaseError('Lipase overlay requires curated/local residue mapping without inferred coordinate-order fallback')
      return
    }

    const positions = Array.from(new Set(mappingResult.mappings.map((row) => row.uniprot_position)))
      .filter((position) => Number.isFinite(position))
      .sort((a, b) => a - b)
    if (positions.length === 0) {
      setLipaseError('Residue mapping returned no positions to query')
      return
    }

    setLipaseLoading(true)
    setLipaseError(null)

    try {
      const chunks: number[][] = []
      for (let index = 0; index < positions.length; index += 75) {
        chunks.push(positions.slice(index, index + 75))
      }
      const responses: LipaseEvidenceContext[] = []
      for (const [index, chunk] of chunks.entries()) {
        responses.push(await api.getLipaseEvidenceContext({
          positions: chunk,
          q: index === 0 ? analysisTitle || analysisFileName || 'lipase' : undefined,
          limit: 100,
        }))
      }

      const [first, ...rest] = responses
      const exactMatches = responses.flatMap((item) => item.exact_mutation_matches || [])
      const positionMatches = responses.flatMap((item) => item.position_matches || [])
      const strongest = strongestEvidenceLevel(responses.map((item) => item.strongest_evidence_level))

      setLipaseEvidenceContext({
        ...first,
        requested_positions: positions,
        exact_mutation_matches: exactMatches,
        position_matches: positionMatches,
        counts: {
          exact_mutation_matches: exactMatches.length,
          position_matches: positionMatches.length,
          search_matches: first.counts.search_matches,
        },
        strongest_evidence_level: strongest,
        search: first.search || rest.find((item) => item.search)?.search || null,
      })
    } catch (e) {
      setLipaseError(e instanceof Error ? e.message : 'Failed to load lipase evidence context')
    } finally {
      setLipaseLoading(false)
    }
  }, [analysisFileName, analysisTitle, lipaseNumberingConfirmed, mappingResult])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'chemical/x-pdb': ['.pdb', '.ent'], 'chemical/x-cif': ['.cif'] },
    maxFiles: 1,
  })

  const handleQuickAction = (actionKey: string) => {
    switch (actionKey) {
      case 'chat':
        navigate('/chat/agent', {
          state: {
            initialPrompt: `分析这个PDB结构 ${analysisFileName || ''}，帮我分析其结构特征、稳定性、潜在的突变改造方案`,
            uploadFile: file,
          },
        })
        break
      case 'md':
        void startMdValidation()
        break
      case 'mapping':
        void runResidueMapping()
        break
      case 'search':
        void runStructureSearch()
        break
      case 'annotation':
        void runAnnotationBundle()
        break
      case 'ligand':
        void runLigandPreflight()
        break
      case 'lipase':
        void runLipaseEvidenceOverlay()
        break
    }
  }

  const quickActions = [
    {
      key: 'chat',
      title: 'Deep Analysis in Chat',
      subtitle: 'Open this structure in the agent workspace for deeper reasoning and mutation planning.',
      badge: 'Primary',
      primary: true,
      disabled: false,
      loading: false,
      className: 'border-blue-200/80 bg-[linear-gradient(135deg,rgba(37,99,235,0.96),rgba(29,78,216,0.9))] text-white shadow-[0_24px_60px_-30px_rgba(37,99,235,0.9)] hover:-translate-y-0.5 hover:shadow-[0_28px_70px_-30px_rgba(37,99,235,0.95)]',
      badgeClassName: 'bg-white/16 text-blue-50 ring-1 ring-white/15',
      iconClassName: 'bg-white/14 text-white ring-1 ring-white/18',
      titleClassName: 'text-white',
      subtitleClassName: 'text-blue-50/88',
    },
    {
      key: 'md',
      title: mdActionBusy ? 'MD Running' : 'MD Validation',
      subtitle: mdActionBusy ? 'Track the live GROMACS workflow and monitor progress from the worker queue.' : 'Run a molecular dynamics validation workflow on the current structure.',
      badge: mdActionStatus,
      primary: false,
      disabled: mdActionBusy,
      loading: mdActionBusy,
      className: 'border-sky-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,249,255,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(14,165,233,0.75)] hover:-translate-y-0.5 hover:border-sky-300 hover:shadow-[0_26px_50px_-34px_rgba(14,165,233,0.8)] dark:border-sky-900/60 dark:bg-[linear-gradient(180deg,rgba(8,47,73,0.45),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-sky-100 text-sky-700 ring-1 ring-sky-200 dark:bg-sky-950/70 dark:text-sky-200 dark:ring-sky-900/80',
      iconClassName: 'bg-sky-100 text-sky-700 ring-1 ring-sky-200 dark:bg-sky-950/70 dark:text-sky-200 dark:ring-sky-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
    {
      key: 'mapping',
      title: mappingLoading ? 'Mapping' : 'Residue Mapping',
      subtitle: 'Align chain residues to UniProt positions so structure and sequence annotations stay in sync.',
      badge: mappingLoading ? 'Working' : 'SIFTS-ready',
      primary: false,
      disabled: mappingLoading,
      loading: mappingLoading,
      className: 'border-emerald-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(236,253,245,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(16,185,129,0.72)] hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-[0_26px_50px_-34px_rgba(16,185,129,0.8)] dark:border-emerald-900/60 dark:bg-[linear-gradient(180deg,rgba(6,78,59,0.4),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-950/70 dark:text-emerald-200 dark:ring-emerald-900/80',
      iconClassName: 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-950/70 dark:text-emerald-200 dark:ring-emerald-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
    {
      key: 'search',
      title: searchLoading ? 'Searching' : 'Structure Search',
      subtitle: 'Compare the uploaded fold against nearby structures and inspect similar hits fast.',
      badge: searchLoading ? 'Working' : 'Foldseek-ready',
      primary: false,
      disabled: searchLoading,
      loading: searchLoading,
      className: 'border-amber-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,251,235,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(245,158,11,0.72)] hover:-translate-y-0.5 hover:border-amber-300 hover:shadow-[0_26px_50px_-34px_rgba(245,158,11,0.82)] dark:border-amber-900/60 dark:bg-[linear-gradient(180deg,rgba(120,53,15,0.38),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-amber-100 text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:ring-amber-900/80',
      iconClassName: 'bg-amber-100 text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:ring-amber-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
    {
      key: 'annotation',
      title: annotationLoading ? 'Annotating' : 'Annotation Bundle',
      subtitle: 'Collect catalytic sites, domains, signal peptides, and related evidence in one pass.',
      badge: annotationLoading ? 'Working' : 'Bundle',
      primary: false,
      disabled: annotationLoading,
      loading: annotationLoading,
      className: 'border-rose-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,241,242,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(244,63,94,0.7)] hover:-translate-y-0.5 hover:border-rose-300 hover:shadow-[0_26px_50px_-34px_rgba(244,63,94,0.82)] dark:border-rose-900/60 dark:bg-[linear-gradient(180deg,rgba(136,19,55,0.35),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-rose-100 text-rose-700 ring-1 ring-rose-200 dark:bg-rose-950/70 dark:text-rose-200 dark:ring-rose-900/80',
      iconClassName: 'bg-rose-100 text-rose-700 ring-1 ring-rose-200 dark:bg-rose-950/70 dark:text-rose-200 dark:ring-rose-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
    {
      key: 'ligand',
      title: ligandLoading ? 'Checking Ligand' : 'Ligand Preflight',
      subtitle: 'Check the 2D SDF substrate before docking or complex MD. Reports missing OpenBabel, Vina, and topology tools.',
      badge: ligandLoading ? 'Working' : (ligandResult?.status || '2D SDF'),
      primary: false,
      disabled: ligandLoading,
      loading: ligandLoading,
      className: 'border-cyan-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(236,254,255,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(6,182,212,0.72)] hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-[0_26px_50px_-34px_rgba(6,182,212,0.82)] dark:border-cyan-900/60 dark:bg-[linear-gradient(180deg,rgba(22,78,99,0.38),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-cyan-100 text-cyan-700 ring-1 ring-cyan-200 dark:bg-cyan-950/70 dark:text-cyan-200 dark:ring-cyan-900/80',
      iconClassName: 'bg-cyan-100 text-cyan-700 ring-1 ring-cyan-200 dark:bg-cyan-950/70 dark:text-cyan-200 dark:ring-cyan-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
    {
      key: 'lipase',
      title: lipaseLoading ? 'Loading Evidence' : 'Lipase Overlay',
      subtitle: isReliableStructureMapping(mappingResult)
        ? 'Map KWB lipase evidence positions through curated/local residue mapping.'
        : isStructureMappingResult(mappingResult)
          ? 'Lipase overlay is blocked for inferred coordinate-order mappings.'
        : 'Run residue mapping first, then confirm numbering before applying lipase evidence.',
      badge: lipaseLoading ? 'Working' : (lipaseEvidenceContext ? `exact ${lipaseEvidenceContext.counts.exact_mutation_matches}` : 'KWB DB'),
      primary: false,
      disabled: lipaseLoading || !isReliableStructureMapping(mappingResult) || !lipaseNumberingConfirmed,
      loading: lipaseLoading,
      className: 'border-teal-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,253,250,0.98))] text-slate-900 shadow-[0_20px_45px_-36px_rgba(20,184,166,0.72)] hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-[0_26px_50px_-34px_rgba(20,184,166,0.82)] dark:border-teal-900/60 dark:bg-[linear-gradient(180deg,rgba(19,78,74,0.38),rgba(15,23,42,0.95))] dark:text-slate-50',
      badgeClassName: 'bg-teal-100 text-teal-700 ring-1 ring-teal-200 dark:bg-teal-950/70 dark:text-teal-200 dark:ring-teal-900/80',
      iconClassName: 'bg-teal-100 text-teal-700 ring-1 ring-teal-200 dark:bg-teal-950/70 dark:text-teal-200 dark:ring-teal-900/80',
      titleClassName: 'text-slate-900 dark:text-slate-50',
      subtitleClassName: 'text-slate-600 dark:text-slate-300/90',
    },
  ]

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => navigate('/chat/agent')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Chat
          </button>
          <div className="flex-1" />
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Dna className="w-6 h-6 text-blue-500" />
            PDB Structure Analysis
          </h1>
        </div>

        {/* Drop zone */}
        {!analysis && (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all ${
              isDragActive
                ? 'border-primary bg-primary/5 scale-[1.01]'
                : 'border-border hover:border-muted-foreground/30 hover:bg-secondary/30'
            }`}
          >
            <input {...getInputProps()} />
            {uploading ? (
              <div className="space-y-4">
                <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary" />
                <div>
                  <p className="text-sm font-medium">{file?.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">Uploading & analyzing...</p>
                </div>
                <div className="w-64 mx-auto bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : (
              <>
                <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-base font-medium mb-2">
                  Drop a PDB or CIF file here
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse — .pdb .ent .cif
                </p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 flex items-center gap-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Analysis Result */}
        {analysis && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle className="w-4 h-4" />
                Analysis complete
              </div>
              <button
                onClick={() => {
                  clearMdPollTimer()
                  setFile(null)
                  setAnalysis(null)
                  setPdbContent(null)
                  setError(null)
                  setMdTaskId(null)
                  setMdLastTaskId(null)
                  setMdStatus(null)
                  setMdCanceling(false)
                  setMdCancelRequestedAt(null)
                  setMdError(null)
                  setMdResult(null)
                  setMappingLoading(false)
                  setMappingError(null)
                  setMappingResult(null)
                  setSearchLoading(false)
                  setSearchError(null)
                  setSearchResult(null)
                  setAnnotationLoading(false)
                  setAnnotationError(null)
                  setAnnotationResult(null)
                  setLigandLoading(false)
                  setLigandError(null)
                  setLigandResult(null)
                  setLipaseNumberingConfirmed(false)
                  setLipaseLoading(false)
                  setLipaseError(null)
                  setLipaseEvidenceContext(null)
                }}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Analyze another
              </button>
            </div>

            <PDBAnalysisCard
              data={{ ...analysis, lipaseEvidenceContext: lipaseEvidenceContext || analysis.lipaseEvidenceContext || undefined }}
              pdbContent={pdbContent ?? undefined}
              highlightResidues={structureHighlights}
              highlightRanges={structureHighlightRanges}
              highlightSummary={structureHighlightSummary}
            />

            {/* Quick actions */}
            <div className="overflow-hidden rounded-[28px] border border-border/70 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.08),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] p-4 shadow-[0_24px_80px_-60px_rgba(15,23,42,0.45)] dark:bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.16),transparent_30%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] sm:p-5">
              <div className="flex flex-col gap-2 border-b border-border/60 pb-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                    Structure Workflows
                  </div>
                  <h2 className="mt-2 text-xl font-semibold tracking-tight text-foreground">
                    Pick the next action for this structure
                  </h2>
                </div>
                <div className="flex flex-col gap-2 sm:min-w-[280px]">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    MD Protocol
                  </label>
                  <select
                    value={selectedMdProtocolId}
                    onChange={(event) => setSelectedMdProtocolId(event.target.value)}
                    disabled={mdActionBusy || mdProtocols.length === 0}
                    className="rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {mdProtocols.length === 0 ? (
                      <option value={selectedMdProtocolId}>Loading protocols...</option>
                    ) : mdProtocols.map((protocol) => (
                      <option key={protocol.id} value={protocol.id}>{protocol.label}</option>
                    ))}
                  </select>
                  {selectedMdProtocol && (
                    <div className="space-y-1 text-xs leading-5 text-muted-foreground">
                      <div>
                        {selectedMdProtocol.parameters.simulation_time_ns} ns · {selectedMdProtocol.parameters.ensemble} · {selectedMdProtocol.parameters.force_field}
                      </div>
                      <div>
                        {selectedMdProtocol.risk_level}
                        {selectedMdProtocol.scientific_controls?.replicate_policy?.minimum_for_ranking
                          ? ` · ranking requires ${selectedMdProtocol.scientific_controls.replicate_policy.minimum_for_ranking} replicates`
                          : ''}
                      </div>
                    </div>
                  )}
                  {mdProtocolError && <div className="text-xs text-red-500">{mdProtocolError}</div>}
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {quickActions.map((action) => (
                  <button
                    key={action.key}
                    onClick={() => handleQuickAction(action.key)}
                    disabled={action.disabled}
                    className={[
                      'group relative overflow-hidden rounded-[24px] border p-5 text-left transition-all duration-200',
                      'focus:outline-none focus:ring-2 focus:ring-primary/30',
                      'disabled:cursor-not-allowed disabled:opacity-65 disabled:hover:translate-y-0 disabled:hover:shadow-none',
                      action.primary ? 'min-h-[180px] md:col-span-2' : 'min-h-[170px]',
                      action.className,
                    ].join(' ')}
                  >
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.18),transparent_34%)] opacity-90" />
                    <div className="relative flex h-full flex-col">
                      <div className="flex items-start justify-between gap-3">
                        <div className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${action.iconClassName}`}>
                          {action.loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <ArrowRight className="h-5 w-5" />}
                        </div>
                        <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${action.badgeClassName}`}>
                          {action.badge}
                        </span>
                      </div>

                      <div className="mt-auto pt-8">
                        <div className={`text-xl font-semibold tracking-tight ${action.titleClassName}`}>
                          {action.title}
                        </div>
                        <p className={`mt-2 max-w-[34rem] text-sm leading-6 ${action.subtitleClassName}`}>
                          {action.subtitle}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-4 rounded-2xl border border-teal-200/80 bg-white/75 px-4 py-3 text-sm dark:border-teal-900/60 dark:bg-slate-950/40">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={lipaseNumberingConfirmed}
                    onChange={(event) => {
                      setLipaseNumberingConfirmed(event.target.checked)
                      setLipaseError(null)
                      if (!event.target.checked) setLipaseEvidenceContext(null)
                    }}
                    className="mt-1 h-4 w-4 rounded border-teal-300 text-teal-600 focus:ring-teal-500"
                    disabled={!isStructureMappingResult(mappingResult)}
                  />
                  <span>
                    <span className="block font-medium text-slate-900 dark:text-slate-50">
                      KWB lipase numbering confirmed
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500 dark:text-slate-400">
                      Enables lipase evidence overlay only after residue mapping is available and the sequence numbering relationship has been checked.
                    </span>
                  </span>
                </label>
                {lipaseError ? (
                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                    {lipaseError}
                  </div>
                ) : null}
              </div>

              {mdTaskId && (
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={() => { void cancelMdValidation() }}
                    className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-white/80 px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300 dark:hover:bg-red-950/40"
                    disabled={mdCanceling}
                  >
                    {mdCanceling ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertCircle className="w-4 h-4" />}
                    {mdCanceling ? 'Canceling...' : 'Cancel MD Run'}
                  </button>
                </div>
              )}
            </div>

            {(mdStatus || mdError || displayedMdTaskId) && (
              <div className="rounded-xl border border-border bg-card p-4 text-sm">
                <div className="font-medium text-foreground">MD Task Status</div>
                <div className="mt-2 text-muted-foreground">
                  {displayedMdTaskId ? `${mdTaskId ? 'Active task' : 'Last task'} ${displayedMdTaskId}` : 'No task submitted'}
                </div>
                {mdStatus && (
                  <div className={`mt-2 font-medium ${mdStatusTone(mdStatus)}`}>
                    {formatMdStatus(mdStatus)}
                  </div>
                )}
                {mdStageMessage && (
                  <div className="mt-2 text-sm text-foreground">
                    {mdStageMessage}
                    {mdStepLabel ? <span className="ml-2 text-muted-foreground">Step {mdStepLabel}</span> : null}
                  </div>
                )}
                {typeof mdProgress === 'number' && (
                  <div className="mt-3">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Worker progress</span>
                      <span>{mdProgress}%</span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all duration-500"
                        style={{ width: `${mdProgress}%` }}
                      />
                    </div>
                  </div>
                )}
                {mdTaskId && !mdCancelRequestedAt && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    Polling worker status every 3 seconds.
                  </div>
                )}
                {mdCancelRequestedAt && (
                  <div className="mt-2 text-amber-600 dark:text-amber-300">
                    Cancel requested at {new Date(mdCancelRequestedAt).toLocaleString()}. Waiting for worker terminal state.
                  </div>
                )}
                {mdError && <div className="mt-2 text-red-500">{mdError}</div>}
              </div>
            )}

            {isMDResult(mdResult) && (
              <MDResultView data={mdResult} taskId={mdLastTaskId} />
            )}

            <LigandPreflightCard result={ligandResult} error={ligandError} />

            {mappingError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                {mappingError}
              </div>
            )}

            {isStructureMappingResult(mappingResult) && (
              <StructureMappingCard data={mappingResult} />
            )}

            {searchError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                {searchError}
              </div>
            )}

            {isStructureSearchResult(searchResult) && (
              <StructureSearchResultCard data={searchResult} />
            )}

            {annotationError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                {annotationError}
              </div>
            )}

            {isAnnotationBundleResult(annotationResult) && (
              <AnnotationBundleCard data={annotationResult} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
