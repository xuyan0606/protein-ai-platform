import { ShieldAlert, TrendingUp, Target, Download, Printer } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'
import { ReportBadge, ReportBody, ReportHeader, ReportMetricCard, ReportMetricGrid, ReportPanel, ReportSection, ReportShell } from '@/components/analysis/ReportShell'

interface RecommendedMutation {
  mutation: string
  type: string
  purpose: string
  lipase_evidence?: {
    exact_match_count?: number
    matches?: Array<Record<string, unknown>>
    source?: string
    interpretation?: string
  }
}

interface CandidateFeatureCompleteness {
  schema_version?: string
  status?: string
  available_features?: string[]
  missing_feature_reasons?: string[]
  available_feature_count?: number
  missing_feature_count?: number
  evidence_level?: string
  no_wet_lab_claim?: boolean
}

interface StructureFeatureGapSummary {
  schema_version?: string
  status?: string
  row_count?: number
  feature_completeness_status_counts?: Record<string, number>
  available_feature_counts?: Record<string, number>
  missing_feature_reason_counts?: Record<string, number>
  top_missing_feature_reasons?: Array<{ reason?: string; count?: number }>
  report_action?: string
  must_not_claim?: string[]
}

interface ObjectiveAssayGapSummary {
  schema_version?: string
  status?: string
  objective_row_count?: number
  assay_required_counts?: Record<string, number>
  top_assay_gaps?: Array<{ assay?: string; count?: number }>
  blocking_reason_counts?: Record<string, number>
  top_blocking_reasons?: Array<{ reason?: string; count?: number }>
  project_feedback_readiness?: {
    status?: string
    evidence_level?: string
    data_quality_grade?: string
    measured_variant_count?: number
    hit_rate?: number | null
    objective?: string | null
    assay_key?: string | null
    dataset_fingerprint?: string | null
    boundary?: string
  }
  report_action?: string
  must_not_claim?: string[]
}

interface Candidate {
  position: number
  user_position?: string | number | null
  pdb_position?: string | number | null
  uniprot_position?: string | number | null
  numbering_status?: string | null
  wild_type: string
  composite_priority: number
  tier: number
  mutation_type?: string | null
  logic: string
  recommended_mutations: RecommendedMutation[]
  is_protected?: boolean
  active_site_distance_residues?: number | null
  active_site_sources?: string[]
  categories?: string[]
  lipase_position_evidence_count?: number
  expected_effect?: string
  risk_flags?: string[]
  experiment_priority?: string
  experiment_action?: string
  candidate_evidence_status?: string
  objective_missing_evidence?: string[]
  blocked_upgrade_conditions?: string[]
  structure_feature_status?: string | null
  ca_b_factor?: number | null
  nearest_catalytic_distance_ca_angstrom?: number | null
  contact_count_ca_8a?: number | null
  nearest_ca_neighbor_distance_angstrom?: number | null
  nearest_ca_neighbor_position?: number | null
  nearest_ca_neighbor_pdb_position?: string | null
  ca_contact_environment?: string | null
  secondary_structure?: string | null
  secondary_structure_source?: string | null
  rel_sasa?: number | null
  residue_sasa_angstrom2?: number | null
  rel_sasa_status?: string | null
  pocket_channel_interface_status?: string | null
  nonpolymer_proximity_status?: string | null
  nearest_nonpolymer_heteroatom_distance_angstrom?: number | null
  nearest_nonpolymer_component_id?: string | null
  nearest_nonpolymer_component_position?: string | null
  nonpolymer_component_ids_within_4a?: string[]
  phi_deg?: number | null
  psi_deg?: number | null
  backbone_torsion_status?: string | null
  backbone_torsion_reason?: string | null
  structure_feature_risk_flags?: string[]
  feature_completeness?: CandidateFeatureCompleteness
  missing_feature_reasons?: string[]
}

export interface MutationScoreData {
  sequence_length: number
  sequence_preview?: string
  engineering_goal: string
  target_ph?: number
  target_tm?: number
  active_site_positions: number[]
  active_site_position_sources?: Record<string, string[]>
  summary: {
    total_positions: number
    tier_1_count: number
    tier_2_count: number
    tier_3_count: number
    never_mutate_count: number
    never_mutate_positions: number[]
    catalytic_guardrail_enabled?: boolean
  }
  guardrails?: {
    protected_positions?: number[]
    sources?: Record<string, string[]>
    rule?: string
  }
  tier_1_candidates: Candidate[]
  tier_2_candidates: Candidate[]
  all_positions?: Candidate[]
  candidate_table_status?: string
  identity_gate?: {
    status?: string | null
    identity_status?: string | null
    reason?: string | null
  }
  objective_gate?: {
    status?: string | null
    objective?: string | null
    module?: string | null
    candidate_output_allowed?: boolean | null
    missing_evidence?: string[]
    ranking_boundary?: string | null
  }
  p2_engineering_scorecard_contract?: {
    status?: string
    component_status?: Record<string, string | null | undefined>
    candidate_statuses?: string[]
    blocked_reasons?: string[]
    report_action?: string
    must_not_claim?: string[]
  }
  candidate_table_generation?: {
    schema_version?: string
    status?: string
    experiment_design_policy?: {
      schema_version?: string
      excluded_candidate_statuses?: string[]
      excluded_priorities?: string[]
      requires_recommended_mutation?: boolean
      blocked_rows_excluded_count?: number
      blocked_rows_remain_traceable?: string
      no_wet_lab_claim?: boolean
    }
  }
  p2_candidate_readiness_summary?: {
    schema_version?: string
    status?: string
    candidate_table_status?: string
    candidate_row_scope?: string
    reported_candidate_count?: number
    all_position_count?: number
    feature_completeness_status_counts?: Record<string, number>
    candidate_status_counts?: Record<string, number>
    missing_feature_reason_counts?: Record<string, number>
    top_missing_feature_reasons?: Array<{ reason?: string; count?: number }>
    report_action?: string
    must_not_claim?: string[]
  }
  p2_objective_score_readiness_summary?: {
    schema_version?: string
    status?: string
    objective_row_count?: number
    component_status_counts?: Record<string, Record<string, number>>
    unknown_component_counts?: Record<string, number>
    top_unknown_components?: Array<{ component?: string; count?: number }>
    assay_required_counts?: Record<string, number>
    blocking_reason_counts?: Record<string, number>
    top_blocking_reasons?: Array<{ reason?: string; count?: number }>
    aggregation?: string
    no_composite_score?: boolean
    report_action?: string
    must_not_claim?: string[]
  }
  p2_structure_feature_gap_summary?: StructureFeatureGapSummary
  p2_objective_assay_gap_summary?: ObjectiveAssayGapSummary
  strategy?: {
    objective?: string
    design_principle?: string
    screening_logic?: string[]
    preserved_constraints?: string[]
    experiment_plan?: Array<{ priority: string; scope: string; purpose: string; gate: string }>
    confidence_boundary?: string
  }
}

