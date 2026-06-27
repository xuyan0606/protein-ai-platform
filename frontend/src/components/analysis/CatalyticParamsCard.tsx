import { Zap, TrendingUp, Info } from 'lucide-react'

interface CatalyticParamsData {
  predicted_kcat_s1: number
  predicted_log10_kcat: number
  confidence_interval_log10: [number, number]
  confidence_interval_kcat_s1: [number, number]
  enzyme_class: string
  efficiency_assessment: string
  contributing_factors: {
    enzyme_class_baseline: { mean_log_kcat: number; std_log_kcat: number; typical_range: string }
    avg_residue_volume: number
    avg_hydropathy: number
    charge_density: number
    gly_fraction: number
    substrate_complexity: number
    temperature_factor: number
    ph_factor: number
  }
  model: string
  method: string
  is_real_inference?: boolean
  sequence_length: number
  error?: string
}

const CLASS_LABELS: Record<string, string> = {
  hydrolase: '水解酶',
  transferase: '转移酶',
  oxidoreductase: '氧化还原酶',
  lyase: '裂合酶',
  isomerase: '异构酶',
  ligase: '连接酶',
  unknown: '未知类型',
}

function formatKcat(kcat: number): string {
  if (kcat >= 1000) return (kcat / 1000).toFixed(1) + ' × 10³ s⁻¹'
  if (kcat >= 1) return kcat.toFixed(2) + ' s⁻¹'
  if (kcat >= 0.001) return (kcat * 1000).toFixed(2) + ' × 10⁻³ s⁻¹'
  return kcat.toExponential(2) + ' s⁻¹'
}

export function CatalyticParamsCard({ data }: { data: CatalyticParamsData }) {
  const f = data.contributing_factors
  const ci = data.confidence_interval_kcat_s1

  return (
    <div className="space-y-3 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h3 className="font-semibold text-sm">酶动力学参数预测</h3>
          {data.is_real_inference && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
              ML
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground">
            {CLASS_LABELS[data.enzyme_class] || data.enzyme_class}
          </span>
          <span className="text-[9px] text-muted-foreground">{data.sequence_length} aa</span>
        </div>
      </div>

      {data.error && (
        <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3 text-xs text-red-400">
          {data.error}
        </div>
      )}

      {/* Kcat display */}
      <div className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-4 text-center">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">预测 Kcat</p>
        <p className="text-2xl font-bold font-mono text-amber-400">
          {formatKcat(data.predicted_kcat_s1)}
        </p>
        <p className="text-[10px] text-muted-foreground mt-1">
          log₁₀(Kcat) = {data.predicted_log10_kcat.toFixed(2)}
        </p>
        <div className="flex items-center justify-center gap-1.5 mt-1.5">
          <span className="text-[9px] text-muted-foreground">置信区间:</span>
          <code className="text-[10px] font-mono text-muted-foreground">
            {formatKcat(ci[0])} — {formatKcat(ci[1])}
          </code>
        </div>
      </div>

      {/* Efficiency assessment */}
      <div className="flex items-center gap-2 bg-secondary/30 rounded-lg px-3 py-2">
        <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs">{data.efficiency_assessment}</span>
      </div>

      {/* Contributing factors grid */}
      <div className="grid grid-cols-2 gap-1.5">
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">平均残基体积</p>
          <p className="text-xs font-mono font-medium">{f.avg_residue_volume.toFixed(1)} Å³</p>
        </div>
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">平均亲水性</p>
          <p className="text-xs font-mono font-medium">{f.avg_hydropathy.toFixed(2)}</p>
        </div>
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">电荷密度</p>
          <p className="text-xs font-mono font-medium">{(f.charge_density * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">Gly比例</p>
          <p className="text-xs font-mono font-medium">{(f.gly_fraction * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">底物复杂度</p>
          <p className="text-xs font-mono font-medium">{f.substrate_complexity.toFixed(2)}</p>
        </div>
        <div className="bg-secondary/30 rounded p-2">
          <p className="text-[9px] text-muted-foreground">酶类基线</p>
          <p className="text-xs font-mono font-medium">logKcat={f.enzyme_class_baseline.mean_log_kcat}</p>
        </div>
      </div>

      {/* Footer */}
      <div className="text-[10px] text-muted-foreground flex items-center gap-1">
        <Info className="w-3 h-3" />
        {data.method}
      </div>
    </div>
  )
}

export function isCatalyticParamsResult(data: unknown): data is CatalyticParamsData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'predicted_kcat_s1' in d && 'enzyme_class' in d && 'contributing_factors' in d
}
