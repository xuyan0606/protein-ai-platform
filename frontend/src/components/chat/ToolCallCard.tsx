import { useState, useMemo, useEffect } from 'react'
import type { ReactElement } from 'react'
import type { ToolCall } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'
import { api } from '@/lib/api'
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
  conversationId?: string | null
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
    return JSON.parse(preview)
  } catch {
    try { return JSON.parse(preview.replace(/'/g, '"')) } catch { return null }
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
  'ligand_contact_analysis',
  'structure_pocket_interface_analysis',
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

function isGeometryEvidenceResult(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return record.geometry_only === true && typeof record.evidence_level === 'string'
}

function GeometryEvidenceCard({ data, kind }: { data: Record<string, unknown>; kind: 'ligand' | 'pocket' }) {
  const isLigand = kind === 'ligand'
  const contacts = Array.isArray(data.contacts) ? data.contacts as Array<Record<string, unknown>> : []
  const pocket = data.pocket && typeof data.pocket === 'object' ? data.pocket as Record<string, unknown> : {}
  const pocketResidues = Array.isArray(pocket.residues) ? pocket.residues as Array<Record<string, unknown>> : []
  const interfaces = Array.isArray(data.chain_interfaces) ? data.chain_interfaces as Array<Record<string, unknown>> : []
  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-2">
        <div><p className="text-[10px] uppercase text-muted-foreground">状态</p><p className="font-medium">{String(data.status || 'unknown')}</p></div>
        <div><p className="text-[10px] uppercase text-muted-foreground">证据等级</p><p className="font-medium">{String(data.evidence_level || 'GEOMETRY_ONLY')}</p></div>
      </div>
      {isLigand ? (
        <>
          <p className="text-muted-foreground">接触残基 {contacts.length} 个；距离阈值 {String((data.thresholds as Record<string, unknown> | undefined)?.contact_distance_angstrom || '-')} Å。</p>
          {contacts.length > 0 && <div className="overflow-x-auto"><table className="w-full border-collapse text-left"><thead><tr className="border-b border-border"><th className="py-1 pr-3 font-medium">残基</th><th className="py-1 pr-3 font-medium">配体</th><th className="py-1 pr-3 font-medium">距离 Å</th></tr></thead><tbody>{contacts.slice(0, 10).map((row, index) => <tr key={index} className="border-b border-border/50"><td className="py-1 pr-3 font-mono">{String(row.chain_id || '?')}:{String(row.residue_name || '?')}{String(row.residue_number || '?')}</td><td className="py-1 pr-3">{String(row.instance_id || row.component_id || '-')}</td><td className="py-1 pr-3 font-mono">{String(row.distance_angstrom ?? '-')}</td></tr>)}</tbody></table></div>}
        </>
      ) : (
        <>
          <p className="text-muted-foreground">口袋残基 {pocketResidues.length} 个；链界面 {interfaces.length} 个；通道结果仅为几何线索。</p>
          {pocketResidues.length > 0 && <p>口袋预览：{pocketResidues.slice(0, 10).map((row) => `${String(row.chain_id || '?')}:${String(row.residue_name || '?')}${String(row.residue_number || '?')}`).join('；')}</p>}
        </>
      )}
      <p className="text-amber-600">{String(data.interpretation_boundary || '仅表示坐标几何邻近关系，不能证明结合能、催化机制或实验收益。')}</p>
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
  ligand_contact_analysis: (data: unknown) => isGeometryEvidenceResult(data) ? <GeometryEvidenceCard data={data} kind="ligand" /> : null,
  structure_pocket_interface_analysis: (data: unknown) => isGeometryEvidenceResult(data) ? <GeometryEvidenceCard data={data} kind="pocket" /> : null,
} satisfies Record<string, (data: unknown) => ReactElement | null>

export function ToolCallCard({ toolCall, conversationId }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [taskState, setTaskState] = useState<{ status: string; result?: unknown; error?: string | null; message?: string | null; rid?: string | null; canResume?: boolean } | null>(null)
  const [pollGeneration, setPollGeneration] = useState(0)
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [revisionCreated, setRevisionCreated] = useState(false)
  const taskId = useMemo(() => {
    if (toolCall.status !== 'submitted') return null
    const value = tryParseResult(toolCall.rawResult) || tryParseResult(toolCall.resultPreview)
    if (!value || typeof value !== 'object') return null
    const id = (value as Record<string, unknown>).task_id
    return typeof id === 'string' && id ? id : null
  }, [toolCall.status, toolCall.rawResult, toolCall.resultPreview])
  useEffect(() => {
    if (!taskId) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let pollAttempt = 0
    let errorAttempt = 0
    const poll = async () => {
      try {
        const response = await api.getToolTask(taskId)
        if (!active) return
        pollAttempt += 1
        errorAttempt = 0
        setTaskState({ status: response.status, result: response.result, error: response.error,
          message: response.message, rid: response.rid, canResume: response.can_resume })
        if (!['completed', 'failed', 'canceled', 'degraded'].includes(response.status)) {
          // Keep early progress responsive, then back off for long-running tasks.
          const delay = Math.min(30000, 5000 * 2 ** Math.min(pollAttempt - 1, 3))
          timer = setTimeout(() => void poll(), delay)
        }
      } catch (error) {
        if (active) {
          errorAttempt += 1
          setTaskState({ status: 'poll_error', message: '暂时无法连接，正在重试。后台任务将继续处理。', error: error instanceof Error ? error.message : 'Unable to load task status' })
          const delay = Math.min(60000, 15000 * 2 ** Math.min(errorAttempt - 1, 2))
          timer = setTimeout(() => void poll(), delay)
        }
      }
    }
    void poll()
    return () => { active = false; if (timer) clearTimeout(timer) }
  }, [taskId, pollGeneration])
  const updateReport = async () => {
    if (!taskId || !conversationId || actionBusy) return
    setActionBusy(true); setActionError(null)
    try {
      await api.createBlastReportRevision(taskId, Number(conversationId))
      setRevisionCreated(true)
      if (useChatStore.getState().currentId === conversationId && !useChatStore.getState().streaming) {
        await useChatStore.getState().setCurrentId(conversationId)
      }
    } catch (error) { setActionError(error instanceof Error ? error.message : '报告更新失败，请重试') }
    finally { setActionBusy(false) }
  }
  const resume = async () => {
    if (!taskId || actionBusy) return
    setActionBusy(true); setActionError(null)
    try {
      await api.resumeBlastTask(taskId)
      setTaskState({ status: 'waiting', message: '已恢复原 NCBI 任务查询。' })
      setPollGeneration((value) => value + 1)
    } catch (error) { setActionError(error instanceof Error ? error.message : '恢复查询失败') }
    finally { setActionBusy(false) }
  }
  const displayedStatus = taskState?.status || toolCall.status
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
    if (taskState?.status === 'completed' || taskState?.status === 'degraded') {
      const result = taskState.result
      if (result && typeof result === 'object') {
        const record = result as Record<string, unknown>
        return record.tool === toolCall.name && record.result ? record.result : result
      }
    }
    if (toolCall.status !== 'completed') return null
    if (toolCall.name === 'build_site_structure_function_features' && toolCall.rawResult) {
      return tryParseResult(toolCall.rawResult)
    }
    return tryParseResult(toolCall.resultPreview)
  }, [toolCall.name, toolCall.status, toolCall.resultPreview, toolCall.rawResult, taskState])
  const evidenceSource = useMemo(() => extractEvidenceSource(parsedResult), [parsedResult])

  // Parse result for analysis tools
  const analysisResult = useMemo(() => {
    if (!ANALYSIS_TOOLS.includes(toolCall.name) || !['completed', 'degraded'].includes(displayedStatus)) return null
    return parsedResult
  }, [parsedResult, toolCall.name, displayedStatus])

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
    canceled: 'Canceled',
    degraded: 'Degraded',
    poll_error: 'Status unavailable',
    waiting: 'NCBI 正在处理',
    submitting: '正在提交 NCBI',
    retry: '等待后台续查',
  }[displayedStatus] || displayedStatus

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-background/55 shadow-[0_6px_20px_rgba(15,23,42,0.03)]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-secondary/15"
      >
        {['waiting', 'submitting', 'retry'].includes(displayedStatus) ? <Clock className="w-4 h-4 text-blue-500" /> : displayedStatus === 'completed' ? statusIcon.completed : displayedStatus === 'degraded' ? <XCircle className="w-4 h-4 text-amber-500" /> : statusIcon[toolCall.status]}
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

      {(taskState?.error || toolCall.error) && (
        <p className="px-3 pb-2 text-xs text-red-500">{taskState?.error || toolCall.error}</p>
      )}
      {taskState?.message && (
        <p role="status" className="px-3 pb-2 text-xs text-muted-foreground">{taskState.message}</p>
      )}
      {taskState?.rid && <p className="px-3 pb-2 text-xs text-muted-foreground">NCBI 任务编号：{taskState.rid}</p>}
      {toolCall.name === 'blast_search' && taskState?.status === 'completed' && conversationId && (
        <div className="px-3 pb-3">
          <p role="status" className="mb-2 text-xs text-emerald-600">同源搜索已完成，可以将结果纳入更新报告。原报告将保留。</p>
          <button type="button" disabled={actionBusy || revisionCreated} onClick={() => void updateReport()} className="rounded-md border border-border px-3 py-1.5 text-xs disabled:opacity-50">
            {revisionCreated ? '更新报告已保存' : actionBusy ? '正在生成…' : '生成更新报告'}
          </button>
        </div>
      )}
      {taskState?.canResume && <button type="button" disabled={actionBusy} onClick={() => void resume()} className="mx-3 mb-3 rounded-md border border-border px-3 py-1.5 text-xs">继续查询原任务</button>}
      {actionError && <p role="alert" className="px-3 pb-2 text-xs text-red-500">{actionError}</p>}

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
