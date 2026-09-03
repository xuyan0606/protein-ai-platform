import { Activity, MapPinned, ShieldAlert, Table2 } from 'lucide-react'
import {
  ReportBadge,
  ReportBody,
  ReportDataTable,
  ReportHeader,
  ReportMetricCard,
  ReportMetricGrid,
  ReportPanel,
  ReportSection,
  ReportShell,
} from '@/components/analysis/ReportShell'

interface SiteFeatureCoord {
  x: number
  y: number
  z: number
}

interface SiteFeatureRow {
  position: number
  position_source?: string
  wild_type?: string
  chain_id?: string
  pdb_position?: string
  pdb_residue_no?: number
  uniprot_position?: number | null
  has_ca?: boolean
  ca_coord?: SiteFeatureCoord | null
  b_factor?: number | null
  nearest_catalytic_distance_ca_angstrom?: number | null
  nearest_catalytic_position?: number | null
  nearest_ca_neighbor_distance_angstrom?: number | null
  nearest_ca_neighbor_position?: number | null
  nearest_ca_neighbor_pdb_position?: string | null
  contact_count_ca_8a?: number
  ca_contact_environment?: string
  secondary_structure?: string
  secondary_structure_source?: string
  rel_sasa?: number | null
  residue_sasa_angstrom2?: number | null
  rel_sasa_status?: string
  pocket_channel_interface_status?: string
  nonpolymer_proximity_status?: string
  nearest_nonpolymer_heteroatom_distance_angstrom?: number | null
  nearest_nonpolymer_component_id?: string | null
  nearest_nonpolymer_component_position?: string | null
  nonpolymer_component_ids_within_4a?: string[]
  phi_deg?: number | null
  psi_deg?: number | null
  backbone_torsion_status?: string
  backbone_torsion_reason?: string
  is_catalytic?: boolean
  is_protected?: boolean
  risk_flags?: string[]
}

interface SiteFeatureSummary {
  residue_count?: number
  feature_count?: number
  mapped_count?: number
  ca_available_count?: number
  protected_count?: number
  secondary_structure_source?: string
  rel_sasa_status?: string
  pocket_channel_interface_status?: string
  nonpolymer_proximity_status?: string
  nonpolymer_component_count?: number
  nonpolymer_heavy_atom_count?: number
  nonpolymer_component_ids?: string[]
  backbone_torsion_status?: string
  distance_graph_status?: string
  distance_graph_node_count?: number
  distance_graph_edge_count?: number
  distance_graph_radius_angstrom?: number
}

interface FeatureTableContract {
  schema_version?: string
  status?: string
  field_state?: Record<string, string>
  unknown_fields?: string[]
  must_not_claim?: string[]
  blocked_reasons?: string[]
}

interface ResidueDistanceGraph {
  schema_version?: string
  status?: string
  coordinate_basis?: string
  radius_angstrom?: number
  node_count?: number
  edge_count?: number
  boundary?: string
}

export interface SiteStructureFunctionFeaturesData {
  found: boolean
  status: string
  source?: string
  capability_status?: string
  evidence_level?: string
  report_boundary?: string
  chain_id?: string | null
  contact_radius_angstrom?: number
  feature_count?: number
  summary?: SiteFeatureSummary
  feature_table_contract?: FeatureTableContract
  residue_distance_graph?: ResidueDistanceGraph
  features: SiteFeatureRow[]
}

function formatCoord(coord?: SiteFeatureCoord | null): string {
  if (!coord) return 'No CA'
  return `${coord.x}, ${coord.y}, ${coord.z}`
}

function formatRisk(row: SiteFeatureRow): string {
  if (row.risk_flags && row.risk_flags.length > 0) {
    return row.risk_flags.slice(0, 2).join('; ')
  }
  if (row.is_protected) return 'protected position'
  return 'review'
}