const GOAL_LABELS: Record<string, string> = {
  ph_lowering: 'pH降低改造',
  ph_raising: 'pH升高改造',
  thermostability: '热稳定性改造',
  activity: '活性改造',
  specificity: '底物特异性改造',
  general: '通用改造',
}

const TYPE_TONES: Record<string, 'info' | 'warning' | 'neutral'> = {
  表面电荷翻转: 'info',
  活性中心电荷中和: 'info',
  增加loop刚性: 'warning',
  表面电荷优化: 'info',
  表面电荷网络优化: 'info',
  loop稳定性: 'warning',
}

function TierBadge({ tier }: { tier: number }) {
  const map: Record<number, { tone: 'success' | 'warning' | 'neutral'; label: string }> = {
    1: { tone: 'success', label: '优先' },
    2: { tone: 'warning', label: '可选' },
    3: { tone: 'neutral', label: '保守' },
  }
  const badge = map[tier] || map[3]
  return <ReportBadge tone={badge.tone}>{badge.label}</ReportBadge>
}

function typeTone(type: string): 'info' | 'warning' | 'neutral' {
  return TYPE_TONES[type] || 'neutral'
}

function experimentTone(priority?: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (priority?.startsWith('P1')) return 'success'
  if (priority === 'No-Go') return 'danger'
  if (priority?.startsWith('P2') || priority?.startsWith('P3')) return 'warning'
  return 'neutral'
}

function evidenceTone(status?: string): 'success' | 'warning' | 'neutral' {
  if (status === 'ready') return 'success'
  if (status === 'exploratory_requires_objective_evidence') return 'warning'
  if (status === 'computational_hypothesis') return 'warning'
  if (status === 'wet_lab_calibrated' || status === 'experimental_supported') return 'success'
  return 'neutral'
}

function evidenceLabel(status?: string): string {
  if (status === 'ready') return '可排单'
  if (status === 'exploratory_requires_objective_evidence') return '探索性'
  if (status === 'computational_hypothesis') return '计算假设'
  if (status === 'wet_lab_calibrated') return '项目校准'
  if (status === 'experimental_supported') return '实验证据'
  if (status === 'blocked') return '已阻断'
  if (status === 'blocked_by_identity_gate') return '身份未过'
  return status || '待确认'
}

function featureCompletenessTone(status?: string, missingCount?: number): 'success' | 'warning' | 'neutral' {
  if (missingCount === 0 && ['ready', 'complete', 'available'].includes(status || '')) return 'success'
  if (!status || status === 'not_reported') return 'neutral'
  return 'warning'
}

function getMissingFeatureReasons(candidate: Candidate): string[] {
  const contractReasons = candidate.feature_completeness?.missing_feature_reasons
  if (Array.isArray(contractReasons)) return contractReasons
  return Array.isArray(candidate.missing_feature_reasons) ? candidate.missing_feature_reasons : []
}

function featureCompletenessStatus(candidate: Candidate): string {
  return candidate.feature_completeness?.status || 'not_reported'
}

function featureCompletenessCountLabel(candidate: Candidate): string {
  const completeness = candidate.feature_completeness
  const available = completeness?.available_feature_count
  const missing = completeness?.missing_feature_count ?? getMissingFeatureReasons(candidate).length
  if (typeof available === 'number') return `${available} available / ${missing} missing`
  return `${missing} missing`
}

function formatPositionValue(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '未映射'
  return String(value)
}

function formatUserPosition(candidate: Candidate): string {
  return formatPositionValue(candidate.user_position ?? candidate.position)
}

function formatRecommendedMutations(candidate: Candidate): string {
  if (candidate.recommended_mutations.length > 0) {
    return candidate.recommended_mutations.slice(0, 3).map((mutation) => mutation.mutation).join(' / ')
  }
  return candidate.is_protected ? '禁止突变' : `${candidate.wild_type}${candidate.position}`
}

function formatFeatureNumber(value?: number | null, digits = 1): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'NA'
}

function hasStructureFeature(candidate: Candidate): boolean {
  return candidate.structure_feature_status === 'available'
}

