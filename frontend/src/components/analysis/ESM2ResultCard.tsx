import { Dna, TrendingUp, TrendingDown, Minus, Zap } from 'lucide-react'

interface ESM2Mutation {
  mutation: string
  position: number
  wild_type: string
  mutant: string
  score: number
  prediction: string
  method?: string
  error?: string
}

interface ESM2Residue {
  position: number
  amino_acid: string
  embedding_preview: number[]
}

interface ESM2ResultData {
  mutations?: ESM2Mutation[]
  per_residue?: ESM2Residue[]
  sequence_length?: number
  embedding_dim?: number
  model: string
  method: string
  is_real_inference?: boolean
  error?: string
}

const PREDICTION_LABELS: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  strongly_favored: { label: '强烈有利', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', icon: TrendingUp },
  mildly_favored: { label: '轻微有利', color: 'text-teal-400 bg-teal-500/10 border-teal-500/20', icon: TrendingUp },
  neutral: { label: '中性', color: 'text-muted-foreground bg-muted/30 border-border', icon: Minus },
  disfavored: { label: '不利', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20', icon: TrendingDown },
  strongly_disfavored: { label: '强烈不利', color: 'text-red-400 bg-red-500/10 border-red-500/20', icon: TrendingDown },
}

export function ESM2ResultCard({ data }: { data: ESM2ResultData }) {
  const mutations = data.mutations || []

  return (
    <div className="space-y-3 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Dna className="w-4 h-4 text-blue-400" />
          <h3 className="font-semibold text-sm">ESM-2 突变效应预测</h3>
          {data.is_real_inference && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
              ML
            </span>
          )}
        </div>
        <span className="text-[10px] text-muted-foreground">{data.model}</span>
      </div>
      <p className="text-[10px] text-muted-foreground">{data.method}</p>

      {data.error && (
        <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-3 text-xs text-red-400">
          {data.error}
        </div>
      )}

      {/* Embedding info */}
      {data.embedding_dim && (
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span>嵌入维度: {data.embedding_dim}</span>
          {data.sequence_length && <span>序列长度: {data.sequence_length}</span>}
        </div>
      )}

      {/* Per-residue embeddings preview */}
      {data.per_residue && data.per_residue.length > 0 && (
        <div>
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
            残基嵌入预览 (前5维)
          </h4>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {data.per_residue.slice(0, 20).map((r) => (
              <div key={r.position} className="flex items-center gap-2 text-xs">
                <code className="font-mono font-medium w-16">{r.amino_acid}{r.position}</code>
                <div className="flex gap-0.5">
                  {r.embedding_preview.map((v, i) => (
                    <span key={i} className="text-[9px] text-muted-foreground font-mono w-14 truncate">
                      {v.toFixed(3)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {data.per_residue.length > 20 && (
              <p className="text-[10px] text-muted-foreground pl-16">
                ... 还有 {data.per_residue.length - 20} 个残基
              </p>
            )}
          </div>
        </div>
      )}

      {/* Mutation scores */}
      {mutations.length > 0 && (
        <div className="space-y-1.5">
          {mutations.map((m, i) => {
            const pred = PREDICTION_LABELS[m.prediction] || PREDICTION_LABELS.neutral
            const Icon = pred.icon
            return (
              <div key={i} className="flex items-center gap-3 bg-secondary/30 rounded-lg px-3 py-2">
                <code className="text-xs font-mono font-medium w-20 shrink-0">{m.mutation}</code>
                <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium border ${pred.color}`}>
                  <Icon className="w-2.5 h-2.5" />
                  {pred.label}
                </div>
                <div className="flex-1" />
                <span className="text-xs font-mono font-bold">
                  {m.score > 0 ? '+' : ''}{m.score.toFixed(2)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function isESM2Result(data: unknown): data is ESM2ResultData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return ('mutations' in d || 'per_residue' in d || 'embedding_dim' in d) && 'model' in d
}