export function SiteStructureFunctionFeaturesCard({ data }: { data: SiteStructureFunctionFeaturesData }) {
  const summary = data.summary || {}
  const contract = data.feature_table_contract
  const fieldState = contract?.field_state || {}
  const contractMustNotClaim = contract?.must_not_claim || []
  const distanceGraph = data.residue_distance_graph
  const previewRows = data.features.slice(0, 10)
  const remaining = Math.max(0, data.features.length - previewRows.length)

  return (
    <ReportShell>
      <ReportHeader
        icon={Activity}
        title="Site Structure Features"
        subtitle={`${data.chain_id || 'chain auto'} · ${data.source || 'PDB CA geometry'}`}
        badge={
          <ReportBadge tone={data.found ? 'success' : 'warning'}>
            {data.found ? 'Ready' : data.status}
          </ReportBadge>
        }
      />
      <ReportBody>
        <ReportSection title="Summary" icon={MapPinned}>
          <ReportMetricGrid>
            <ReportMetricCard label="Features" value={data.feature_count ?? summary.feature_count ?? data.features.length} tone="info" />
            <ReportMetricCard label="Mapped" value={summary.mapped_count ?? '-'} tone="success" />
            <ReportMetricCard label="CA Available" value={summary.ca_available_count ?? '-'} />
            <ReportMetricCard label="Protected" value={summary.protected_count ?? 0} tone={summary.protected_count ? 'warning' : 'neutral'} />
            <ReportMetricCard label="Non-polymer" value={summary.nonpolymer_component_count ?? 0} tone={summary.nonpolymer_component_count ? 'info' : 'neutral'} />
            <ReportMetricCard label="Distance Edges" value={summary.distance_graph_edge_count ?? distanceGraph?.edge_count ?? 0} tone={summary.distance_graph_edge_count ? 'info' : 'neutral'} />
          </ReportMetricGrid>
        </ReportSection>

        {distanceGraph ? (
          <ReportSection title="Distance Graph" icon={MapPinned}>
            <ReportPanel tone={distanceGraph.status === 'ready' ? 'info' : 'warning'} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ReportBadge tone={distanceGraph.status === 'ready' ? 'success' : 'warning'}>
                  {distanceGraph.status || 'unknown'}
                </ReportBadge>
                <span className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                  nodes: <span className="font-mono text-foreground">{distanceGraph.node_count ?? 0}</span>
                </span>
                <span className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                  edges: <span className="font-mono text-foreground">{distanceGraph.edge_count ?? 0}</span>
                </span>
                <span className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                  radius: <span className="font-mono text-foreground">{distanceGraph.radius_angstrom ?? data.contact_radius_angstrom ?? '-'} A</span>
                </span>
              </div>
              {distanceGraph.boundary ? (
                <div className="text-[11px] leading-5 text-muted-foreground">{distanceGraph.boundary}</div>
              ) : null}
            </ReportPanel>
          </ReportSection>
        ) : null}

        {contract ? (
          <ReportSection title="Feature Contract" icon={ShieldAlert}>
            <ReportPanel tone={contract.status === 'ready' ? 'info' : 'warning'} className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <ReportBadge tone={contract.status === 'ready' ? 'success' : 'warning'}>
                  {contract.status || 'unknown'}
                </ReportBadge>
                {Object.entries(fieldState).map(([key, value]) => (
                  <span key={key} className="rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground">
                    {key}: <span className="font-mono text-foreground">{value}</span>
                  </span>
                ))}
              </div>
              {contractMustNotClaim.length > 0 ? (
                <div className="text-[11px] leading-5 text-muted-foreground">
                  Must not claim: {contractMustNotClaim.slice(0, 4).join(', ')}
                </div>
              ) : null}
            </ReportPanel>
          </ReportSection>
        ) : null}

        {data.report_boundary ? (
          <ReportPanel tone="warning" className="text-xs leading-6 text-muted-foreground">
            {data.report_boundary}
          </ReportPanel>
        ) : null}

        {previewRows.length > 0 ? (
          <ReportSection title="Feature Preview" icon={Table2}>
            <ReportDataTable>
              <thead>
                <tr className="border-b border-border/70 text-left text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Site</th>
                  <th className="px-4 py-3 font-medium">PDB</th>
                  <th className="px-4 py-3 font-medium">CA</th>
                  <th className="px-4 py-3 font-medium">B-factor</th>
                  <th className="px-4 py-3 font-medium">relSASA</th>
                  <th className="px-4 py-3 font-medium">Cat Dist</th>
                  <th className="px-4 py-3 font-medium">Nearest CA</th>
                  <th className="px-4 py-3 font-medium">Non-polymer</th>
                  <th className="px-4 py-3 font-medium">Phi/Psi</th>
                  <th className="px-4 py-3 font-medium">8A Contacts</th>
                  <th className="px-4 py-3 font-medium">CA Env</th>
                  <th className="px-4 py-3 font-medium">Sec Struct</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row, index) => (
                  <tr key={`${row.chain_id || 'chain'}-${row.pdb_position || row.position}-${index}`} className="border-b border-border/50 last:border-b-0">
                    <td className="px-4 py-3 text-xs font-mono">
                      {row.wild_type || '-'}
                      {row.position}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{row.pdb_position || row.pdb_residue_no || '-'}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{formatCoord(row.ca_coord)}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{row.b_factor ?? '-'}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.rel_sasa ?? row.rel_sasa_status ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.nearest_catalytic_distance_ca_angstrom ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.nearest_ca_neighbor_distance_angstrom != null
                        ? `${row.nearest_ca_neighbor_position ?? row.nearest_ca_neighbor_pdb_position ?? '?'} (${row.nearest_ca_neighbor_distance_angstrom})`
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.nearest_nonpolymer_heteroatom_distance_angstrom ?? '-'}
                      {row.nearest_nonpolymer_component_id ? ` ${row.nearest_nonpolymer_component_id}` : ''}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.phi_deg ?? '-'}/{row.psi_deg ?? '-'}
                      <span className="ml-1 text-[10px]">{row.backbone_torsion_status || 'not_computed'}</span>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{row.contact_count_ca_8a ?? 0}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{row.ca_contact_environment || '-'}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{row.secondary_structure || 'unknown'}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatRisk(row)}</td>
                  </tr>
                ))}
              </tbody>
            </ReportDataTable>
            {remaining > 0 ? (
              <div className="text-xs text-muted-foreground">
                {remaining} more rows omitted from the preview.
              </div>
            ) : null}
          </ReportSection>
        ) : (
          <ReportSection title="Feature Preview" icon={ShieldAlert}>
            <ReportPanel tone="warning" className="text-xs text-muted-foreground">
              No residue-level CA feature rows were returned.
            </ReportPanel>
          </ReportSection>
        )}
      </ReportBody>
    </ReportShell>
  )
}