function structureFeatureItems(candidate: Candidate): string[] {
  return [
    `CA B-factor ${formatFeatureNumber(candidate.ca_b_factor)}`,
    `催化CA距离 ${formatFeatureNumber(candidate.nearest_catalytic_distance_ca_angstrom)} Å`,
    `最近CA邻居 ${candidate.nearest_ca_neighbor_position ?? candidate.nearest_ca_neighbor_pdb_position ?? 'NA'} / ${formatFeatureNumber(candidate.nearest_ca_neighbor_distance_angstrom)} Å`,
    `8Å CA contacts ${formatFeatureNumber(candidate.contact_count_ca_8a, 0)}`,
    `CA环境 ${candidate.ca_contact_environment || 'NA'}`,
    `二级结构 ${candidate.secondary_structure || 'unknown'}`,
    `relSASA ${formatFeatureNumber(candidate.rel_sasa, 3)}`,
    `非聚合HETATM ${formatFeatureNumber(candidate.nearest_nonpolymer_heteroatom_distance_angstrom)} Å${candidate.nearest_nonpolymer_component_id ? ` (${candidate.nearest_nonpolymer_component_id})` : ''}`,
    `主链 phi/psi ${formatFeatureNumber(candidate.phi_deg, 2)}/${formatFeatureNumber(candidate.psi_deg, 2)}`,
  ]
}

function decisionSummary(candidates: Candidate[], protectedRows: Candidate[], tableStatus?: string, objectiveStatus?: string | null) {
  const goCount = candidates.filter((candidate) => candidate.experiment_priority?.startsWith('P1') && !candidate.is_protected).length
  const noGoCount = protectedRows.length + candidates.filter((candidate) => candidate.experiment_priority === 'No-Go' || candidate.is_protected).length
  const watchCount = candidates.filter((candidate) => {
    const priority = candidate.experiment_priority || ''
    return !candidate.is_protected && (priority.startsWith('P2') || priority.startsWith('P3') || candidate.candidate_evidence_status !== 'ready')
  }).length
  const isIdentityBlocked = tableStatus === 'blocked_by_identity_gate'
  const objectiveNeedsEvidence = objectiveStatus === 'blocked'

  return [
    {
      label: 'Go',
      value: isIdentityBlocked || objectiveNeedsEvidence ? 0 : goCount,
      tone: 'success' as const,
      description: isIdentityBlocked
        ? '身份或编号门控未通过，未生成候选'
        : objectiveNeedsEvidence
          ? '目标证据未补齐，先按 Watch 小批验证'
          : '首轮优先单点验证',
    },
    {
      label: 'Watch',
      value: isIdentityBlocked ? 0 : watchCount,
      tone: 'warning' as const,
      description: isIdentityBlocked ? '没有放行的候选位点' : '探索性或第二梯队，需带对照复核',
    },
    {
      label: 'No-Go',
      value: isIdentityBlocked ? '门控' : noGoCount,
      tone: 'danger' as const,
      description: isIdentityBlocked ? '身份或编号硬门控未通过' : '保护位点或禁止突变',
    },
  ]
}

