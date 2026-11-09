import { Activity, TrendingUp, TrendingDown, ShieldCheck, ShieldAlert, Circle, Download, Printer, Zap, AlertTriangle } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'
import { buildToolTaskArtifactBundleUrl } from '@/lib/api'
import { ReportBody, ReportDataTable, ReportHeader, ReportMetricCard, ReportMetricGrid, ReportPanel, ReportSection, ReportShell } from '@/components/analysis/ReportShell'

interface SimulationParams {
  sequence_length: number | null
  protocol_id?: string | null
  simulation_time_ns: number
  temperature_k: number
  force_field: string
  water_model: string
  estimated_atom_count: number | null
  constraint_algorithm?: string
  constraints?: string
  coulombtype?: string
  cutoff_scheme?: string
  rcoulomb_nm?: number
  rvdw_nm?: number
}

interface Stability {
  rmsd_equilibrated_nm: number | null
  rmsd_final_nm: number | null
  rmsd_drift_nm: number | null
  mean_rmsf_nm: number | null
  is_stable: boolean
}

interface Compactness {
  radius_of_gyration_initial_nm: number | null
  radius_of_gyration_final_nm: number | null
  rg_change_nm: number | null
  sasa_initial_nm2: number | null
  sasa_final_nm2: number | null
}

interface Energetics {
  potential_energy_kjmol: number | null
  kinetic_energy_kjmol: number | null
  total_energy_kjmol: number | null
}

interface FlexibleRegion {
  residues: string
  mean_rmsf_nm: number
  interpretation: string
}

interface StructurePreparation {
  version?: number
  counts?: Record<string, number>
  risk_flags?: string[]
  warnings?: string[]
  hetero_residue_counts?: Record<string, number>
  ion_counts?: Record<string, number>
  cofactor_counts?: Record<string, number>
  histidine_count?: number
  cysteine_count?: number
  alternate_locations?: string[]
}

interface ReplicateConsistency {
  version?: number
  status?: string
  ranking_allowed?: boolean
  minimum_replicates?: number
  group_count?: number
  warnings?: string[]
  recommended_next_steps?: string[]
  quality_gates?: Array<{
    metric: string
    status: string
    value: number | null
    limit: number | string | null
  }>
  groups?: Array<{
    variant: string
    replicate_count: number
    status: string
    stable_agreement?: boolean | null
    metrics?: Record<string, {
      count?: number
      mean?: number | null
      sd?: number | null
      cv?: number | null
      min?: number | null
      max?: number | null
      values?: number[]
    }>
  }>
}

interface ReplicateExecutionPlan {
  version?: number
  status?: string
  protocol_id?: string | null
  replicate_count?: number
  variant_count?: number
  total_tasks?: number
  variants?: string[]
  warnings?: string[]
  tasks?: Array<{
    task_id: string
    variant: string
    replicate_index: number
    seed: number
    status: string
    requires_mutant_structure?: boolean
  }>
}

interface BatchReplicateSummary {
  version?: number
  status?: string
  ranking_allowed?: boolean
  minimum_replicates?: number
  candidate_count?: number
  candidates?: Array<{
    variant: string
    replicate_count: number
    ranking_score?: number | null
    ranking_ready?: boolean
    lipase_evidence?: LipaseEvidenceSummary
    stability_delta?: { mean?: number | null; sd?: number | null; cv?: number | null }
    rmsf_change_mean?: { mean?: number | null; sd?: number | null; cv?: number | null }
    rmsd_drift_nm?: { mean?: number | null; sd?: number | null; cv?: number | null }
  }>
  ranked_candidates?: Array<{
    variant: string
    replicate_count: number
    ranking_score?: number | null
    ranking_ready?: boolean
    lipase_evidence?: LipaseEvidenceSummary
  }>
  replicate_consistency?: ReplicateConsistency
  recommended_next_steps?: string[]
}

interface LipaseEvidenceSummary {
  source?: string
  exact_match_count?: number
  position_match_count?: number
  matches?: Array<Record<string, unknown>>
  interpretation?: string
}

interface TopologyReview {
  version?: number
  warning_count?: number
  risk_flags?: string[]
  warnings?: string[]
  entries?: Array<{
    file?: string
    line?: string
    message?: string
  }>
}

