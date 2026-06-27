import { Beaker, ShieldCheck, ShieldAlert, HelpCircle } from 'lucide-react'

interface ECPrediction {
  ec_number: string
  name: string
  class: string
  confidence: string
  score: number
  motif_hits?: number
  motif_details?: Array<{ pattern: string; position: number; matched: string }>
}

interface ECPredictionData {
  query_length: number
  predictions: ECPrediction[]
  top_k?: number
  model: string
  method: string
  is_real_inference?: boolean
  embedding_info?: { embedding_dim?: number; model?: string } | null
  error?: string
}

const CONFIDENCE_CONFIG: Record<string, { color: string; icon: typeof ShieldCheck }> = {
  high: { color: 'text-emerald-400', icon: ShieldCheck },
  medium: { color: 'text-amber-400', icon: ShieldAlert },
  low: { color: 'text-muted-foreground', icon: HelpCircle },
}

const CLASS_COLORS: Record<string, string> = {
  'Hydrolase': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  'Transferase': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  'Oxidoreductase': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  'Lyase': 'bg-green-500/10 text-green-400 border-green-500/20',
  'Isomerase': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  'Ligase': 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  'Unknown': 'bg-muted text-muted-foreground border-border',
}

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score * 100))
  const color = score >= 0.7 ? 'bg-emerald-400' : score >= 0.5 ? 'bg-amber-400' : 'bg-muted-foreground'
  return (
    <div className="w-20 h-1.5 bg-secondary rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function ECPredictionCard({ data }: { data: ECPredictionData }) {
  const predictions = data.predictions || []

  return (
    <div className="space-y-3 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Beaker className="w-4 h-4 text-purple-400" />
          <h3 className="font-semibold text-sm">酶功能预测 (EC编号)</h3>
          {data.is_real_inference && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
              ML
            </span>
          )}
        </div>
        <span className="text-[10px] text-muted-foreground">{data.query_length} aa</span>
      </div>

      {data.error && (
        <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3 text-xs text-red-400">
          {data.error}
        </div>
      )}

      {/* Predictions */}
      {predictions.length === 0 ? (
        <div className="text-center py-6 text-xs text-muted-foreground">
          <HelpCircle className="w-8 h-8 text-muted-foreground/20 mx-auto mb-2" />
          未检测到已知酶家族特征 — 该蛋白可能属于新型酶类
        </div>
      ) : (
        <div className="space-y-2">
          {predictions.map((pred, i) => {
            const confCfg = CONFIDENCE_CONFIG[pred.confidence] || CONFIDENCE_CONFIG.low
            const Icon = confCfg.icon
            const classColor = CLASS_COLORS[pred.class] || CLASS_COLORS.Unknown
            return (
              <div key={i} className="bg-secondary/30 border border-border rounded-lg p-3">
                <div className="flex items-center justify-between gap-3 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-muted-foreground">#{i + 1}</span>
                    <code className="text-sm font-bold font-mono text-primary">{pred.ec_number}</code>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${classColor}`}>
                      {pred.class}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Icon className={`w-3 h-3 ${confCfg.color}`} />
                    <span className={`text-[10px] font-medium ${confCfg.color}`}>
                      {pred.confidence === 'high' ? '高置信度' : pred.confidence === 'medium' ? '中置信度' : '低置信度'}
                    </span>
                    <ConfidenceBar score={pred.score} />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-1">{pred.name}</p>
                {/* Motif evidence */}
                {pred.motif_details && pred.motif_details.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {pred.motif_details.map((m, j) => (
                      <div key={j} className="flex items-center gap-2 text-[10px] text-muted-foreground">
                        <code className="bg-secondary px-1.5 py-0.5 rounded font-mono">{m.pattern}</code>
                        <span>位点 {m.position}</span>
                        <code className="text-primary/70 font-mono">{m.matched}</code>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Footer */}
      <div className="text-[10px] text-muted-foreground flex items-center gap-3">
        <span>{data.model}</span>
      </div>
    </div>
  )
}

export function isECPredictionResult(data: unknown): data is ECPredictionData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'predictions' in d && 'query_length' in d && 'method' in d
}
