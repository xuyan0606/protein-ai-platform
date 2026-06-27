import { useState } from 'react'
import { Dna, Layers, Ruler, Zap, Grid3X3, Copy, Check } from 'lucide-react'
import { ProteinViewer } from '@/components/viewer/ProteinViewer'

interface ChainData {
  chain_id: string
  sequence: string
  residue_count: number
  atom_count: number
  residue_range: [number, number] | null
}

interface PDBAnalysisData {
  header?: { title?: string }
  chains: ChainData[]
  resolution?: number | null
  r_factor?: number | null
  space_group?: string | null
  unit_cell?: Record<string, number> | null
  b_factor_stats?: { mean: number; min: number; max: number } | null
  total_atoms: number
  total_residues: number
  seqres_sequence?: string | null
  method?: string | null
  deposited_date?: string | null
  object_name?: string
  download_url?: string
  file_name?: string
  file_size?: number
}

interface Props {
  data: PDBAnalysisData
  pdbContent?: string
}

export function PDBAnalysisCard({ data, pdbContent }: Props) {
  const [copiedChain, setCopiedChain] = useState<string | null>(null)

  const copySequence = async (seq: string, chainId: string) => {
    await navigator.clipboard.writeText(seq)
    setCopiedChain(chainId)
    setTimeout(() => setCopiedChain(null), 2000)
  }

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 bg-secondary/50 border-b border-border">
        <Dna className="w-5 h-5 text-blue-500" />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold truncate">
            {data.header?.title || data.file_name || 'PDB Structure'}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            {data.method && `${data.method}  `}
            {data.deposited_date && `${data.deposited_date}  `}
            {data.total_residues} residues  {data.total_atoms} atoms
          </p>
        </div>
      </div>

      {/* 3D Viewer */}
      {pdbContent && (
        <div className="border-b border-border">
          <ProteinViewer pdbData={pdbContent} height={320} />
        </div>
      )}

      {/* Structure metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 border-b border-border">
        {data.resolution && (
          <Metric icon={Ruler} label="Resolution" value={`${data.resolution} Å`} />
        )}
        {data.r_factor && (
          <Metric icon={Layers} label="R-factor" value={`${data.r_factor}`} />
        )}
        {data.space_group && (
          <Metric icon={Grid3X3} label="Space Group" value={data.space_group} />
        )}
        {data.b_factor_stats && (
          <Metric
            icon={Zap}
            label="B-factor"
            value={`${data.b_factor_stats.mean} (${data.b_factor_stats.min}-${data.b_factor_stats.max})`}
          />
        )}
      </div>

      {/* Unit cell */}
      {data.unit_cell && (
        <div className="px-4 py-3 border-b border-border text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Unit Cell:</span>{' '}
          a={data.unit_cell.a} b={data.unit_cell.b} c={data.unit_cell.c}{' '}
          α={data.unit_cell.alpha}° β={data.unit_cell.beta}° γ={data.unit_cell.gamma}°
        </div>
      )}

      {/* Chains */}
      <div className="p-4 space-y-3">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Chains ({data.chains.length})
        </h4>
        {data.chains.map((chain) => (
          <div
            key={chain.chain_id}
            className="border border-border rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-500/10 text-blue-500 text-xs font-bold">
                  {chain.chain_id}
                </span>
                <span className="text-sm font-medium">
                  Chain {chain.chain_id}
                </span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {chain.residue_count} residues  {chain.atom_count} atoms
                {chain.residue_range && `  (${chain.residue_range[0]}-${chain.residue_range[1]})`}
              </span>
            </div>

            {/* Sequence */}
            <div className="relative">
              <pre className="text-[11px] font-mono bg-secondary rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-24 overflow-y-auto">
                {chain.sequence}
              </pre>
              <button
                onClick={() => copySequence(chain.sequence, chain.chain_id)}
                className="absolute top-1 right-1 p-1 rounded hover:bg-background/50 text-muted-foreground hover:text-foreground transition-colors"
                title="Copy sequence"
              >
                {copiedChain === chain.chain_id ? (
                  <Check className="w-3 h-3 text-green-500" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
      <div className="min-w-0">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
        <p className="text-sm font-medium truncate">{value}</p>
      </div>
    </div>
  )
}

export function isPDBAnalysisResult(data: unknown): data is PDBAnalysisData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return Array.isArray(d.chains) && typeof d.total_atoms === 'number'
}