interface MDInterpretation {
  verdict?: string
  confidence?: string
  evidence_level?: string
  conclusion?: string
  findings?: string[]
  warnings?: string[]
  recommended_next_steps?: string[]
  quality_gates?: Array<{
    metric: string
    status: string
    value: number | null
    limit: number | null
  }>
  missing_evidence?: Array<{ metric: string; reason: string }>
  structure_preparation?: StructurePreparation
  replicate_consistency?: ReplicateConsistency
  topology_review?: TopologyReview
  protocol_review?: {
    protocol_id?: string | null
    protocol_label?: string | null
    risk_level?: string
    force_field?: string
    water_model?: string
    ensemble?: string
    review_warnings?: string[]
    requires_expert_review?: boolean
    scientific_controls?: {
      force_field_rationale?: string
      water_model_rationale?: string
      system_preparation_checks?: string[]
      replicate_policy?: {
        recommended_replicates?: number
        minimum_for_ranking?: number
        note?: string
      }
      cutoff_policy?: Record<string, string | number | boolean>
      constraint_policy?: Record<string, string | number | boolean>
    }
  }
}

interface MDResult {
  simulation_parameters: SimulationParams
  structural_stability: Stability
  compactness: Compactness
  interactions: { intra_protein_hbonds: number | null; protein_solvent_hbonds: number | null }
  energetics: Energetics
  flexible_regions: FlexibleRegion[]
  structure_preparation?: StructurePreparation
  replicate_consistency?: ReplicateConsistency
  topology_review?: TopologyReview
  interpretation?: MDInterpretation
  note?: string
}

interface MutantResult {
  mutation: string
  stability_delta: number
  rmsf_change_mean: number
  stable: boolean
}

export interface MDResultData {
  status?: string
  error?: string
  error_code?: string
  required_runtime?: string[]
  is_real_md?: boolean
  wild_type?: MDResult
  mutants?: MutantResult[] | null
  engine?: string
  ensemble?: string
  pressure_bar?: number
  salt_concentration_m?: number
  artifacts?: MDArtifact[]
  artifact_manifest?: ArtifactManifest
  replicate_consistency?: ReplicateConsistency
  replicate_execution_plan?: ReplicateExecutionPlan
  batch_replicate_summary?: BatchReplicateSummary
  topology_review?: TopologyReview
  note?: string
}

interface MDArtifact {
  name?: string
  size?: number
  object_name?: string
  download_url?: string
  category?: string
}

interface ArtifactManifest {
  version?: number
  total_count?: number
  total_size?: number
  groups?: Record<string, MDArtifact[]>
  counts?: Record<string, number>
}

const ARTIFACT_LABELS: Record<string, string> = {
  structures: 'Structures',
  topology: 'Topology',
  trajectory: 'Trajectory',
  analysis: 'Analysis',
  parameters: 'Parameters',
  logs: 'Logs',
  other: 'Other',
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
}

function displayMetric(value: number | null | undefined, unit: string, digits = 2) {
  const formatted = formatNumber(value, digits)
  return formatted === '—' ? formatted : `${formatted} ${unit}`
}