export function MutationScoreCard({ data }: { data: MutationScoreData }) {
  const { summary, tier_1_candidates, tier_2_candidates, engineering_goal, active_site_positions, target_ph, target_tm } = data
  const protectedPositions = data.guardrails?.protected_positions || summary.never_mutate_positions || []
  const guardrailSources = data.guardrails?.sources || data.active_site_position_sources || {}
  const protectedRows = (data.all_positions || []).filter((item) => item.is_protected).slice(0, 8)
  const mutationTableCandidates = [...tier_1_candidates, ...tier_2_candidates].slice(0, 20)
  const isIdentityBlocked = data.candidate_table_status === 'blocked_by_identity_gate'
    || data.identity_gate?.status === 'blocked'
  const decisions = decisionSummary(mutationTableCandidates, protectedRows, data.candidate_table_status, data.objective_gate?.status)
  const p2Contract = data.p2_engineering_scorecard_contract
  const experimentDesignPolicy = data.candidate_table_generation?.experiment_design_policy
  const p2CandidateReadiness = data.p2_candidate_readiness_summary
  const p2ObjectiveReadiness = data.p2_objective_score_readiness_summary
  const p2StructureFeatureGapSummary = data.p2_structure_feature_gap_summary
  const p2ObjectiveAssayGapSummary = data.p2_objective_assay_gap_summary
  const p2BlockedReasons = p2Contract?.blocked_reasons || []
  const p2MustNotClaim = p2Contract?.must_not_claim || []

  return (
    <ReportShell>
      <ReportHeader
        icon={Target}
        title="突变优先级分析"
        subtitle={`${GOAL_LABELS[engineering_goal] || engineering_goal}${target_ph != null ? ` · 目标 pH ${target_ph}` : ''}${target_tm != null ? ` · 目标 Tm ${target_tm}°C` : ''} · 扫描 ${summary.total_positions} 个位点`}
        actions={
          <>
            <button onClick={() => downloadReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="下载报告">
              <Download className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => printReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="打印报告">
              <Printer className="w-3.5 h-3.5" />
            </button>
          </>
        }
      />
      <ReportBody>
        <ReportSection title="首轮决策" icon={ShieldAlert}>
          <div className="grid gap-2 sm:grid-cols-3">
            {decisions.map((item) => (
              <ReportPanel key={item.label} tone={item.tone} className="px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-foreground">{item.label}</div>
                  <div className="font-mono text-lg font-bold">{item.value}</div>
                </div>
                <div className="mt-1 text-[11px] leading-5 text-muted-foreground">{item.description}</div>
              </ReportPanel>
            ))}
          </div>
        </ReportSection>

        {(p2Contract || p2CandidateReadiness || p2ObjectiveReadiness) ? (
          <ReportSection title="P2 合同状态" icon={ShieldAlert}>
            <ReportPanel tone={p2Contract?.status === 'ready' ? 'info' : 'warning'} className="space-y-3">
              {p2Contract ? (
                <div className="flex flex-wrap items-center gap-2">
                  <ReportBadge tone={p2Contract.status === 'ready' ? 'success' : 'warning'}>
                    {p2Contract.status || 'unknown'}
                  </ReportBadge>
                  {Object.entries(p2Contract.component_status || {}).map(([key, value]) => (
                    <span key={key} className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                      {key}: <span className="font-mono text-foreground">{value || 'unknown'}</span>
                    </span>
                  ))}
                </div>
              ) : null}
              {experimentDesignPolicy ? (
                <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="font-semibold text-foreground">排单门控</span>
                    <ReportBadge tone="warning">
                      blocked excluded {experimentDesignPolicy.blocked_rows_excluded_count ?? 0}
                    </ReportBadge>
                    <span className="font-mono text-muted-foreground">{experimentDesignPolicy.schema_version || 'experiment_design_schedulability_policy_v1'}</span>
                  </div>
                  <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                    Exclude status: {(experimentDesignPolicy.excluded_candidate_statuses || ['blocked']).join(', ')} · priority: {(experimentDesignPolicy.excluded_priorities || ['No-Go']).join(', ')} · trace: {experimentDesignPolicy.blocked_rows_remain_traceable || 'all_positions'}
                  </div>
                </div>
              ) : null}
              {p2CandidateReadiness ? (
                <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="font-semibold text-foreground">候选证据 readiness</span>
                    <ReportBadge tone={p2CandidateReadiness.status === 'complete' ? 'success' : p2CandidateReadiness.status === 'blocked' ? 'danger' : 'warning'}>
                      {p2CandidateReadiness.status || 'unknown'}
                    </ReportBadge>
                    <span className="font-mono text-muted-foreground">{p2CandidateReadiness.schema_version || 'p2_candidate_readiness_summary_v1'}</span>
                    <span className="text-muted-foreground">
                      reported {p2CandidateReadiness.reported_candidate_count ?? 0} / all {p2CandidateReadiness.all_position_count ?? 0}
                    </span>
                  </div>
                  {(p2CandidateReadiness.top_missing_feature_reasons || []).length > 0 ? (
                    <div className="mt-1 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
                      Top missing: {p2CandidateReadiness.top_missing_feature_reasons?.slice(0, 5).map((item) => `${item.reason || 'unknown'}(${item.count ?? 0})`).join('；')}
                    </div>
                  ) : null}
                  {p2CandidateReadiness.report_action ? (
                    <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                      Action: {p2CandidateReadiness.report_action}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {p2ObjectiveReadiness ? (
                <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="font-semibold text-foreground">目标分量 readiness</span>
                    <ReportBadge tone={p2ObjectiveReadiness.status === 'complete' ? 'success' : p2ObjectiveReadiness.status === 'missing' ? 'danger' : 'warning'}>
                      {p2ObjectiveReadiness.status || 'unknown'}
                    </ReportBadge>
                    <span className="font-mono text-muted-foreground">{p2ObjectiveReadiness.schema_version || 'p2_objective_score_readiness_summary_v1'}</span>
                    <span className="text-muted-foreground">
                      rows {p2ObjectiveReadiness.objective_row_count ?? 0} · aggregation {p2ObjectiveReadiness.aggregation || 'none'}
                    </span>
                  </div>
                  {(p2ObjectiveReadiness.top_unknown_components || []).length > 0 ? (
                    <div className="mt-1 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
                      Unknown components: {p2ObjectiveReadiness.top_unknown_components?.slice(0, 6).map((item) => `${item.component || 'unknown'}(${item.count ?? 0})`).join('；')}
                    </div>
                  ) : null}
                  {(p2ObjectiveReadiness.top_blocking_reasons || []).length > 0 ? (
                    <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                      Blocking: {p2ObjectiveReadiness.top_blocking_reasons?.slice(0, 4).map((item) => `${item.reason || 'unknown'}(${item.count ?? 0})`).join('；')}
                    </div>
                  ) : null}
                  {p2ObjectiveReadiness.report_action ? (
                    <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                      Action: {p2ObjectiveReadiness.report_action}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {(p2StructureFeatureGapSummary || p2ObjectiveAssayGapSummary) ? (
                <div className="grid gap-2 md:grid-cols-2">
                  {p2StructureFeatureGapSummary ? (
                    <div className="rounded-md border border-border/70 bg-secondary/20 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="font-semibold text-foreground">结构特征 gap</span>
                        <ReportBadge tone={p2StructureFeatureGapSummary.status === 'complete' ? 'success' : p2StructureFeatureGapSummary.status === 'missing' ? 'danger' : 'warning'}>
                          {p2StructureFeatureGapSummary.status || 'unknown'}
                        </ReportBadge>
                        <span className="font-mono text-muted-foreground">{p2StructureFeatureGapSummary.schema_version || 'p2_structure_feature_gap_summary_v1'}</span>
                        <span className="text-muted-foreground">rows {p2StructureFeatureGapSummary.row_count ?? 0}</span>
                      </div>
                      {(p2StructureFeatureGapSummary.top_missing_feature_reasons || []).length > 0 ? (
                        <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                          Missing: {p2StructureFeatureGapSummary.top_missing_feature_reasons?.slice(0, 4).map((item) => `${item.reason || 'unknown'}(${item.count ?? 0})`).join('；')}
                        </div>
                      ) : null}
                      {p2StructureFeatureGapSummary.report_action ? (
                        <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                          Action: {p2StructureFeatureGapSummary.report_action}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {p2ObjectiveAssayGapSummary ? (
                    <div className="rounded-md border border-border/70 bg-secondary/20 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="font-semibold text-foreground">目标 assay gap</span>
                        <ReportBadge tone={p2ObjectiveAssayGapSummary.status === 'complete' ? 'success' : p2ObjectiveAssayGapSummary.status === 'missing' ? 'danger' : 'warning'}>
                          {p2ObjectiveAssayGapSummary.status || 'unknown'}
                        </ReportBadge>
                        <span className="font-mono text-muted-foreground">{p2ObjectiveAssayGapSummary.schema_version || 'p2_objective_assay_gap_summary_v1'}</span>
                        <span className="text-muted-foreground">rows {p2ObjectiveAssayGapSummary.objective_row_count ?? 0}</span>
                      </div>
                      {(p2ObjectiveAssayGapSummary.top_assay_gaps || []).length > 0 ? (
                        <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                          Assays: {p2ObjectiveAssayGapSummary.top_assay_gaps?.slice(0, 4).map((item) => `${item.assay || 'unknown'}(${item.count ?? 0})`).join('；')}
                        </div>
                      ) : null}
                      {p2ObjectiveAssayGapSummary.project_feedback_readiness ? (
                        <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                          Feedback: {p2ObjectiveAssayGapSummary.project_feedback_readiness.status || 'unknown'} · {p2ObjectiveAssayGapSummary.project_feedback_readiness.evidence_level || 'unknown'} · n={p2ObjectiveAssayGapSummary.project_feedback_readiness.measured_variant_count ?? 0}
                        </div>
                      ) : null}
                      {p2ObjectiveAssayGapSummary.report_action ? (
                        <div className="mt-1 text-[11px] leading-5 text-muted-foreground">
                          Action: {p2ObjectiveAssayGapSummary.report_action}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {p2BlockedReasons.length > 0 ? (
                <div className="text-[11px] leading-5 text-muted-foreground">
                  Blocked reasons: {p2BlockedReasons.slice(0, 4).join(', ')}
                </div>
              ) : null}
              {p2MustNotClaim.length > 0 ? (
                <div className="text-[11px] leading-5 text-muted-foreground">
                  Must not claim: {p2MustNotClaim.slice(0, 4).join(', ')}
                </div>
              ) : null}
            </ReportPanel>
          </ReportSection>
        ) : null}

        {data.strategy && (
          <ReportSection title="改造策略" icon={Target}>
            <ReportPanel tone="info" className="space-y-4">
              <div>
                <div className="text-sm font-semibold text-foreground">目标</div>
                <p className="mt-1 text-xs leading-6 text-muted-foreground">{data.strategy.objective}</p>
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">设计原则</div>
                <p className="mt-1 text-xs leading-6 text-muted-foreground">{data.strategy.design_principle}</p>
              </div>
              {(data.strategy.screening_logic || []).length > 0 && (
                <div>
                  <div className="text-sm font-semibold text-foreground">位点筛选逻辑</div>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-5 text-muted-foreground">
                    {data.strategy.screening_logic?.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {(data.strategy.preserved_constraints || []).length > 0 && (
                <div className="rounded-md border border-red-500/15 bg-red-500/5 px-3 py-2">
                  <div className="text-xs font-semibold text-red-700 dark:text-red-300">保护约束</div>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] leading-5 text-red-700/80 dark:text-red-200/80">
                    {data.strategy.preserved_constraints?.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {(data.strategy.experiment_plan || []).length > 0 && (
                <div>
                  <div className="text-sm font-semibold text-foreground">实验优先级</div>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full min-w-[620px] border-collapse text-left text-[11px]">
                      <thead>
                        <tr className="border-b border-border/70 text-muted-foreground">
                          <th className="px-2 py-2 font-medium">优先级</th>
                          <th className="px-2 py-2 font-medium">实验层级</th>
                          <th className="px-2 py-2 font-medium">目的</th>
                          <th className="px-2 py-2 font-medium">进入下一层的条件</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.strategy.experiment_plan?.map((item) => (
                          <tr key={`${item.priority}-${item.scope}`} className="border-b border-border/50 align-top">
                            <td className="px-2 py-2 font-mono font-semibold text-primary">{item.priority}</td>
                            <td className="px-2 py-2 font-medium">{item.scope}</td>
                            <td className="px-2 py-2 text-muted-foreground">{item.purpose}</td>
                            <td className="px-2 py-2 text-muted-foreground">{item.gate}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {data.strategy.confidence_boundary && (
                <p className="border-t border-border/60 pt-3 text-[11px] leading-5 text-muted-foreground">
                  证据边界：{data.strategy.confidence_boundary}
                </p>
              )}
            </ReportPanel>
          </ReportSection>
        )}

        {isIdentityBlocked && (
          <ReportSection title="突变候选输出门控" icon={ShieldAlert}>
            <ReportPanel tone="danger" className="space-y-2">
              <div className="text-sm font-semibold text-red-700 dark:text-red-300">本轮不输出具体突变候选</div>
              <p className="text-xs leading-6 text-muted-foreground">
                酶身份、催化/关键残基或编号映射尚未确认。当前结果只能用于证据补齐，不能作为比活力改造位点。
              </p>
              {data.identity_gate?.identity_status && (
                <div className="text-[11px] text-muted-foreground">身份状态：{data.identity_gate.identity_status}</div>
              )}
              {data.identity_gate?.reason && (
                <div className="text-[11px] leading-5 text-muted-foreground">门控说明：{data.identity_gate.reason}</div>
              )}
              <div className="border-t border-border/60 pt-2 text-[11px] leading-5 text-muted-foreground">
                下一步：确认序列同源/家族、催化残基和 PDB/UniProt 编号后，再生成口袋入口、通道和二壳层候选。
              </div>
            </ReportPanel>
          </ReportSection>
        )}

        <ReportSection title="候选汇总">
          <ReportMetricGrid>
            <ReportMetricCard label="优先改造" value={summary.tier_1_count} meta="优先级 > 7.0" tone="success" />
            <ReportMetricCard label="可选改造" value={summary.tier_2_count} meta="优先级 5.0 - 7.0" tone="warning" />
            <ReportMetricCard label="低优先" value={summary.tier_3_count} meta="优先级 < 5.0" tone="neutral" />
            <ReportMetricCard
              label="禁止突变"
              value={summary.never_mutate_count}
              meta={summary.catalytic_guardrail_enabled ? '催化护栏已启用' : '未启用催化护栏'}
              tone="danger"
            />
          </ReportMetricGrid>
        </ReportSection>

        {active_site_positions.length > 0 && (
          <ReportSection title="保护位点" icon={ShieldAlert}>
            <ReportPanel tone="danger" className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium">活性中心/保护位点</span>
                {protectedPositions.map((p) => (
                  <code key={p} className="rounded-md border border-red-500/20 bg-background/70 px-2 py-1 font-mono text-[10px] text-red-600 dark:text-red-300">
                    {p}
                  </code>
                ))}
              </div>
              <p className="text-xs leading-6 text-muted-foreground">
                {data.guardrails?.rule || '保护位点会被强制降级并禁止生成推荐突变；邻近位点也会被附加惩罚。'}
              </p>
              <div className="flex flex-wrap gap-2">
                {protectedPositions.map((position) => (
                  <div key={`source-${position}`} className="flex items-center gap-1 rounded-full border border-red-500/15 bg-background/70 px-2 py-1">
                    <code className="font-mono text-[10px] text-red-600 dark:text-red-300">{position}</code>
                    {(guardrailSources[String(position)] || []).map((source) => (
                      <ReportBadge
                        key={`${position}-${source}`}
                        tone={source === 'curated' ? 'success' : source === 'input' ? 'info' : 'warning'}
                        className="px-2 py-0.5"
                      >
                        {source}
                      </ReportBadge>
                    ))}
                  </div>
                ))}
              </div>
            </ReportPanel>
          </ReportSection>
        )}

        {protectedRows.length > 0 && (
          <ReportSection title="禁止位点">
            <div className="space-y-2">
              {protectedRows.map((c) => (
                <MutationRow key={`protected-${c.position}`} candidate={c} forceTone="danger" />
              ))}
            </div>
          </ReportSection>
        )}

        {data.objective_gate && (
          <ReportSection title="目标模块门控" icon={ShieldAlert}>
            <ReportPanel tone={data.objective_gate.status === 'ready' ? 'success' : 'warning'} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <ReportBadge tone={data.objective_gate.status === 'ready' ? 'success' : 'warning'}>
                  {evidenceLabel(data.objective_gate.status || undefined)}
                </ReportBadge>
                <span className="text-muted-foreground">
                  模块：{data.objective_gate.module || data.objective_gate.objective || '待确认'}
                </span>
                <span className="text-muted-foreground">
                  候选输出：{data.objective_gate.candidate_output_allowed ? '允许' : '未放行'}
                </span>
              </div>
              {(data.objective_gate.missing_evidence || []).length > 0 && (
                <div className="text-[11px] leading-5 text-amber-700 dark:text-amber-300">
                  缺失证据：{data.objective_gate.missing_evidence?.join('；')}
                </div>
              )}
              {data.objective_gate.ranking_boundary && (
                <div className="text-[11px] leading-5 text-muted-foreground">
                  排序边界：{data.objective_gate.ranking_boundary}
                </div>
              )}
            </ReportPanel>
          </ReportSection>
        )}

        {mutationTableCandidates.length > 0 && (
          <ReportSection title="候选突变位点" icon={TrendingUp}>
            <MutationCandidateTable candidates={mutationTableCandidates} tableStatus={data.candidate_table_status} />
          </ReportSection>
        )}

        {tier_1_candidates.length > 0 && (
          <ReportSection title="首轮实验候选位点" icon={TrendingUp}>
            <div className="space-y-2">
              {tier_1_candidates.map((c) => (
                <MutationRow key={c.position} candidate={c} />
              ))}
            </div>
          </ReportSection>
        )}

        {tier_2_candidates.length > 0 && (
          <ReportSection title="第二梯队候选位点">
            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {tier_2_candidates.map((c) => (
                <MutationRow key={c.position} candidate={c} />
              ))}
            </div>
          </ReportSection>
        )}
      </ReportBody>
    </ReportShell>
  )
}

function MutationCandidateTable({ candidates, tableStatus }: { candidates: Candidate[]; tableStatus?: string }) {
  return (
    <ReportPanel className="overflow-hidden p-0">
      {tableStatus && tableStatus !== 'ready' && (
        <div className="border-b border-border/70 bg-amber-500/8 px-3 py-2 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
          当前突变主表状态：{evidenceLabel(tableStatus)}。位点可用于首轮探索排单，但目标性质结论需要补充基线或对照实验后确认。
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] border-collapse text-left text-xs">
          <thead className="bg-secondary/45 text-[11px] text-muted-foreground">
            <tr className="border-b border-border/70">
              <th className="w-16 px-3 py-3 font-semibold">优先级</th>
              <th className="w-28 px-3 py-3 font-semibold">位点/编号</th>
              <th className="w-36 px-3 py-3 font-semibold">推荐突变</th>
              <th className="min-w-[300px] px-3 py-3 font-semibold">机制逻辑</th>
              <th className="min-w-[220px] px-3 py-3 font-semibold">主要风险</th>
              <th className="min-w-[220px] px-3 py-3 font-semibold">P2证据覆盖</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => {
              const riskText = (candidate.risk_flags || []).length > 0 ? candidate.risk_flags?.join('；') : '需实验确认'
              const missingFeatureReasons = getMissingFeatureReasons(candidate)
              const featureStatus = featureCompletenessStatus(candidate)
              return (
                <tr key={`${candidate.position}-${formatRecommendedMutations(candidate)}`} className="border-b border-border/50 align-top last:border-b-0">
                  <td className="px-3 py-3">
                    <ReportBadge tone={experimentTone(candidate.experiment_priority)}>
                      {candidate.experiment_priority || `Tier ${candidate.tier}`}
                    </ReportBadge>
                  </td>
                  <td className="px-3 py-3">
                    <div className="space-y-1 font-mono text-[11px] text-foreground/85">
                      <code className="rounded-md border border-primary/15 bg-primary/8 px-2 py-1 font-mono text-[12px] font-bold text-primary">
                        {candidate.wild_type}{formatUserPosition(candidate)}
                      </code>
                      <div>PDB: {formatPositionValue(candidate.pdb_position)}</div>
                      <div>UniProt: {formatPositionValue(candidate.uniprot_position)}</div>
                    </div>
                    {candidate.numbering_status && (
                      <div className="mt-1 text-[10px] text-muted-foreground">{candidate.numbering_status}</div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <code className="rounded-md border border-primary/15 bg-primary/8 px-2 py-1 font-mono text-[12px] font-bold text-primary">
                      {formatRecommendedMutations(candidate)}
                    </code>
                  </td>
                  <td className="px-3 py-3 leading-6 text-foreground/85">
                    {candidate.logic}
                    {candidate.mutation_type ? (
                      <span className="ml-2 inline-flex">
                        <ReportBadge tone={typeTone(candidate.mutation_type)}>{candidate.mutation_type}</ReportBadge>
                      </span>
                    ) : null}
                    <span className="ml-2 inline-flex">
                      <ReportBadge tone={evidenceTone(candidate.candidate_evidence_status)}>
                        {evidenceLabel(candidate.candidate_evidence_status)}
                      </ReportBadge>
                    </span>
                    {hasStructureFeature(candidate) && (
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] leading-5 text-muted-foreground">
                        <span className="font-semibold text-foreground/75">结构证据</span>
                        {structureFeatureItems(candidate).map((item) => (
                          <span key={item} className="rounded-md border border-border/70 bg-secondary/35 px-1.5 py-0.5">
                            {item}
                          </span>
                        ))}
                      </div>
                    )}
                    {(candidate.rel_sasa_status || candidate.pocket_channel_interface_status || candidate.nonpolymer_proximity_status || candidate.backbone_torsion_status) && (
                      <div className="mt-1 text-[10px] leading-5 text-muted-foreground">
                        relSASA状态: {candidate.rel_sasa_status || 'not_computed'} · 口袋/通道: {candidate.pocket_channel_interface_status || 'not_computed'} · 非聚合HETATM: {candidate.nonpolymer_proximity_status || 'not_computed'} · 主链phi/psi: {candidate.backbone_torsion_status || 'not_computed'}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 leading-6 text-amber-700 dark:text-amber-300">
                    {riskText}
                    {hasStructureFeature(candidate) && (candidate.structure_feature_risk_flags || []).length > 0 && (
                      <div className="mt-1 text-[10px] leading-5 text-muted-foreground">
                        结构风险：{candidate.structure_feature_risk_flags?.join('；')}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 leading-5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <ReportBadge tone={featureCompletenessTone(featureStatus, missingFeatureReasons.length)}>
                        {featureStatus}
                      </ReportBadge>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {featureCompletenessCountLabel(candidate)}
                      </span>
                    </div>
                    <div className="mt-1 text-[10px] leading-5 text-muted-foreground">
                      {candidate.feature_completeness?.schema_version || 'candidate_feature_completeness_v1'}
                    </div>
                    {missingFeatureReasons.length > 0 ? (
                      <div className="mt-1 text-[10px] leading-5 text-amber-700 dark:text-amber-300">
                        缺失：{missingFeatureReasons.slice(0, 4).join('；')}
                      </div>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </ReportPanel>
  )
}

function MutationRow({ candidate: c, forceTone }: { candidate: Candidate; forceTone?: 'danger' }) {
  const scoreColor = c.is_protected ? 'text-red-600 dark:text-red-300' : c.tier === 1 ? 'text-emerald-500' : 'text-amber-500'
  const panelTone = forceTone || (c.is_protected ? 'danger' : 'neutral')
  const missingFeatureReasons = getMissingFeatureReasons(c)
  const featureStatus = featureCompletenessStatus(c)

  return (
    <ReportPanel className="space-y-3" tone={panelTone}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <TierBadge tier={c.tier} />
          <code className="text-sm font-bold font-mono">{c.wild_type}{c.position}</code>
          {c.is_protected ? <ReportBadge tone="danger">禁止突变</ReportBadge> : null}
          {c.mutation_type && (
            <ReportBadge tone={typeTone(c.mutation_type)}>
              {c.mutation_type}
            </ReportBadge>
          )}
          {c.experiment_priority && (
            <ReportBadge tone={experimentTone(c.experiment_priority)}>
              实验 {c.experiment_priority}
            </ReportBadge>
          )}
          {(c.active_site_sources || []).map((source) => (
            <ReportBadge
              key={`${c.position}-${source}`}
              tone={source === 'curated' ? 'success' : source === 'input' ? 'info' : 'warning'}
            >
              {source}
            </ReportBadge>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground">优先分</span>
          <span className={`font-mono text-sm font-bold ${scoreColor}`}>
            {c.composite_priority.toFixed(1)}
          </span>
        </div>
      </div>

      <p className="text-xs leading-6 text-muted-foreground">{c.logic}</p>

      {c.expected_effect && (
        <div className="text-[11px] leading-5 text-foreground/80">
          <span className="font-semibold">预期方向：</span>{c.expected_effect}
        </div>
      )}

      {hasStructureFeature(c) && (
        <div className="flex flex-wrap items-center gap-1.5 text-[11px] leading-5 text-muted-foreground">
          <span className="font-semibold text-foreground/80">结构证据：</span>
          {structureFeatureItems(c).map((item) => (
            <span key={item} className="rounded-md border border-border/70 bg-secondary/35 px-2 py-1">
              {item}
            </span>
          ))}
          {(c.structure_feature_risk_flags || []).length > 0 && (
            <span className="text-amber-700 dark:text-amber-300">
              风险：{c.structure_feature_risk_flags?.join('；')}
            </span>
          )}
        </div>
      )}
      {(c.rel_sasa_status || c.pocket_channel_interface_status || c.nonpolymer_proximity_status || c.backbone_torsion_status) && (
        <div className="text-[11px] leading-5 text-muted-foreground">
          relSASA状态: {c.rel_sasa_status || 'not_computed'} · 口袋/通道: {c.pocket_channel_interface_status || 'not_computed'} · 非聚合HETATM: {c.nonpolymer_proximity_status || 'not_computed'} · 主链phi/psi: {c.backbone_torsion_status || 'not_computed'}
        </div>
      )}

      {(c.feature_completeness || missingFeatureReasons.length > 0) && (
        <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-foreground">P2证据覆盖</span>
            <ReportBadge tone={featureCompletenessTone(featureStatus, missingFeatureReasons.length)}>
              {featureStatus}
            </ReportBadge>
            <span className="font-mono">{featureCompletenessCountLabel(c)}</span>
            <span className="font-mono">{c.feature_completeness?.schema_version || 'candidate_feature_completeness_v1'}</span>
          </div>
          {missingFeatureReasons.length > 0 ? (
            <div className="mt-1 text-amber-700 dark:text-amber-300">
              缺失证据：{missingFeatureReasons.slice(0, 6).join('；')}
            </div>
          ) : null}
        </div>
      )}

      {(c.risk_flags || []).length > 0 && (
        <div className="rounded-md border border-amber-500/15 bg-amber-500/5 px-3 py-2 text-[11px] leading-5 text-amber-700 dark:text-amber-300">
          <span className="font-semibold">风险提示：</span>{c.risk_flags?.join('；')}
        </div>
      )}

      {(c.blocked_upgrade_conditions || []).length > 0 && (
        <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
          <span className="font-semibold text-foreground">升级条件：</span>{c.blocked_upgrade_conditions?.join('；')}
        </div>
      )}

      {c.active_site_distance_residues != null ? (
        <div className="text-[11px] text-muted-foreground">
          距离保护位点 {c.active_site_distance_residues} 个残基
        </div>
      ) : null}

      {typeof c.lipase_position_evidence_count === 'number' && c.lipase_position_evidence_count > 0 && (
        <div className="rounded-md border border-emerald-500/15 bg-emerald-500/5 px-3 py-2 text-[11px] leading-5 text-emerald-700 dark:text-emerald-300">
          KWB Lipase DB：该位点有 {c.lipase_position_evidence_count} 条文献/变体位置证据；需确认编号体系后使用。
        </div>
      )}

      {c.recommended_mutations.length > 0 && !c.is_protected && (
        <div className="flex flex-wrap gap-2">
          {c.recommended_mutations.map((m) => (
            <div key={m.mutation} className="group relative">
              <code className="cursor-default rounded-md border border-primary/15 bg-primary/8 px-2 py-1 font-mono text-[10px] font-medium text-primary">
                {m.mutation}
              </code>
              <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border/70 bg-popover px-2 py-1 text-[10px] text-foreground opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
                {m.purpose}
              </div>
              {m.lipase_evidence?.exact_match_count ? (
                <span className="ml-1 rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700 dark:text-emerald-300">
                  lipase {m.lipase_evidence.exact_match_count}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {c.is_protected && (
        <div className="text-[11px] font-medium text-red-700 dark:text-red-300">
          该位点已被催化护栏锁定，不生成任何推荐突变。
        </div>
      )}
    </ReportPanel>
  )
}
