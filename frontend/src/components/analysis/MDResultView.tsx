import { Activity, Zap, TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldAlert, Circle } from 'lucide-react'

interface SimulationParams {
  sequence_length: number
  simulation_time_ns: number
  temperature_k: number
  force_field: string
  water_model: string
  estimated_atom_count: number
}

interface Stability {
  rmsd_equilibrated_nm: number
  rmsd_final_nm: number
  rmsd_drift_nm: number
  mean_rmsf_nm: number
  is_stable: boolean
}

interface Compactness {
  radius_of_gyration_initial_nm: number
  radius_of_gyration_final_nm: number
  rg_change_nm: number
  sasa_initial_nm2: number
  sasa_final_nm2: number
}

interface Energetics {
  potential_energy_kjmol: number
  kinetic_energy_kjmol: number
  total_energy_kjmol: number
}

interface FlexibleRegion {
  residues: string
  mean_rmsf_nm: number
  interpretation: string
}

interface MDResult {
  simulation_parameters: SimulationParams
  structural_stability: Stability
  compactness: Compactness
  interactions: { intra_protein_hbonds: number; protein_solvent_hbonds: number }
  energetics: Energetics
  flexible_regions: FlexibleRegion[]
  note?: string
}

interface MutantResult {
  mutation: string
  stability_delta: number
  rmsf_change_mean: number
  stable: boolean
}

interface MDResultData {
  wild_type: MDResult
  mutants?: MutantResult[] | null
  engine: string
  ensemble: string
  pressure_bar?: number
  salt_concentration_m?: number
  note?: string
}

function StabilityGauge({ drift, isStable }: { drift: number; isStable: boolean }) {
  const pct = Math.min(100, Math.max(0, (1 - drift / 0.5) * 100))
  const color = drift < 0.15 ? '#34d399' : drift < 0.3 ? '#fbbf24' : '#f87171'

  return (
    <div className="flex items-center gap-3">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r="22" fill="none" stroke="currentColor" strokeWidth="4" className="text-secondary" />
        <circle
          cx="26" cy="26" r="22" fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${pct * 1.38} ${138 - pct * 1.38}`}
          strokeLinecap="round" transform="rotate(-90 26 26)"
        />
        <text x="26" y="28" textAnchor="middle" fontSize="11" fontWeight="700" fill="currentColor" className="fill-foreground">
          {drift.toFixed(2)}
        </text>
      </svg>
      <div>
        <div className="flex items-center gap-1.5">
          {isStable ? (
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          ) : (
            <ShieldAlert className="w-4 h-4 text-red-400" />
          )}
          <span className={`text-sm font-semibold ${isStable ? 'text-emerald-400' : 'text-red-400'}`}>
            {isStable ? 'Stable' : 'Unstable'}
          </span>
        </div>
        <p className="text-[10px] text-muted-foreground mt-0.5">RMSD drift {drift} nm</p>
      </div>
    </div>
  )
}

function MetricCard({ label, value, unit, delta }: { label: string; value: number; unit: string; delta?: number }) {
  return (
    <div className="bg-secondary/30 rounded-lg p-2.5">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="flex items-baseline gap-1 mt-0.5">
        <span className="text-sm font-bold font-mono">{value.toFixed(2)}</span>
        <span className="text-[9px] text-muted-foreground">{unit}</span>
      </div>
      {delta !== undefined && delta !== 0 && (
        <div className={`flex items-center gap-0.5 mt-0.5 text-[10px] ${delta > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
          {delta > 0 ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
          {delta > 0 ? '+' : ''}{delta.toFixed(2)}
        </div>
      )}
    </div>
  )
}

function EnergyBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(100, Math.abs(value) / max * 100)
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground w-20 shrink-0 text-right">{label}</span>
      <div className="flex-1 h-2.5 bg-secondary rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono font-medium w-16 text-right">{value.toFixed(0)}</span>
    </div>
  )
}

