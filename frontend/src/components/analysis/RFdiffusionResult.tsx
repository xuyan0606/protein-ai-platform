import { useMemo } from 'react'
import { Box, Layers, Gauge, Activity, Hash } from 'lucide-react'

interface ChainData {
  chain_id: string
  coordinates: [number, number, number][]
  num_residues?: number
}

interface SymmetryResult {
  chains: ChainData[]
  num_chains: number
  symmetry: string
  symmetry_label: string
  symmetry_family?: string
  total_residues?: number
}

interface DesignResult {
  design_id: number
  length: number
  monomer_length: number
  symmetry_result: SymmetryResult
  mean_plddt: number
  radius_of_gyration: number
  ss_composition_pct: Record<string, number>
  interface_score: number
  backbone_rmsd_estimate: number
}

export interface RFdiffusionData {
  designs: DesignResult[]
  parameters: {
    length: number
    num_designs: number
    target: string
    symmetry_type: string
    symmetry_label: string
    num_subunits: number
    monomer_length: number
    helix_pct: number
    sheet_pct: number
  }
  target_notes: string
  method: string
  top_design?: {
    design_id: number
    mean_plddt: number
    rg: number
    ss_composition: Record<string, number>
    backbone_rmsd: number
    interface_score: number
    symmetry: SymmetryResult
  }
}

function MetricRow({ icon: Icon, label, value, unit, color }: {
  icon: typeof Box; label: string; value: string | number; unit?: string; color?: string
}) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
      <div className="flex items-center gap-1.5">
        <Icon className={`w-3 h-3 ${color || 'text-muted-foreground'}`} />
        <span className="text-[11px] text-muted-foreground">{label}</span>
      </div>
      <span className="text-[11px] font-mono font-medium">
        {value}{unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
      </span>
    </div>
  )
}

function SSBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{pct}%</span>
      </div>
      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function InterfaceScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, score * 100)
  const color = score > 0.6 ? 'bg-emerald-500' : score > 0.3 ? 'bg-yellow-500' : 'bg-red-400'
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px]">
        <span className="text-muted-foreground">Interface Score</span>
        <span className="font-mono">{score.toFixed(3)}</span>
      </div>
      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ChainPreview({ chain }: { chain: ChainData }) {
  const nRes = chain.num_residues || chain.coordinates.length
  return (
    <div className="flex items-center gap-2 px-2 py-1 rounded bg-secondary/40 text-[10px]">
      <span className="font-mono font-bold text-primary">{chain.chain_id}</span>
      <span className="text-muted-foreground">{nRes} res</span>
      {chain.coordinates.length > 0 && (
        <span className="text-muted-foreground/60 truncate">
          [{chain.coordinates[0].map(c => c.toFixed(1)).join(', ')}]...
        </span>
      )}
    </div>
  )
}

export function RFdiffusionResult({ data }: { data: RFdiffusionData }) {
  const params = data.parameters
  const top = useMemo(() => {
    if (data.top_design) return data.top_design
    const firstDesign = data.designs[0]
    if (!firstDesign) return null
    return {
      design_id: firstDesign.design_id,
      mean_plddt: firstDesign.mean_plddt,
      rg: firstDesign.radius_of_gyration,
      ss_composition: firstDesign.ss_composition_pct,
      backbone_rmsd: firstDesign.backbone_rmsd_estimate,
      interface_score: firstDesign.interface_score,
      symmetry: firstDesign.symmetry_result,
    }
  }, [data.designs, data.top_design])

  const isSymmetric = params.symmetry_type !== 'none' && params.num_subunits > 1

  const ssEntries = useMemo(() => {
    if (!top?.ss_composition) return []
    const colors: Record<string, string> = {
      helix: 'bg-blue-500',
      sheet: 'bg-amber-500',
      loop: 'bg-gray-400',
      extended: 'bg-purple-400',
    }
    return Object.entries(top.ss_composition).map(([k, v]) => ({
      label: k.charAt(0).toUpperCase() + k.slice(1),
      pct: v as number,
      color: colors[k] || 'bg-gray-400',
    }))
  }, [top])

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Box className="w-4 h-4 text-violet-400" />
        <span className="text-xs font-medium">RFdiffusion Design</span>
        {isSymmetric && (
          <span className="px-1.5 py-0.5 rounded bg-violet-500/20 text-[10px] font-medium text-violet-300">
            {params.symmetry_label}
          </span>
        )}
      </div>

      {/* Symmetry info */}
      {isSymmetric && top?.symmetry && (
        <div className="p-2 rounded-md bg-violet-500/10 border border-violet-500/20 space-y-1.5">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-violet-300">
            <Layers className="w-3 h-3" />
            Symmetry: {params.symmetry_type}
          </div>
          <div className="grid grid-cols-3 gap-2 text-[10px]">
            <div>
              <span className="text-muted-foreground block">Family</span>
              <span className="font-mono capitalize">{top.symmetry.symmetry_family || params.symmetry_type}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Subunits</span>
              <span className="font-mono">{params.num_subunits}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Monomer</span>
              <span className="font-mono">{params.monomer_length} aa</span>
            </div>
          </div>

          {/* Chain list (show up to 12) */}
          {top.symmetry.chains.length > 1 && (
            <div className="space-y-1 mt-1.5">
              <span className="text-[10px] text-muted-foreground">Chains ({top.symmetry.num_chains}):</span>
              <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
                {top.symmetry.chains.slice(0, 12).map((chain) => (
                  <ChainPreview key={chain.chain_id} chain={chain} />
                ))}
                {top.symmetry.chains.length > 12 && (
                  <span className="text-[10px] text-muted-foreground self-center px-1">
                    +{top.symmetry.chains.length - 12} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quality metrics */}
      {top && (
        <div className="p-2 rounded-md bg-secondary/30 border border-border space-y-0">
          <MetricRow icon={Gauge} label="Mean pLDDT" value={top.mean_plddt.toFixed(1)} color="text-emerald-400" />
          <MetricRow icon={Activity} label="Radius of Gyration" value={top.rg.toFixed(2)} unit="Å" color="text-blue-400" />
          <MetricRow icon={Hash} label="Backbone RMSD" value={top.backbone_rmsd.toFixed(2)} unit="Å" color="text-amber-400" />
          {isSymmetric && (
            <div className="pt-1.5">
              <InterfaceScoreBar score={top.interface_score} />
            </div>
          )}
        </div>
      )}

      {/* Secondary structure */}
      {ssEntries.length > 0 && (
        <div className="p-2 rounded-md bg-secondary/30 border border-border space-y-1.5">
          <span className="text-[10px] font-medium text-muted-foreground">Secondary Structure</span>
          {ssEntries.map(({ label, pct, color }) => (
            <SSBar key={label} label={label} pct={pct} color={color} />
          ))}
        </div>
      )}

      {/* Design list */}
      {data.designs.length > 1 && (
        <div className="space-y-1">
          <span className="text-[10px] font-medium text-muted-foreground">All Designs:</span>
          {data.designs.map((d) => (
            <div key={d.design_id} className="flex items-center justify-between px-2 py-1 rounded bg-secondary/20 text-[10px]">
              <span className="font-mono">#{d.design_id}</span>
              <span>pLDDT: {d.mean_plddt.toFixed(1)}</span>
              <span>Rg: {d.radius_of_gyration.toFixed(1)} Å</span>
              {isSymmetric && <span>IF: {d.interface_score.toFixed(3)}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Method note */}
      <p className="text-[9px] text-muted-foreground/60 italic">{data.target_notes} — {data.method}</p>
    </div>
  )
}
