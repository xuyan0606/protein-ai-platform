import { Link2, Rows3, ShieldAlert } from 'lucide-react'
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

interface MappingRow {
  chain_id: string
  pdb_residue_no: number
  insertion_code?: string | null
  residue_name: string
  residue_aa: string
  uniprot_id?: string | null
  uniprot_position: number
  mapping_confidence?: string | null
}

export interface StructureMappingData {
  found: boolean
  status: string
  source?: string
  mapping_source?: string | null
  uniprot_id?: string | null
  chain_id?: string | null
  uniprot_start?: number
  mapping_count?: number
  mappings: MappingRow[]
  limitations?: string[]
  error?: string
}

export function StructureMappingCard({ data }: { data: StructureMappingData }) {
  const previewRows = data.mappings.slice(0, 8)
  const remaining = Math.max(0, data.mappings.length - previewRows.length)

  return (
    <ReportShell>
      <ReportHeader
        icon={Link2}
        title="Residue Mapping"
        subtitle={`${data.chain_id || 'all chains'} · ${data.source || 'mapping'}`}
        badge={
          <ReportBadge tone={data.found ? 'success' : 'warning'}>
            {data.found ? 'Mapped' : data.status}
          </ReportBadge>
        }
      />
      <ReportBody>
        {data.error ? (
          <ReportPanel tone="danger" className="text-xs text-red-700 dark:text-red-300">
            {data.error}
          </ReportPanel>
        ) : null}

        <ReportSection title="Summary">
          <ReportMetricGrid>
            <ReportMetricCard label="Rows" value={data.mapping_count ?? data.mappings.length} tone="info" />
            <ReportMetricCard label="Chain" value={data.chain_id || 'All'} mono />
            <ReportMetricCard label="UniProt" value={data.uniprot_id || 'Inferred only'} mono />
            <ReportMetricCard
              label="Mode"
              value={data.source === 'local_sifts_mapping' ? 'Curated SIFTS' : 'Inferred'}
              tone={data.source === 'local_sifts_mapping' ? 'success' : 'warning'}
            />
          </ReportMetricGrid>
        </ReportSection>

        <ReportPanel tone={data.source === 'local_sifts_mapping' ? 'success' : 'warning'} className="text-xs leading-6 text-muted-foreground">
          {data.source === 'local_sifts_mapping'
            ? 'Mapping came from local SIFTS-style residue files.'
            : `Mapping is inferred from PDB coordinate order with UniProt start offset ${data.uniprot_start ?? 1}.`}
          {data.mapping_source ? (
            <>
              {' '}Source file: <code className="font-mono">{data.mapping_source}</code>
            </>
          ) : null}
        </ReportPanel>

        {previewRows.length > 0 ? (
          <ReportSection title="Preview Rows" icon={Rows3}>
            <ReportDataTable>
              <thead>
                <tr className="border-b border-border/70 text-left text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Chain</th>
                  <th className="px-4 py-3 font-medium">PDB</th>
                  <th className="px-4 py-3 font-medium">Residue</th>
                  <th className="px-4 py-3 font-medium">UniProt</th>
                  <th className="px-4 py-3 font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row) => (
                  <tr
                    key={`${row.chain_id}-${row.pdb_residue_no}-${row.insertion_code || ''}`}
                    className="border-b border-border/50 last:border-b-0"
                  >
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{row.chain_id}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.pdb_residue_no}
                      {row.insertion_code || ''}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {row.residue_name} ({row.residue_aa})
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {row.uniprot_id ? `${row.uniprot_id}:` : ''}
                      {row.uniprot_position}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {row.mapping_confidence || 'N/A'}
                    </td>
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
        ) : null}

        {data.limitations && data.limitations.length > 0 ? (
          <ReportSection title="Limitations" icon={ShieldAlert}>
            <div className="space-y-2">
              {data.limitations.map((item) => (
                <ReportPanel key={item} tone="warning" className="text-xs leading-6 text-muted-foreground">
                  {item}
                </ReportPanel>
              ))}
            </div>
          </ReportSection>
        ) : null}
      </ReportBody>
    </ReportShell>
  )
}
