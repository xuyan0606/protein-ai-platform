import { ShieldAlert, ShieldCheck, ShieldX, TrendingUp, Target, Download, Printer } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'

interface DimensionScores {
  surface_exposure?: number
  active_site_distance?: number
  conservation?: number
  functional_relevance?: number
  ddg_prediction?: number
}

interface Candidate {
  position: number
  wild_type: string
  composite_priority: number
  recommended_mutations: string | string[]
  target_type?: string
  dimension_scores?: DimensionScores
  categories?: string[]
  detailed_rationale?: string
}

interface MutationScoreData {
  sequence_length: number
  sequence_preview?: string
  engineering_goal: string
  target_ph?: number
  target_tm?: number
  active_site_positions: number[]
  summary: {
    total_positions: number
    tier_1_count: number
    tier_2_count: number
    tier_3_count: number
    never_mutate_count: number
    never_mutate_positions: number[]
  }
  tier_1_candidates: Candidate[]
  tier_2_candidates: Candidate[]
  all_positions?: Candidate[]
}

const DIMENSION_LABELS: Record<string, string> = {
  surface_exposure: 'Surface Exposure',
  active_site_distance: 'Distance from Active Site',
  conservation: 'Conservation',
  functional_relevance: 'Functional Relevance',
  ddg_prediction: 'ΔΔG Prediction',
}

const DIMENSION_COLORS: Record<string, string> = {
  surface_exposure: 'bg-blue-400',
  active_site_distance: 'bg-purple-400',
  conservation: 'bg-emerald-400',
  functional_relevance: 'bg-amber-400',
  ddg_prediction: 'bg-rose-400',
}

const GOAL_LABELS: Record<string, string> = {
  ph_lowering: 'pH Lowering',
  thermostability: 'Thermostability',
  solubility: 'Solubility',
  general: 'General Engineering',
}

function TierBadge({ tier }: { tier: number }) {
  const map = {
    1: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    2: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    3: 'bg-muted text-muted-foreground border-border',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${map[tier as keyof typeof map]}`}>
      T{tier}
    </span>
  )
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
      <div
        className={`h-full ${color} rounded-full transition-all`}
        style={{ width: `${Math.min(100, value * 10)}%` }}
      />
    </div>
  )
}

export function MutationScoreCard({ data }: { data: MutationScoreData }) {
  const { summary, tier_1_candidates, tier_2_candidates, engineering_goal, active_site_positions } = data

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-primary" />
            <h3 className="font-semibold">Mutation Priority Score</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            {GOAL_LABELS[engineering_goal] || engineering_goal} · {summary.total_positions} positions scanned
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => downloadReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Download HTML report">
            <Download className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => printReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Print report">
            <Printer className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Summary Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] text-muted-foreground">Tier 1</span>
          </div>
          <div className="text-lg font-bold text-emerald-400">{summary.tier_1_count}</div>
          <div className="text-[9px] text-muted-foreground">Priority &gt; 7.0</div>
        </div>
        <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[10px] text-muted-foreground">Tier 2</span>
          </div>
          <div className="text-lg font-bold text-amber-400">{summary.tier_2_count}</div>
          <div className="text-[9px] text-muted-foreground">Priority 5.0-7.0</div>
        </div>
        <div className="bg-muted/30 border border-border rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] text-muted-foreground">Tier 3</span>
          </div>
          <div className="text-lg font-bold text-muted-foreground">{summary.tier_3_count}</div>
          <div className="text-[9px] text-muted-foreground">Low Priority</div>
        </div>
        <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldX className="w-3.5 h-3.5 text-red-400" />
            <span className="text-[10px] text-muted-foreground">Never Mutate</span>
          </div>
          <div className="text-lg font-bold text-red-400">{summary.never_mutate_count}</div>
          <div className="text-[9px] text-red-400/70">Catalytic/Essential</div>
        </div>
      </div>

      {/* Active site positions */}
      {active_site_positions.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Active site positions:{' '}
          {active_site_positions.map((p) => (
            <code key={p} className="text-[10px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded font-mono ml-1">{p}</code>
          ))}
        </div>
      )}

      {/* Tier 1 Candidates */}
      {tier_1_candidates.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
            <TrendingUp className="w-3 h-3 text-emerald-400" />
            Tier 1 — High Priority Candidates
          </h4>
          <div className="space-y-2">
            {tier_1_candidates.map((c) => (
              <MutationRow key={c.position} candidate={c} tier={1} />
            ))}
          </div>
        </div>
      )}

      {/* Tier 2 Candidates */}
      {tier_2_candidates.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-4">
            Tier 2 — Moderate Priority
          </h4>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {tier_2_candidates.map((c) => (
              <MutationRow key={c.position} candidate={c} tier={2} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MutationRow({ candidate: c, tier }: { candidate: Candidate; tier: number }) {
  const muts = Array.isArray(c.recommended_mutations) ? c.recommended_mutations : [c.recommended_mutations]

  return (
    <div className="bg-secondary/30 border border-border rounded-lg p-3">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <TierBadge tier={tier} />
          <code className="text-sm font-bold font-mono">{c.wild_type}{c.position}</code>
          <span className="text-[10px] text-muted-foreground">{c.target_type?.replace(/_/g, ' ') || ''}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground">Score</span>
          <span className={`text-sm font-bold font-mono ${tier === 1 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {c.composite_priority.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Dimension scores */}
      {c.dimension_scores && (
        <div className="space-y-1 mb-2">
          {Object.entries(c.dimension_scores).map(([key, val]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground w-24 shrink-0 truncate">
                {DIMENSION_LABELS[key] || key}
              </span>
              <ScoreBar value={val} color={DIMENSION_COLORS[key] || 'bg-muted-foreground'} />
              <span className="text-[10px] font-mono font-medium w-6 text-right">{val.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Mutations */}
      <div className="flex flex-wrap gap-1.5 mt-2">
        {muts.map((m) => (
          <code key={m} className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-md font-mono font-medium">
            {c.wild_type}{c.position}{m}
          </code>
        ))}
      </div>
      {c.detailed_rationale && (
        <p className="text-[10px] text-muted-foreground mt-1.5">{c.detailed_rationale}</p>
      )}
    </div>
  )
}

export function isMutationScoreResult(data: unknown): data is MutationScoreData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'tier_1_candidates' in d && 'tier_2_candidates' in d && 'summary' in d
}
