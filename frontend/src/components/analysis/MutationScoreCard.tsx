import { ShieldAlert, ShieldCheck, ShieldX, TrendingUp, Target, Download, Printer, Zap } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'

interface RecommendedMutation {
  mutation: string
  type: string
  purpose: string
}

interface Candidate {
  position: number
  wild_type: string
  composite_priority: number
  tier: number
  mutation_type?: string | null
  logic: string
  recommended_mutations: RecommendedMutation[]
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

const GOAL_LABELS: Record<string, string> = {
  ph_lowering: 'pH降低改造',
  ph_raising: 'pH升高改造',
  thermostability: '热稳定性改造',
  activity: '活性改造',
  specificity: '底物特异性改造',
  general: '通用改造',
}

const TYPE_COLORS: Record<string, string> = {
  '表面电荷翻转': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  '活性中心电荷中和': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  '增加loop刚性': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  '表面电荷优化': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  'loop稳定性': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
}

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] || 'bg-muted text-muted-foreground border-border'
}

function TierBadge({ tier }: { tier: number }) {
  const map: Record<number, string> = {
    1: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    2: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    3: 'bg-muted text-muted-foreground border-border',
  }
  const labels: Record<number, string> = { 1: '优先', 2: '可选', 3: '保守' }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${map[tier] || map[3]}`}>
      {labels[tier] || `T${tier}`}
    </span>
  )
}

export function MutationScoreCard({ data }: { data: MutationScoreData }) {
  const { summary, tier_1_candidates, tier_2_candidates, engineering_goal, active_site_positions, target_ph, target_tm } = data

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-primary" />
            <h3 className="font-semibold">突变优先级分析</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            {GOAL_LABELS[engineering_goal] || engineering_goal}
            {target_ph != null && ` · 目标pH ${target_ph}`}
            {target_tm != null && ` · 目标Tm ${target_tm}°C`}
            {' · '}扫描 {summary.total_positions} 个位点
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => downloadReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="下载报告">
            <Download className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => printReport('mutation_score', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="打印报告">
            <Printer className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Summary Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] text-muted-foreground">优先改造</span>
          </div>
          <div className="text-lg font-bold text-emerald-400">{summary.tier_1_count}</div>
          <div className="text-[9px] text-muted-foreground">优先级 &gt; 7.0</div>
        </div>
        <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[10px] text-muted-foreground">可选改造</span>
          </div>
          <div className="text-lg font-bold text-amber-400">{summary.tier_2_count}</div>
          <div className="text-[9px] text-muted-foreground">优先级 5.0-7.0</div>
        </div>
        <div className="bg-muted/30 border border-border rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] text-muted-foreground">低优先</span>
          </div>
          <div className="text-lg font-bold text-muted-foreground">{summary.tier_3_count}</div>
          <div className="text-[9px] text-muted-foreground">优先级 &lt; 5.0</div>
        </div>
        <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldX className="w-3.5 h-3.5 text-red-400" />
            <span className="text-[10px] text-muted-foreground">禁止突变</span>
          </div>
          <div className="text-lg font-bold text-red-400">{summary.never_mutate_count}</div>
          <div className="text-[9px] text-red-400/70">催化/必需残基</div>
        </div>
      </div>

      {/* Active site positions */}
      {active_site_positions.length > 0 && (
        <div className="text-xs text-muted-foreground">
          活性中心位点：
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
            优先改造位点（Tier 1）
          </h4>
          <div className="space-y-2">
            {tier_1_candidates.map((c) => (
              <MutationRow key={c.position} candidate={c} />
            ))}
          </div>
        </div>
      )}

      {/* Tier 2 Candidates */}
      {tier_2_candidates.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 mt-4">
            可选改造位点（Tier 2）
          </h4>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {tier_2_candidates.map((c) => (
              <MutationRow key={c.position} candidate={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MutationRow({ candidate: c }: { candidate: Candidate }) {
  const tier = c.tier
  const scoreColor = tier === 1 ? 'text-emerald-400' : 'text-amber-400'

  return (
    <div className="bg-secondary/30 border border-border rounded-lg p-3">
      {/* Top row: position, type tag, priority */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <TierBadge tier={tier} />
          <code className="text-sm font-bold font-mono">{c.wild_type}{c.position}</code>
          {c.mutation_type && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${getTypeColor(c.mutation_type)}`}>
              {c.mutation_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground">优先级</span>
          <span className={`text-sm font-bold font-mono ${scoreColor}`}>
            {c.composite_priority.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Logic — Chinese engineering rationale */}
      <p className="text-xs text-muted-foreground leading-relaxed mb-2">
        {c.logic}
      </p>

      {/* Recommended mutations with purpose */}
      {c.recommended_mutations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {c.recommended_mutations.map((m) => (
            <div
              key={m.mutation}
              className="group relative"
            >
              <code className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-md font-mono font-medium cursor-default">
                {m.mutation}
              </code>
              {/* Tooltip with purpose */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 bg-popover border border-border rounded-md shadow-lg text-[10px] text-foreground whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                {m.purpose}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function isMutationScoreResult(data: unknown): data is MutationScoreData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'tier_1_candidates' in d && 'tier_2_candidates' in d && 'summary' in d
}
