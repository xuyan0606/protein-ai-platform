import { CheckCircle2, XCircle, AlertTriangle, Info, FlaskConical, Thermometer, Dna, Box, Zap } from 'lucide-react'

interface BenchmarkData {
  query_info: { length: number; sequence_preview: string }
  family: { identified: string | null; name: string; ec?: string; mechanism?: string; confidence: string }
  properties: {
    molecular_weight_kda: number
    isoelectric_point: number
    gravy: number
    amino_acid_composition: Record<string, number>
    charge_distribution: Record<string, number>
    surface_lys_arg_count: number
    surface_candidate_count: number
    gly_count: number
    pro_count: number
    cys_count: number
  }
  conservation_analysis: { highly_conserved_count: number; variable_count: number; conserved_positions: number[] }
  family_motifs: Array<{ region: string; pattern: string; found_at: string; matched_sequence?: string; match_quality?: string }>
  catalytic_residues: { known: boolean; family?: string; residues?: Array<{ role: string; position: number; residue: string }> }
  domain_architecture: Array<{ domain: string; fold: string; role: string; estimated_region: string }>
  homolog_comparison: { blast_top_hits?: Array<{ name: string; identity_pct: number; e_value: string }>; summary: string }
  engineering_targets: {
    ph_lowering?: Array<{ position: number; mutation: string; rationale: string; priority: string }>
    thermostability?: Array<{ position: number; mutation: string; rationale: string; priority: string }>
    never_mutate?: Array<{ category: string; reason: string; residues?: string[] }>
  }
  benchmark_metrics: {
    ph_engineering?: { pI: number; assessment: string; estimated_mutations_needed?: string }
    thermostability?: { gly_to_pro_candidates: number; disulfide_potential: string; recommendation: string }
  }
  known_engineering_successes: Array<{ mutation: string; effect: string; organism: string }>
  recommendations: Array<{
    priority: number
    category: string
    action: string
    candidates?: Array<{ position: number; mutation: string; rationale: string }>
    residues?: Array<{ category: string; reason: string }>
    examples?: Array<{ mutation: string; effect: string; organism: string }>
    plan?: string[]
    rationale?: string
  }>
}

function ConfidenceBadge({ level }: { level: string }) {
  const map: Record<string, { color: string; icon: typeof CheckCircle2 }> = {
    high: { color: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20', icon: CheckCircle2 },
    medium: { color: 'bg-amber-500/10 text-amber-400 border-amber-500/20', icon: AlertTriangle },
    low: { color: 'bg-red-500/10 text-red-400 border-red-500/20', icon: XCircle },
    none: { color: 'bg-muted text-muted-foreground border-border', icon: Info },
  }
  const c = map[level] || map.none
  const Icon = c.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${c.color}`}>
      <Icon className="w-2.5 h-2.5" />
      {level}
    </span>
  )
}

function MotifBadge({ found }: { found: string }) {
  const isFound = !found.includes('not detected')
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
      isFound ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
    }`}>
      {isFound ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
      {isFound ? 'Found' : 'Not detected'}
    </span>
  )
}

