import type { BatchCompareData, CompareItem } from './BatchCompare'
import type { BenchmarkData } from './BenchmarkReport'
import type { BlastResult } from './BlastResultView'
import type { CatalyticParamsData } from './CatalyticParamsCard'
import type { CatalyticSiteData } from './CatalyticSiteCard'
import type { ECPredictionData } from './ECPredictionCard'
import type { ESM2ResultData } from './ESM2ResultCard'
import type { InterProAnnotationData } from './InterProAnnotationCard'
import type { MDResultData } from './MDResultView'
import type { MutationScoreData } from './MutationScoreCard'
import type { PDBAnalysisData } from './PDBAnalysisCard'
import type { RFdiffusionData } from './RFdiffusionResult'
import type { SignalPeptideData } from './SignalPeptideCard'
import type { SiteStructureFunctionFeaturesData } from './SiteStructureFunctionFeaturesCard'
import type { StructureMappingData } from './StructureMappingCard'
import type { StructureSearchData } from './StructureSearchResultCard'

export { isAnnotationBundleResult } from './AnnotationBundleResult'

export function isBatchCompareResult(data: unknown): data is BatchCompareData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'title' in d && 'items' in d && Array.isArray(d.items)
}

export function extractBatchCompare(
  items: Array<Record<string, unknown>>,
  title: string = 'Sequence Comparison'
): BatchCompareData | null {
  if (!items || items.length === 0) return null
  const mapped: CompareItem[] = items.map((item, i) => ({
    id: (item.id || item.name || `item-${i}`) as string,
    name: (item.name || item.accession || `Item ${i + 1}`) as string,
    length: (item.length || item.query_length || 0) as number,
    molecular_weight_kda: (item.molecular_weight_kda || 0) as number,
    isoelectric_point: (item.isoelectric_point || 0) as number,
    gravy: (item.gravy || 0) as number,
    identity_to_query: item.identity_to_query as number | undefined,
    stability_score: item.stability_score as number | undefined,
    mutation_count: item.mutation_count as number | undefined,
    notes: item.notes as string | undefined,
  }))
  return { title, items: mapped }
}

export function isBenchmarkResult(data: unknown): data is BenchmarkData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'query_info' in d && 'family' in d && 'benchmark_metrics' in d && 'recommendations' in d
}

export function isBlastResult(data: unknown): data is BlastResult {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'results' in d && 'program' in d && 'database' in d
}

export function isCatalyticParamsResult(data: unknown): data is CatalyticParamsData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'predicted_kcat_s1' in d && 'enzyme_class' in d && 'contributing_factors' in d
}

export function isCatalyticSiteResult(data: unknown): data is CatalyticSiteData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return 'curated_sites' in record && 'inferred_guardrails' in record && 'protected_positions' in record
}

export function isECPredictionResult(data: unknown): data is ECPredictionData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'predictions' in d && 'query_length' in d && 'method' in d
}

export function isESM2Result(data: unknown): data is ESM2ResultData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return ('mutations' in d || 'per_residue' in d || 'embedding_dim' in d) && 'model' in d
}

export function isInterProAnnotationResult(data: unknown): data is InterProAnnotationData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return 'summary' in record && 'annotations' in record
}

export function isMDResult(data: unknown): data is MDResultData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return (
    ('wild_type' in d && ('engine' in d || 'ensemble' in d))
    || 'error_code' in d
    || 'replicate_execution_plan' in d
    || 'batch_replicate_summary' in d
    || d.status === 'failed'
    || d.status === 'planned'
  )
}

export function isMutationScoreResult(data: unknown): data is MutationScoreData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'tier_1_candidates' in d && 'tier_2_candidates' in d && 'summary' in d
}

export function isPDBAnalysisResult(data: unknown): data is PDBAnalysisData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return Array.isArray(d.chains) && typeof d.total_atoms === 'number'
}

export function isRFdiffusionResult(data: unknown): data is RFdiffusionData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return (
    Array.isArray(d.designs) &&
    typeof d.parameters === 'object' &&
    d.parameters !== null &&
    typeof (d.parameters as Record<string, unknown>).symmetry_type === 'string'
  )
}

export function isSignalPeptideResult(data: unknown): data is SignalPeptideData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return 'has_signal_peptide' in record && 'predicted_type' in record && 'regions' in record
}

export function isSiteStructureFunctionFeaturesResult(data: unknown): data is SiteStructureFunctionFeaturesData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return Array.isArray(record.features) && 'feature_count' in record && 'summary' in record
}

export function isStructureMappingResult(data: unknown): data is StructureMappingData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return Array.isArray(record.mappings) && typeof record.status === 'string'
}

export function isStructureSearchResult(data: unknown): data is StructureSearchData {
  if (!data || typeof data !== 'object') return false
  const record = data as Record<string, unknown>
  return Array.isArray(record.results) && 'status' in record && 'query_structure' in record
}
