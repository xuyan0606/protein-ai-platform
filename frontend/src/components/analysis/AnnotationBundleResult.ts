export interface AnnotationBundleData {
  found: boolean
  error?: string
  query?: {
    uniprot_id?: string | null
    sequence_length?: number
    has_curated_enzyme?: boolean
  }
  protein?: {
    uniprot_id?: string | null
    protein_name?: string | null
    gene_name?: string | null
    function_annotation?: string | null
    catalytic_activity?: string | null
    cofactors?: unknown
    ec_numbers?: Array<{
      ec?: string
      name?: string | null
      primary?: boolean
    }>
  }
  coordinate_system?: {
    curated_record?: string | null
    query_record?: string | null
    status?: string
    note?: string
  }
  interpro: unknown
  catalytic_sites: unknown
  signal_peptide: unknown
  note?: string
}

export function isAnnotationBundleResult(data: unknown): data is AnnotationBundleData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return (
    typeof record.found === 'boolean'
    && 'interpro' in record
    && 'catalytic_sites' in record
    && 'signal_peptide' in record
  )
}