export function BenchmarkReport({ data }: { data: BenchmarkData }) {
  const { query_info, family, properties, conservation_analysis, family_motifs, catalytic_residues, domain_architecture, benchmark_metrics, known_engineering_successes, recommendations } = data

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Dna className="w-4 h-4 text-primary" />
            <h3 className="font-semibold">{family.name}</h3>
            <ConfidenceBadge level={family.confidence} />
          </div>
          <p className="text-xs text-muted-foreground">
            {query_info.length} residues · {family.ec || 'EC unknown'} · {family.mechanism || 'Mechanism unknown'}
          </p>
        </div>
      </div>

      {/* Physicochemical Properties */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Thermometer className="w-3 h-3" /> Properties
        </h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'MW (kDa)', value: properties.molecular_weight_kda },
            { label: 'pI', value: properties.isoelectric_point },
            { label: 'GRAVY', value: properties.gravy },
            { label: 'Gly→Pro Candidates', value: properties.gly_count },
            { label: 'Surface K+R', value: properties.surface_lys_arg_count },
            { label: 'Surface Candidates', value: properties.surface_candidate_count },
            { label: 'Pro Stabilizers', value: properties.pro_count },
            { label: 'Cys (SS bonds)', value: properties.cys_count },
          ].map((item) => (
            <div key={item.label} className="bg-secondary/50 rounded-lg p-2.5">
              <div className="text-[10px] text-muted-foreground">{item.label}</div>
              <div className="text-sm font-semibold font-mono">{item.value}</div>
            </div>
          ))}
        </div>
        {/* Charge distribution bar */}
        <div className="mt-2 bg-secondary/30 rounded-lg p-2.5">
          <div className="text-[10px] text-muted-foreground mb-1.5">Charge Distribution</div>
          <div className="flex h-5 rounded-full overflow-hidden text-[9px]">
            {[
              { pct: properties.charge_distribution.acidic_D_E_pct, color: 'bg-red-400', label: 'Acidic' },
              { pct: properties.charge_distribution.basic_R_K_H_pct, color: 'bg-blue-400', label: 'Basic' },
              { pct: properties.charge_distribution.polar_N_Q_S_T_pct, color: 'bg-green-400', label: 'Polar' },
              { pct: properties.charge_distribution.hydrophobic_pct, color: 'bg-amber-400', label: 'Hydrophobic' },
              { pct: properties.charge_distribution.special_C_G_P_pct, color: 'bg-purple-400', label: 'Special' },
            ].map((seg) => (
              <div
                key={seg.label}
                className={`${seg.color} flex items-center justify-center`}
                style={{ width: `${seg.pct}%` }}
                title={`${seg.label}: ${seg.pct}%`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[9px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Acidic {properties.charge_distribution.acidic_D_E_pct}%</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" />Basic {properties.charge_distribution.basic_R_K_H_pct}%</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400" />Polar {properties.charge_distribution.polar_N_Q_S_T_pct}%</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" />Hydro {properties.charge_distribution.hydrophobic_pct}%</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-400" />Special {properties.charge_distribution.special_C_G_P_pct}%</span>
          </div>
        </div>
      </div>

      {/* Conservation Analysis */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Conservation</h4>
        <div className="flex gap-3">
          <div className="flex-1 bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-3">
            <div className="text-emerald-400 font-bold text-lg">{conservation_analysis.highly_conserved_count}</div>
            <div className="text-[10px] text-muted-foreground">Highly Conserved</div>
          </div>
          <div className="flex-1 bg-amber-500/5 border border-amber-500/10 rounded-lg p-3">
            <div className="text-amber-400 font-bold text-lg">{conservation_analysis.variable_count}</div>
            <div className="text-[10px] text-muted-foreground">Variable Positions</div>
          </div>
        </div>
      </div>

      {/* Family Motifs */}
      {family_motifs.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Conserved Motifs</h4>
          <div className="space-y-1.5">
            {family_motifs.map((motif) => (
              <div key={motif.region} className="flex items-start justify-between gap-3 bg-secondary/30 rounded-lg p-2.5">
                <div>
                  <span className="text-xs font-medium">{motif.region}</span>
                  <code className="text-[10px] text-muted-foreground ml-2 font-mono">{motif.pattern}</code>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{motif.found_at}</div>
                </div>
                <MotifBadge found={motif.found_at} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Domain Architecture */}
      {domain_architecture.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Box className="w-3 h-3" /> Domain Architecture
          </h4>
          <div className="flex flex-wrap gap-2">
            {domain_architecture.map((dom) => (
              <div key={dom.domain} className="flex-1 min-w-[140px] bg-secondary/30 rounded-lg p-3 border border-border">
                <div className="text-xs font-semibold">{dom.domain} Domain</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{dom.fold}</div>
                <div className="text-[10px] text-muted-foreground">{dom.role}</div>
                <div className="text-[10px] text-muted-foreground mt-1 italic">{dom.estimated_region}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Catalytic Residues */}
      {catalytic_residues.known && catalytic_residues.residues && catalytic_residues.residues.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Zap className="w-3 h-3" /> Catalytic Residues
          </h4>
          <div className="flex flex-wrap gap-2">
            {catalytic_residues.residues.map((res) => (
              <div key={res.role} className="bg-amber-500/5 border border-amber-500/10 rounded-lg px-3 py-2">
                <div className="text-xs font-medium">{res.role}</div>
                <code className="text-[11px] text-amber-400 font-mono">{res.residue}{res.position}</code>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Benchmark Metrics */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Engineering Assessment</h4>
        <div className="space-y-2">
          {benchmark_metrics.ph_engineering && (
            <div className="bg-secondary/30 rounded-lg p-3">
              <div className="text-xs font-medium">pH Engineering — pI = {benchmark_metrics.ph_engineering.pI}</div>
              <p className="text-[11px] text-muted-foreground mt-0.5">{benchmark_metrics.ph_engineering.assessment}</p>
              {benchmark_metrics.ph_engineering.estimated_mutations_needed && (
                <p className="text-[11px] text-muted-foreground mt-0.5">Estimated: {benchmark_metrics.ph_engineering.estimated_mutations_needed}</p>
              )}
            </div>
          )}
          {benchmark_metrics.thermostability && (
            <div className="bg-secondary/30 rounded-lg p-3">
              <div className="text-xs font-medium">Thermostability</div>
              <p className="text-[11px] text-muted-foreground mt-0.5">{benchmark_metrics.thermostability.recommendation}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">Disulfide: {benchmark_metrics.thermostability.disulfide_potential}</p>
            </div>
          )}
        </div>
      </div>

      {/* Known Engineering Successes */}
      {known_engineering_successes.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <FlaskConical className="w-3 h-3" /> Known Engineering Successes
          </h4>
          <div className="space-y-1.5">
            {known_engineering_successes.map((s, i) => (
              <div key={i} className="flex items-start gap-2 bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-2.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <code className="text-[11px] font-mono">{s.mutation}</code>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{s.effect}</div>
                  <div className="text-[10px] text-muted-foreground/70">{s.organism}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Recommendations</h4>
          <div className="space-y-2">
            {recommendations.map((rec, i) => (
              <div key={i} className={`rounded-lg border p-3 ${
                rec.priority === 0 ? 'bg-red-500/5 border-red-500/20' :
                rec.priority === 1 ? 'bg-primary/5 border-primary/20' :
                'bg-secondary/30 border-border'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    rec.priority === 0 ? 'bg-red-500/20 text-red-400' :
                    rec.priority === 1 ? 'bg-primary/20 text-primary' :
                    'bg-secondary text-muted-foreground'
                  }`}>
                    P{rec.priority}
                  </span>
                  <span className="text-xs font-semibold">{rec.category}</span>
                </div>
                <p className="text-xs font-medium">{rec.action}</p>
                {rec.rationale && <p className="text-[11px] text-muted-foreground mt-0.5">{rec.rationale}</p>}
                {rec.candidates && rec.candidates.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {rec.candidates.slice(0, 5).map((c) => (
                      <code key={c.position} className="text-[10px] bg-secondary px-1.5 py-0.5 rounded font-mono">{c.mutation}</code>
                    ))}
                    {rec.candidates.length > 5 && <span className="text-[10px] text-muted-foreground">+{rec.candidates.length - 5} more</span>}
                  </div>
                )}
                {rec.examples && rec.examples.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {rec.examples.slice(0, 3).map((ex, j) => (
                      <div key={j} className="text-[10px] text-muted-foreground flex gap-1">
                        <span className="text-emerald-400">→</span> {ex.mutation}: {ex.effect} ({ex.organism})
                      </div>
                    ))}
                  </div>
                )}
                {rec.plan && (
                  <div className="mt-2 space-y-0.5">
                    {rec.plan.map((step, j) => (
                      <div key={j} className="text-[10px] text-muted-foreground flex gap-1">
                        <span className="text-muted-foreground">{j + 1}.</span> {step}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function isBenchmarkResult(data: unknown): data is BenchmarkData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'query_info' in d && 'family' in d && 'benchmark_metrics' in d && 'recommendations' in d
}
