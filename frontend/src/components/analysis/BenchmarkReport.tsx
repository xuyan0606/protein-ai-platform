import { CheckCircle2, XCircle, AlertTriangle, Info, FlaskConical, Thermometer, Dna, Box, Zap, Download, Printer } from 'lucide-react'
import { downloadReport, printReport } from '@/lib/report'
import { ReportBadge, ReportBody, ReportHeader, ReportMetricCard, ReportMetricGrid, ReportPanel, ReportSection, ReportShell } from '@/components/analysis/ReportShell'

export interface BenchmarkData {
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
  const map: Record<string, { tone: 'success' | 'warning' | 'danger' | 'neutral'; icon: typeof CheckCircle2 }> = {
    high: { tone: 'success', icon: CheckCircle2 },
    medium: { tone: 'warning', icon: AlertTriangle },
    low: { tone: 'danger', icon: XCircle },
    none: { tone: 'neutral', icon: Info },
  }
  const c = map[level] || map.none
  const Icon = c.icon
  return (
    <ReportBadge tone={c.tone}>
      <Icon className="w-2.5 h-2.5" />
      {level}
    </ReportBadge>
  )
}

function MotifBadge({ found }: { found: string }) {
  const isFound = !found.includes('not detected')
  return (
    <ReportBadge tone={isFound ? 'success' : 'danger'}>
      {isFound ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
      {isFound ? 'Found' : 'Not detected'}
    </ReportBadge>
  )
}

function recommendationTone(priority: number): 'danger' | 'info' | 'neutral' {
  if (priority === 0) return 'danger'
  if (priority === 1) return 'info'
  return 'neutral'
}

export function BenchmarkReport({ data }: { data: BenchmarkData }) {
  const {
    query_info,
    family,
    properties,
    conservation_analysis,
    family_motifs,
    catalytic_residues,
    domain_architecture,
    benchmark_metrics,
    known_engineering_successes,
    recommendations,
  } = data

  return (
    <ReportShell>
      <ReportHeader
        icon={Dna}
        title={family.name}
        subtitle={`${query_info.length} residues · ${family.ec || 'EC unknown'} · ${family.mechanism || 'Mechanism unknown'}`}
        badge={<ConfidenceBadge level={family.confidence} />}
        actions={
          <>
            <button onClick={() => downloadReport('benchmark', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Download HTML report">
              <Download className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => printReport('benchmark', data)} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="Print report">
              <Printer className="w-3.5 h-3.5" />
            </button>
          </>
        }
      />
      <ReportBody>
        <ReportSection title="Properties" icon={Thermometer}>
          <ReportMetricGrid>
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
              <ReportMetricCard key={item.label} label={item.label} value={item.value} mono />
            ))}
          </ReportMetricGrid>

          <ReportPanel>
            <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Charge Distribution</div>
            <div className="mt-2 flex h-5 overflow-hidden rounded-full text-[9px]">
              {[
                { pct: properties.charge_distribution.acidic_D_E_pct, color: 'bg-red-400', label: 'Acidic' },
                { pct: properties.charge_distribution.basic_R_K_H_pct, color: 'bg-blue-400', label: 'Basic' },
                { pct: properties.charge_distribution.polar_N_Q_S_T_pct, color: 'bg-green-400', label: 'Polar' },
                { pct: properties.charge_distribution.hydrophobic_pct, color: 'bg-amber-400', label: 'Hydrophobic' },
                { pct: properties.charge_distribution.special_C_G_P_pct, color: 'bg-fuchsia-400', label: 'Special' },
              ].map((seg) => (
                <div
                  key={seg.label}
                  className={seg.color}
                  style={{ width: `${seg.pct}%` }}
                  title={`${seg.label}: ${seg.pct}%`}
                />
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Acidic {properties.charge_distribution.acidic_D_E_pct}%</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" />Basic {properties.charge_distribution.basic_R_K_H_pct}%</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400" />Polar {properties.charge_distribution.polar_N_Q_S_T_pct}%</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" />Hydro {properties.charge_distribution.hydrophobic_pct}%</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-fuchsia-400" />Special {properties.charge_distribution.special_C_G_P_pct}%</span>
            </div>
          </ReportPanel>
        </ReportSection>

        <ReportSection title="Conservation">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ReportMetricCard label="Highly Conserved" value={conservation_analysis.highly_conserved_count} tone="success" />
            <ReportMetricCard label="Variable Positions" value={conservation_analysis.variable_count} tone="warning" />
          </div>
        </ReportSection>

        {family_motifs.length > 0 && (
          <ReportSection title="Conserved Motifs">
            <div className="space-y-2">
              {family_motifs.map((motif) => (
                <ReportPanel key={motif.region} className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-xs font-medium">{motif.region}</span>
                    <code className="ml-2 font-mono text-[10px] text-muted-foreground">{motif.pattern}</code>
                    <div className="mt-1 text-[10px] text-muted-foreground">{motif.found_at}</div>
                  </div>
                  <MotifBadge found={motif.found_at} />
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}

        {domain_architecture.length > 0 && (
          <ReportSection title="Domain Architecture" icon={Box}>
            <div className="flex flex-wrap gap-3">
              {domain_architecture.map((dom) => (
                <ReportPanel key={dom.domain} className="min-w-[180px] flex-1">
                  <div className="text-xs font-semibold">{dom.domain} Domain</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">{dom.fold}</div>
                  <div className="text-[10px] text-muted-foreground">{dom.role}</div>
                  <div className="mt-1 text-[10px] italic text-muted-foreground">{dom.estimated_region}</div>
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}

        {catalytic_residues.known && catalytic_residues.residues && catalytic_residues.residues.length > 0 && (
          <ReportSection title="Catalytic Residues" icon={Zap}>
            <div className="flex flex-wrap gap-2">
              {catalytic_residues.residues.map((res) => (
                <ReportPanel key={res.role} tone="warning" className="px-3 py-2">
                  <div className="text-xs font-medium">{res.role}</div>
                  <code className="font-mono text-[11px] text-amber-500">{res.residue}{res.position}</code>
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}

        <ReportSection title="Engineering Assessment">
          <div className="space-y-2">
            {benchmark_metrics.ph_engineering && (
              <ReportPanel>
                <div className="text-xs font-medium">pH Engineering — pI = {benchmark_metrics.ph_engineering.pI}</div>
                <p className="mt-1 text-[11px] text-muted-foreground">{benchmark_metrics.ph_engineering.assessment}</p>
                {benchmark_metrics.ph_engineering.estimated_mutations_needed && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Estimated: {benchmark_metrics.ph_engineering.estimated_mutations_needed}
                  </p>
                )}
              </ReportPanel>
            )}
            {benchmark_metrics.thermostability && (
              <ReportPanel>
                <div className="text-xs font-medium">Thermostability</div>
                <p className="mt-1 text-[11px] text-muted-foreground">{benchmark_metrics.thermostability.recommendation}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Disulfide: {benchmark_metrics.thermostability.disulfide_potential}
                </p>
              </ReportPanel>
            )}
          </div>
        </ReportSection>

        {known_engineering_successes.length > 0 && (
          <ReportSection title="Known Engineering Successes" icon={FlaskConical}>
            <div className="space-y-2">
              {known_engineering_successes.map((s, i) => (
                <ReportPanel key={i} tone="success" className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  <div>
                    <code className="font-mono text-[11px]">{s.mutation}</code>
                    <div className="mt-1 text-[11px] text-muted-foreground">{s.effect}</div>
                    <div className="text-[10px] text-muted-foreground/80">{s.organism}</div>
                  </div>
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}

        {recommendations.length > 0 && (
          <ReportSection title="Recommendations">
            <div className="space-y-2">
              {recommendations.map((rec, i) => (
                <ReportPanel key={i} tone={recommendationTone(rec.priority)}>
                  <div className="mb-2 flex items-center gap-2">
                    <ReportBadge tone={recommendationTone(rec.priority)}>P{rec.priority}</ReportBadge>
                    <span className="text-xs font-semibold">{rec.category}</span>
                  </div>
                  <p className="text-xs font-medium">{rec.action}</p>
                  {rec.rationale && <p className="mt-1 text-[11px] text-muted-foreground">{rec.rationale}</p>}
                  {rec.candidates && rec.candidates.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {rec.candidates.slice(0, 5).map((c) => (
                        <code key={c.position} className="rounded-md border border-border/70 bg-background/70 px-2 py-1 font-mono text-[10px]">
                          {c.mutation}
                        </code>
                      ))}
                      {rec.candidates.length > 5 && (
                        <span className="text-[10px] text-muted-foreground">+{rec.candidates.length - 5} more</span>
                      )}
                    </div>
                  )}
                  {rec.examples && rec.examples.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {rec.examples.slice(0, 3).map((ex, j) => (
                        <div key={j} className="flex gap-1 text-[10px] text-muted-foreground">
                          <span className="text-emerald-500">→</span>
                          {ex.mutation}: {ex.effect} ({ex.organism})
                        </div>
                      ))}
                    </div>
                  )}
                  {rec.plan && (
                    <div className="mt-2 space-y-1">
                      {rec.plan.map((step, j) => (
                        <div key={j} className="flex gap-1 text-[10px] text-muted-foreground">
                          <span>{j + 1}.</span>
                          {step}
                        </div>
                      ))}
                    </div>
                  )}
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        )}
      </ReportBody>
    </ReportShell>
  )
}