export function MDResultView({ data }: { data: MDResultData }) {
  const { wild_type: wt, mutants, engine, ensemble, pressure_bar } = data
  const { simulation_parameters: p, structural_stability: s, compactness: c, interactions: i, energetics: e, flexible_regions } = wt

  const maxEnergy = Math.max(
    Math.abs(e.potential_energy_kjmol),
    Math.abs(e.kinetic_energy_kjmol),
    Math.abs(e.total_energy_kjmol),
    1
  )

  return (
    <div className="space-y-4 text-sm">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <Activity className="w-4 h-4 text-primary" />
        <h3 className="font-semibold">MD Simulation Results</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        {engine} · {ensemble} · {p.simulation_time_ns}ns · {p.temperature_k}K · {p.force_field}/{p.water_model}
        {pressure_bar && <> · {pressure_bar} bar</>}
        {' · '}{p.estimated_atom_count} atoms
      </p>

      {/* Stability Gauge */}
      <div className="bg-secondary/30 border border-border rounded-lg p-4">
        <StabilityGauge drift={s.rmsd_drift_nm} isStable={s.is_stable} />
      </div>

      {/* Structural Stability Metrics */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Structural Stability</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <MetricCard label="RMSD Final" value={s.rmsd_final_nm} unit="nm" />
          <MetricCard label="RMSD Drift" value={s.rmsd_drift_nm} unit="nm" />
          <MetricCard label="Mean RMSF" value={s.mean_rmsf_nm} unit="nm" />
          <MetricCard label="Equilibrated" value={s.rmsd_equilibrated_nm} unit="nm" />
        </div>
      </div>

      {/* Compactness */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Compactness & Solvation</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <MetricCard label="Rg Initial" value={c.radius_of_gyration_initial_nm} unit="nm" />
          <MetricCard label="Rg Final" value={c.radius_of_gyration_final_nm} unit="nm" delta={c.rg_change_nm} />
          <MetricCard label="SASA Initial" value={c.sasa_initial_nm2} unit="nm²" />
          <MetricCard label="SASA Final" value={c.sasa_final_nm2} unit="nm²" />
        </div>
      </div>

      {/* Energetics */}
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Zap className="w-3 h-3" /> Energetics (kJ/mol)
        </h4>
        <div className="bg-secondary/30 rounded-lg p-3 space-y-2">
          <EnergyBar label="Potential" value={e.potential_energy_kjmol} max={maxEnergy} color="bg-blue-400" />
          <EnergyBar label="Kinetic" value={e.kinetic_energy_kjmol} max={maxEnergy} color="bg-amber-400" />
          <EnergyBar label="Total" value={e.total_energy_kjmol} max={maxEnergy} color="bg-purple-400" />
        </div>
      </div>

      {/* Interactions */}
      <div className="flex gap-3">
        <div className="flex-1 bg-secondary/30 rounded-lg p-3">
          <div className="text-[10px] text-muted-foreground">Intra-protein H-bonds</div>
          <div className="text-lg font-bold font-mono mt-1">{i.intra_protein_hbonds}</div>
        </div>
        <div className="flex-1 bg-secondary/30 rounded-lg p-3">
          <div className="text-[10px] text-muted-foreground">Protein-Solvent H-bonds</div>
          <div className="text-lg font-bold font-mono mt-1">{i.protein_solvent_hbonds}</div>
        </div>
      </div>

      {/* Flexible Regions */}
      {flexible_regions.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Flexible Regions</h4>
          <div className="space-y-1">
            {flexible_regions.map((fr, idx) => (
              <div key={idx} className="flex items-center gap-2 bg-secondary/30 rounded-lg px-3 py-2">
                <Circle className={`w-2 h-2 ${fr.mean_rmsf_nm > 0.4 ? 'fill-red-400 text-red-400' : 'fill-amber-400 text-amber-400'}`} />
                <code className="text-[11px] font-mono font-medium">{fr.residues}</code>
                <span className="text-[10px] text-muted-foreground">RMSF {fr.mean_rmsf_nm}nm</span>
                <div className="flex-1" />
                <span className="text-[10px] text-muted-foreground">{fr.interpretation}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mutant Comparison */}
      {mutants && mutants.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Mutant Comparison</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 text-[10px] text-muted-foreground font-medium">Mutation</th>
                  <th className="text-right py-2 px-2 text-[10px] text-muted-foreground font-medium">ΔΔG (kJ/mol)</th>
                  <th className="text-right py-2 px-2 text-[10px] text-muted-foreground font-medium">ΔRMSF (nm)</th>
                  <th className="text-center py-2 px-2 text-[10px] text-muted-foreground font-medium">Stable</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/50">
                  <td className="py-2 px-2 font-mono font-medium">WT</td>
                  <td className="py-2 px-2 text-right text-muted-foreground">—</td>
                  <td className="py-2 px-2 text-right text-muted-foreground">—</td>
                  <td className="py-2 px-2 text-center">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 mx-auto" />
                  </td>
                </tr>
                {mutants.map((m, idx) => (
                  <tr key={idx} className="border-b border-border/30 hover:bg-secondary/20">
                    <td className="py-2 px-2">
                      <code className="font-mono text-[11px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">{m.mutation}</code>
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${m.stability_delta > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                      {m.stability_delta > 0 ? '+' : ''}{m.stability_delta.toFixed(1)}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${m.rmsf_change_mean > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                      {m.rmsf_change_mean > 0 ? '+' : ''}{m.rmsf_change_mean.toFixed(3)}
                    </td>
                    <td className="py-2 px-2 text-center">
                      {m.stable ? (
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 mx-auto" />
                      ) : (
                        <ShieldAlert className="w-3.5 h-3.5 text-red-400 mx-auto" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export function isMDResult(data: unknown): data is MDResultData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'wild_type' in d && 'engine' in d
}