function formatBytes(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function buildFallbackGroups(artifacts: MDArtifact[] | undefined): Record<string, MDArtifact[]> {
  if (!artifacts?.length) return {}
  return artifacts.reduce<Record<string, MDArtifact[]>>((acc, artifact) => {
    const key = artifact.category || 'other'
    acc[key] = [...(acc[key] || []), artifact]
    return acc
  }, {})
}

function ArtifactManifestSection({ data }: { data: MDResultData }) {
  const groups = data.artifact_manifest?.groups || buildFallbackGroups(data.artifacts)
  const entries = Object.entries(groups).filter(([, artifacts]) => artifacts.length > 0)
  if (entries.length === 0) return null

  const totalCount = data.artifact_manifest?.total_count ?? data.artifacts?.length ?? entries.reduce((sum, [, artifacts]) => sum + artifacts.length, 0)
  const totalSize = data.artifact_manifest?.total_size ?? data.artifacts?.reduce((sum, artifact) => sum + (artifact.size || 0), 0)

  return (
    <ReportSection title="Artifacts & Reproducibility">
      <ReportPanel className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>{totalCount} files</span>
          <span>•</span>
          <span>{formatBytes(totalSize)}</span>
          {data.artifact_manifest?.version && (
            <>
              <span>•</span>
              <span>manifest v{data.artifact_manifest.version}</span>
            </>
          )}
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {entries.map(([group, artifacts]) => (
            <div key={group} className="rounded-lg border border-border/70 bg-background/60 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-[0.12em] text-foreground/80">
                  {ARTIFACT_LABELS[group] || group}
                </div>
                <div className="text-[10px] text-muted-foreground">{artifacts.length}</div>
              </div>
              <div className="space-y-2">
                {artifacts.map((artifact, idx) => {
                  const name = artifact.name || artifact.object_name || `artifact-${idx + 1}`
                  return (
                    <div key={`${name}-${idx}`} className="flex items-center gap-2 text-xs">
                      <code className="min-w-0 flex-1 truncate rounded bg-secondary/60 px-2 py-1 font-mono text-[11px]">
                        {name}
                      </code>
                      <span className="shrink-0 text-[10px] text-muted-foreground">{formatBytes(artifact.size)}</span>
                      {artifact.download_url && (
                        <a
                          href={artifact.download_url}
                          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-border/70 px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
                          title={`Download ${name}`}
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>Download</span>
                        </a>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </ReportPanel>
    </ReportSection>
  )
}

function StabilityGauge({ drift, isStable }: { drift: number | null | undefined; isStable: boolean }) {
  const safeDrift = typeof drift === 'number' && Number.isFinite(drift) ? drift : 0
  const pct = Math.min(100, Math.max(0, (1 - safeDrift / 0.5) * 100))
  const color = safeDrift < 0.15 ? '#34d399' : safeDrift < 0.3 ? '#fbbf24' : '#f87171'
  const label = typeof drift === 'number' && Number.isFinite(drift) ? drift.toFixed(2) : '—'

  return (
    <div className="flex items-center gap-4">
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r="24" fill="none" stroke="currentColor" strokeWidth="4" className="text-secondary" />
        <circle
          cx="28"
          cy="28"
          r="24"
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeDasharray={`${pct * 1.51} ${151 - pct * 1.51}`}
          strokeLinecap="round"
          transform="rotate(-90 28 28)"
        />
        <text x="28" y="31" textAnchor="middle" fontSize="11" fontWeight="700" fill="currentColor" className="fill-foreground">
          {label}
        </text>
      </svg>
      <div>
        <div className="flex items-center gap-1.5">
          {isStable ? (
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
          ) : (
            <ShieldAlert className="h-4 w-4 text-red-500" />
          )}
          <span className={`text-sm font-semibold ${isStable ? 'text-emerald-500' : 'text-red-500'}`}>
            {isStable ? 'Stable' : 'Unstable'}
          </span>
        </div>
        <p className="mt-1 text-[10px] text-muted-foreground">RMSD drift {label} nm</p>
      </div>
    </div>
  )
}

function MetricCard({ label, value, unit, delta }: { label: string; value: number | null | undefined; unit: string; delta?: number | null }) {
  const hasDelta = typeof delta === 'number' && Number.isFinite(delta) && delta !== 0
  return (
    <ReportMetricCard
      label={label}
      value={displayMetric(value, unit)}
      meta={
        hasDelta ? (
          <span className={`inline-flex items-center gap-1 ${delta > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
            {delta > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {delta > 0 ? '+' : ''}
            {formatNumber(delta)}
          </span>
        ) : undefined
      }
      mono
    />
  )
}

function StructurePreparationPanel({ preparation }: { preparation?: StructurePreparation }) {
  if (!preparation) return null
  const risks = preparation.risk_flags || []
  const warnings = preparation.warnings || []
  const counts = preparation.counts || {}
  const residueEntries = [
    ...Object.entries(preparation.cofactor_counts || {}).map(([name, count]) => [`cofactor:${name}`, count] as const),
    ...Object.entries(preparation.ion_counts || {}).map(([name, count]) => [`ion:${name}`, count] as const),
    ...Object.entries(preparation.hetero_residue_counts || {}).map(([name, count]) => [`het:${name}`, count] as const),
  ].slice(0, 12)

  return (
    <div className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">Structure Preparation</span>
        {risks.length > 0 ? (
          <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600">{risks.length} review flags</span>
        ) : (
          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600">no parser flags</span>
        )}
      </div>
      <div className="grid gap-2 sm:grid-cols-4">
        <div className="rounded-md bg-secondary/50 px-2 py-1.5 text-muted-foreground">HETATM <span className="font-mono text-foreground">{counts.hetatm ?? 0}</span></div>
        <div className="rounded-md bg-secondary/50 px-2 py-1.5 text-muted-foreground">Non-water <span className="font-mono text-foreground">{counts.non_water_hetatm_atoms ?? 0}</span></div>
        <div className="rounded-md bg-secondary/50 px-2 py-1.5 text-muted-foreground">HIS <span className="font-mono text-foreground">{preparation.histidine_count ?? 0}</span></div>
        <div className="rounded-md bg-secondary/50 px-2 py-1.5 text-muted-foreground">CYS <span className="font-mono text-foreground">{preparation.cysteine_count ?? 0}</span></div>
      </div>
      {risks.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {risks.map((risk) => (
            <code key={risk} className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
              {risk}
            </code>
          ))}
        </div>
      )}
      {residueEntries.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {residueEntries.map(([name, count]) => (
            <div key={name} className="rounded-md bg-background/70 px-2 py-1.5 text-muted-foreground">
              <code className="text-foreground">{name}</code> · {count}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {warnings.map((warning) => (
            <div key={warning} className="flex gap-2 leading-5 text-amber-600 dark:text-amber-300">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ReplicateConsistencyPanel({ consistency }: { consistency?: ReplicateConsistency }) {
  if (!consistency) return null
  const groups = consistency.groups || []
  const warnings = consistency.warnings || []
  const statusTone = consistency.ranking_allowed ? 'text-emerald-600' : consistency.status === 'inconsistent' ? 'text-red-600' : 'text-amber-600'

  return (
    <div className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">Replicate Consistency</span>
        {consistency.status && <span className={`rounded-full bg-secondary px-2 py-0.5 font-medium ${statusTone}`}>{consistency.status}</span>}
        <span className="rounded-full bg-secondary px-2 py-0.5 text-muted-foreground">minimum {consistency.minimum_replicates ?? '—'} replicates</span>
        <span className={`rounded-full px-2 py-0.5 ${consistency.ranking_allowed ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'}`}>
          {consistency.ranking_allowed ? 'ranking allowed' : 'ranking blocked'}
        </span>
      </div>
      {groups.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {groups.map((group) => {
            const rmsd = group.metrics?.rmsd_drift_nm
            const rmsf = group.metrics?.mean_rmsf_nm
            return (
              <div key={group.variant} className="rounded-md bg-secondary/40 p-2">
                <div className="flex items-center justify-between gap-2">
                  <code className="font-mono text-[11px] text-foreground">{group.variant}</code>
                  <span className="text-muted-foreground">{group.replicate_count} reps · {group.status}</span>
                </div>
                <div className="mt-1 grid gap-1 text-muted-foreground">
                  <div>RMSD drift mean {formatNumber(rmsd?.mean, 3)} · CV {formatNumber(rmsd?.cv, 3)}</div>
                  <div>Mean RMSF {formatNumber(rmsf?.mean, 3)} · CV {formatNumber(rmsf?.cv, 3)}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {warnings.map((warning) => (
            <div key={warning} className="flex gap-2 leading-5 text-amber-600 dark:text-amber-300">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function BatchReplicateSummaryPanel({ summary, plan }: { summary?: BatchReplicateSummary; plan?: ReplicateExecutionPlan }) {
  if (!summary && !plan) return null
  const ranked = summary?.ranked_candidates || []
  const candidates = summary?.candidates || []
  const warnings = plan?.warnings || summary?.replicate_consistency?.warnings || []
  const statusTone = summary?.ranking_allowed ? 'text-emerald-600' : 'text-amber-600'

  return (
    <ReportSection title="Batch Replicate Review">
      <ReportPanel className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {summary?.status && <span className={`rounded-full bg-secondary px-2.5 py-1 font-semibold ${statusTone}`}>{summary.status}</span>}
          {typeof summary?.minimum_replicates === 'number' && <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">minimum {summary.minimum_replicates} reps</span>}
          {typeof plan?.total_tasks === 'number' && <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">{plan.total_tasks} planned tasks</span>}
          {plan?.protocol_id && <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">{plan.protocol_id}</span>}
        </div>

        {ranked.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {ranked.slice(0, 6).map((candidate, index) => (
              <div key={candidate.variant} className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <code className="font-mono text-[11px] text-foreground">#{index + 1} {candidate.variant}</code>
                  <span className="font-mono text-emerald-600">{formatNumber(candidate.ranking_score, 3)}</span>
                </div>
                <div className="mt-1 text-muted-foreground">{candidate.replicate_count} replicates · ranking ready</div>
                <LipaseEvidenceBadge evidence={candidate.lipase_evidence} />
              </div>
            ))}
          </div>
        )}

        {ranked.length === 0 && candidates.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {candidates.slice(0, 6).map((candidate) => (
              <div key={candidate.variant} className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <code className="font-mono text-[11px] text-foreground">{candidate.variant}</code>
                  <span className="text-muted-foreground">{candidate.replicate_count} reps</span>
                </div>
                <div className="mt-1 grid gap-1 text-muted-foreground">
                  <div>Δ stability mean {formatNumber(candidate.stability_delta?.mean, 3)}</div>
                  <div>Δ RMSF mean {formatNumber(candidate.rmsf_change_mean?.mean, 3)}</div>
                </div>
                <LipaseEvidenceBadge evidence={candidate.lipase_evidence} />
              </div>
            ))}
          </div>
        )}

        {plan?.tasks && plan.tasks.length > 0 && (
          <div className="rounded-lg bg-secondary/30 p-3 text-xs">
            <div className="mb-2 font-semibold text-foreground">Execution Plan Preview</div>
            <div className="grid gap-1 sm:grid-cols-2">
              {plan.tasks.slice(0, 8).map((task) => (
                <div key={task.task_id} className="flex items-center justify-between gap-3 text-muted-foreground">
                  <code className="text-[11px] text-foreground">{task.task_id}</code>
                  <span>seed {task.seed}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {warnings.length > 0 && (
          <div className="space-y-1.5 text-xs">
            {warnings.map((warning) => (
              <div key={warning} className="flex gap-2 leading-5 text-amber-600 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        )}
      </ReportPanel>
    </ReportSection>
  )
}

function LipaseEvidenceBadge({ evidence }: { evidence?: LipaseEvidenceSummary }) {
  if (!evidence) return null
  const exact = evidence.exact_match_count || 0
  const positional = evidence.position_match_count || 0
  if (!exact && !positional) {
    return (
      <div className="mt-2 rounded-md bg-secondary/50 px-2 py-1.5 text-[10px] leading-4 text-muted-foreground">
        KWB Lipase DB：未找到精确突变证据
      </div>
    )
  }
  return (
    <div className="mt-2 rounded-md border border-emerald-500/15 bg-emerald-500/5 px-2 py-1.5 text-[10px] leading-4 text-emerald-700 dark:text-emerald-300">
      KWB Lipase DB：exact {exact} · position {positional}
    </div>
  )
}

function TopologyReviewPanel({ review }: { review?: TopologyReview }) {
  if (!review) return null
  const flags = review.risk_flags || []
  const warnings = review.warnings || []
  const entries = (review.entries || []).slice(0, 6)
  const count = review.warning_count ?? entries.length

  return (
    <div className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">Topology Review</span>
        {count > 0 ? (
          <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600">{count} warnings</span>
        ) : (
          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600">no warnings parsed</span>
        )}
      </div>
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {flags.map((flag) => (
            <code key={flag} className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
              {flag}
            </code>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {warnings.map((warning) => (
            <div key={warning} className="flex gap-2 leading-5 text-amber-600 dark:text-amber-300">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
      {entries.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {entries.map((entry, idx) => (
            <div key={`${entry.file}-${entry.line}-${idx}`} className="rounded-md bg-secondary/40 px-2 py-1.5 text-muted-foreground">
              <code className="text-foreground">{entry.file || 'log'}</code>
              {entry.line && <span>:{entry.line}</span>}
              <div className="mt-1 leading-5">{entry.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function InterpretationPanel({ interpretation }: { interpretation?: MDInterpretation }) {
  if (!interpretation) return null
  const gateTone = (status: string) => {
    if (status === 'pass') return 'text-emerald-500'
    if (status === 'fail') return 'text-red-500'
    if (status === 'missing') return 'text-muted-foreground'
    return 'text-amber-500'
  }

  return (
    <ReportSection title="Interpretation & Review">
      <ReportPanel className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {interpretation.verdict && <span className="rounded-full bg-secondary px-2.5 py-1 font-semibold text-foreground">{interpretation.verdict}</span>}
          {interpretation.confidence && <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">confidence: {interpretation.confidence}</span>}
          {interpretation.evidence_level && <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">evidence: {interpretation.evidence_level}</span>}
        </div>
        {interpretation.conclusion && (
          <p className="text-sm leading-6 text-foreground">{interpretation.conclusion}</p>
        )}
        <StructurePreparationPanel preparation={interpretation.structure_preparation} />
        <ReplicateConsistencyPanel consistency={interpretation.replicate_consistency} />
        <TopologyReviewPanel review={interpretation.topology_review} />
        {interpretation.quality_gates && interpretation.quality_gates.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {interpretation.quality_gates.map((gate) => (
              <div key={`${gate.metric}-${gate.status}`} className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <code className="font-mono text-[11px] text-foreground">{gate.metric}</code>
                  <span className={`font-semibold uppercase tracking-[0.12em] ${gateTone(gate.status)}`}>{gate.status}</span>
                </div>
                <div className="mt-1 text-muted-foreground">
                  value {gate.value == null ? '—' : gate.value} · limit {gate.limit}
                </div>
              </div>
            ))}
          </div>
        )}
        {interpretation.protocol_review && (
          <div className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="font-semibold text-foreground">Protocol Review</span>
              {interpretation.protocol_review.protocol_label && <span className="rounded-full bg-secondary px-2 py-0.5 text-muted-foreground">{interpretation.protocol_review.protocol_label}</span>}
              {interpretation.protocol_review.risk_level && <span className="rounded-full bg-secondary px-2 py-0.5 text-muted-foreground">{interpretation.protocol_review.risk_level}</span>}
              {interpretation.protocol_review.requires_expert_review && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600">expert review</span>}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="text-muted-foreground">
                Force field: <span className="font-mono text-foreground">{interpretation.protocol_review.force_field || '—'}</span>
              </div>
              <div className="text-muted-foreground">
                Water model: <span className="font-mono text-foreground">{interpretation.protocol_review.water_model || '—'}</span>
              </div>
            </div>
            {interpretation.protocol_review.scientific_controls?.replicate_policy && (
              <div className="mt-2 text-muted-foreground">
                Replicates: recommended {interpretation.protocol_review.scientific_controls.replicate_policy.recommended_replicates ?? '—'} · ranking minimum {interpretation.protocol_review.scientific_controls.replicate_policy.minimum_for_ranking ?? '—'}
              </div>
            )}
            {interpretation.protocol_review.review_warnings && interpretation.protocol_review.review_warnings.length > 0 && (
              <div className="mt-2 space-y-1">
                {interpretation.protocol_review.review_warnings.map((warning) => (
                  <div key={warning} className="text-amber-600 dark:text-amber-300">{warning}</div>
                ))}
              </div>
            )}
          </div>
        )}
        {interpretation.warnings && interpretation.warnings.length > 0 && (
          <div className="space-y-2">
            {interpretation.warnings.map((warning) => (
              <div key={warning} className="flex gap-2 text-xs leading-5 text-amber-600 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        )}
        {interpretation.missing_evidence && interpretation.missing_evidence.length > 0 && (
          <div className="rounded-lg border border-dashed border-amber-400/40 bg-amber-500/5 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-amber-600 dark:text-amber-300">Missing Evidence</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {interpretation.missing_evidence.map((item) => (
                <div key={`${item.metric}-${item.reason}`} className="rounded-md bg-background/70 px-3 py-2 text-xs">
                  <code className="text-foreground">{item.metric}</code>
                  <div className="mt-1 text-muted-foreground">{item.reason}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {interpretation.recommended_next_steps && interpretation.recommended_next_steps.length > 0 && (
          <div className="space-y-2">
            {interpretation.recommended_next_steps.map((step) => (
              <div key={step} className="text-xs leading-5 text-muted-foreground">• {step}</div>
            ))}
          </div>
        )}
      </ReportPanel>
    </ReportSection>
  )
}

function EnergyBar({ label, value, max, color }: { label: string; value: number | null | undefined; max: number; color: string }) {
  const safeValue = typeof value === 'number' && Number.isFinite(value) ? value : 0
  const pct = Math.min(100, (Math.abs(safeValue) / max) * 100)
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 shrink-0 text-right text-[10px] text-muted-foreground">{label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-secondary">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right font-mono text-[10px] font-medium">{formatNumber(value, 0)}</span>
    </div>
  )
}

export function MDResultView({ data, taskId }: { data: MDResultData; taskId?: string | null }) {
  if (data.status === 'failed') {
    return (
      <ReportShell>
        <ReportHeader
          icon={AlertTriangle}
          title="MD Simulation Unavailable"
          subtitle={data.is_real_md ? 'Real GROMACS workflow started but failed' : 'Real GROMACS workflow not available in current runtime'}
        />
        <ReportBody>
          <ReportSection title="Failure Details">
            <ReportPanel className="space-y-3">
              <p className="text-sm font-medium text-red-500">{data.error_code || 'MD_FAILED'}</p>
              <p className="text-sm leading-6 text-muted-foreground">{data.error || 'Unknown MD error'}</p>
              {data.note && <p className="text-xs leading-6 text-muted-foreground">{data.note}</p>}
            </ReportPanel>
          </ReportSection>
          {data.required_runtime && data.required_runtime.length > 0 && (
            <ReportSection title="Required Runtime">
              <ReportPanel>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {data.required_runtime.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </ReportPanel>
            </ReportSection>
          )}
          <ArtifactManifestSection data={data} />
        </ReportBody>
      </ReportShell>
    )
  }

  if (data.status === 'planned' || data.replicate_execution_plan || data.batch_replicate_summary) {
    return (
      <ReportShell>
        <ReportHeader
          icon={Activity}
          title="MD Replicate Plan"
          subtitle={data.note || 'Multi-replicate execution plan; no GROMACS command was executed'}
        />
        <ReportBody>
          <BatchReplicateSummaryPanel summary={data.batch_replicate_summary} plan={data.replicate_execution_plan} />
          {data.replicate_consistency && (
            <ReportSection title="Replicate Consistency">
              <ReportPanel>
                <ReplicateConsistencyPanel consistency={data.replicate_consistency} />
              </ReportPanel>
            </ReportSection>
          )}
        </ReportBody>
      </ReportShell>
    )
  }

  const { wild_type: wt, mutants, engine, ensemble, pressure_bar } = data
  if (!wt) return null
  const { simulation_parameters: p, structural_stability: s, compactness: c, interactions: i, energetics: e, flexible_regions } = wt

  const maxEnergy = Math.max(
    Math.abs(e.potential_energy_kjmol ?? 0),
    Math.abs(e.kinetic_energy_kjmol ?? 0),
    Math.abs(e.total_energy_kjmol ?? 0),
    1
  )
  const subtitleParts = [
    engine || 'GROMACS',
    ensemble || 'MD',
    p.simulation_time_ns ? `${p.simulation_time_ns} ns` : null,
    p.temperature_k ? `${p.temperature_k} K` : null,
    p.force_field && p.water_model ? `${p.force_field}/${p.water_model}` : null,
    pressure_bar ? `${pressure_bar} bar` : null,
    p.estimated_atom_count ? `${p.estimated_atom_count} atoms` : null,
  ].filter(Boolean)
  const totalArtifactCount = data.artifact_manifest?.total_count ?? data.artifacts?.length ?? 0
  const bundleDownloadUrl = taskId ? buildToolTaskArtifactBundleUrl(taskId) : null

  return (
    <ReportShell>
      <ReportHeader
        icon={Activity}
        title="MD Simulation Results"
        subtitle={subtitleParts.join(' · ')}
        actions={
          <>
            {bundleDownloadUrl && totalArtifactCount > 0 ? (
              <a
                href={bundleDownloadUrl}
                className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground"
                title={`Download all ${totalArtifactCount} artifacts (.zip)`}
              >
                <Download className="w-3.5 h-3.5" />
              </a>
            ) : (
              <button onClick={() => downloadReport('md', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Download HTML report">
                <Download className="w-3.5 h-3.5" />
              </button>
            )}
            <button onClick={() => printReport('md', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Print report">
              <Printer className="w-3.5 h-3.5" />
            </button>
          </>
        }
      />
      <ReportBody>
        <ReportSection title="Stability Overview">
          <ReportPanel>
            <StabilityGauge drift={s.rmsd_drift_nm} isStable={s.is_stable} />
          </ReportPanel>
        </ReportSection>

        <InterpretationPanel interpretation={wt.interpretation} />
        <BatchReplicateSummaryPanel summary={data.batch_replicate_summary} plan={data.replicate_execution_plan} />

        <ReportSection title="Structural Stability">
          <ReportMetricGrid>
            <MetricCard label="RMSD Final" value={s.rmsd_final_nm} unit="nm" />
            <MetricCard label="RMSD Drift" value={s.rmsd_drift_nm} unit="nm" />
            <MetricCard label="Mean RMSF" value={s.mean_rmsf_nm} unit="nm" />
            <MetricCard label="Equilibrated" value={s.rmsd_equilibrated_nm} unit="nm" />
          </ReportMetricGrid>
        </ReportSection>

        <ReportSection title="Compactness & Solvation">
          <ReportMetricGrid>
            <MetricCard label="Rg Initial" value={c.radius_of_gyration_initial_nm} unit="nm" />
            <MetricCard label="Rg Final" value={c.radius_of_gyration_final_nm} unit="nm" delta={c.rg_change_nm} />
            <MetricCard label="SASA Initial" value={c.sasa_initial_nm2} unit="nm²" />
            <MetricCard label="SASA Final" value={c.sasa_final_nm2} unit="nm²" />
          </ReportMetricGrid>
        </ReportSection>

        <ReportSection title="Energetics" icon={Zap}>
          <ReportPanel className="space-y-3">
            <EnergyBar label="Potential" value={e.potential_energy_kjmol} max={maxEnergy} color="bg-blue-400" />
            <EnergyBar label="Kinetic" value={e.kinetic_energy_kjmol} max={maxEnergy} color="bg-amber-400" />
            <EnergyBar label="Total" value={e.total_energy_kjmol} max={maxEnergy} color="bg-fuchsia-400" />
          </ReportPanel>
        </ReportSection>

        <ReportSection title="Hydrogen Bonds">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ReportMetricCard label="Intra-protein H-bonds" value={formatNumber(i.intra_protein_hbonds, 0)} mono />
            <ReportMetricCard label="Protein-Solvent H-bonds" value={formatNumber(i.protein_solvent_hbonds, 0)} mono />
          </div>
        </ReportSection>

        {flexible_regions.length > 0 && (
          <ReportSection title="Flexible Regions">
            <div className="space-y-2">
              {flexible_regions.map((fr, idx) => (
                <ReportPanel key={idx} className="flex items-center gap-2">
                  <Circle className={`h-2.5 w-2.5 ${fr.mean_rmsf_nm > 0.4 ? 'fill-red-500 text-red-500' : 'fill-amber-500 text-amber-500'}`} />
                  <code className="font-mono text-[11px] font-medium">{fr.residues}</code>
                  <span className="text-[10px] text-muted-foreground">RMSF {displayMetric(fr.mean_rmsf_nm, 'nm')}</span>
                  <div className="flex-1" />
                  <span className="text-[10px] text-muted-foreground">{fr.interpretation}</span>
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}

        {mutants && mutants.length > 0 && (
          <ReportSection title="Mutant Comparison">
            <ReportDataTable>
              <thead>
                <tr>
                  <th className="border-b border-border/80 bg-secondary/60 px-3 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.12em] text-foreground/90">
                    Mutation
                  </th>
                  <th className="border-b border-border/80 bg-secondary/60 px-3 py-3 text-right text-[12px] font-semibold uppercase tracking-[0.12em] text-foreground/90">
                    ΔΔG (kJ/mol)
                  </th>
                  <th className="border-b border-border/80 bg-secondary/60 px-3 py-3 text-right text-[12px] font-semibold uppercase tracking-[0.12em] text-foreground/90">
                    ΔRMSF (nm)
                  </th>
                  <th className="border-b border-border/80 bg-secondary/60 px-3 py-3 text-center text-[12px] font-semibold uppercase tracking-[0.12em] text-foreground/90">
                    Stable
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/50">
                  <td className="px-3 py-3 font-mono text-[13px] font-medium">WT</td>
                  <td className="px-3 py-3 text-right text-[13px] text-muted-foreground">—</td>
                  <td className="px-3 py-3 text-right text-[13px] text-muted-foreground">—</td>
                  <td className="px-3 py-3 text-center">
                    <ShieldCheck className="mx-auto h-3.5 w-3.5 text-emerald-500" />
                  </td>
                </tr>
                {mutants.map((m, idx) => (
                  <tr key={idx} className="border-b border-border/30">
                    <td className="px-3 py-3 font-mono text-[13px] font-medium">{m.mutation}</td>
                    <td className={`px-3 py-3 text-right font-mono text-[13px] ${m.stability_delta > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                      {m.stability_delta > 0 ? '+' : ''}
                      {m.stability_delta.toFixed(2)}
                    </td>
                    <td className={`px-3 py-3 text-right font-mono text-[13px] ${m.rmsf_change_mean > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                      {m.rmsf_change_mean > 0 ? '+' : ''}
                      {m.rmsf_change_mean.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {m.stable ? (
                        <ShieldCheck className="mx-auto h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <ShieldAlert className="mx-auto h-3.5 w-3.5 text-red-500" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </ReportDataTable>
          </ReportSection>
        )}

        <ArtifactManifestSection data={data} />
      </ReportBody>
    </ReportShell>
  )
}
