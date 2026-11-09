import { useState, useEffect, useCallback, useRef, useMemo, type ReactNode } from 'react'
import { Search, Database, Beaker, Dna, Microscope, FlaskConical, Loader2, X, BarChart3, ShieldCheck, AlertTriangle, CheckCircle2, Activity, HardDrive, Server, ArrowLeft, Layers3, Download, ClipboardList, type LucideIcon } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import SmilesDrawerNS from 'smiles-drawer'
import { api, getAccessToken, type ApiRecord, type DataSearchResponse, type DataStats, type DeployDataReadiness, type EnzymeDbFamily, type EnzymeDbPolicyDecisionPreview, type EnzymeMetadataCurationBatch, type EnzymeMetadataCurationList, type EnzymeMetadataCurationMaterializeResult, type ExperimentFeedbackIterationPlan, type ExperimentFeedbackRecord, type ExperimentFeedbackSummary, type LipaseDbStatus, type LipaseGapList, type LipasePaperDetail, type LipasePaperList, type LipaseSearchResult, type LipaseVariantList, type MutationEpistasisCheckResult, type OpsSummary, type ProjectListItem, type ToolCapabilityAudit } from '../lib/api'
import { downloadReport } from '../lib/report'
import { useAuthStore } from '../stores/auth'

type Tab = 'search' | 'substrates' | 'enzymes' | 'lipase' | 'feedback' | 'capabilities' | 'readiness' | 'ops' | 'stats'
type DetailTab = 'overview' | 'kinetics' | 'stability' | 'structures' | 'evolution'
type IconComponent = LucideIcon
type StatItem = readonly [string, number | undefined, IconComponent]
type TabItem = readonly [Tab, string, IconComponent]

const DATA_TABS = new Set<Tab>(['search', 'substrates', 'enzymes', 'lipase', 'feedback', 'capabilities', 'readiness', 'ops', 'stats'])

function initialDataTab(): Tab {
  if (typeof window === 'undefined') return 'search'
  const requested = new URLSearchParams(window.location.search).get('tab') as Tab | null
  return requested && DATA_TABS.has(requested) ? requested : 'search'
}

type SelectedProtein = {
  uniprot_id: string
}

type ProteinDetailData = ApiRecord & {
  uniprot_id?: string
  protein_name?: string | null
  entry_name?: string | null
  gene_name?: string | null
  seq_length?: number | null
  organism?: { name?: string | null; lineage?: string | null }
  ec_numbers?: Array<{ ec: string; name?: string | null; primary?: boolean }>
  function?: string | null
  catalytic_activity?: string | null
  cofactors?: string[] | string | null
  alphafold?: { plddt_mean?: number | null }
  sequence?: string | null
  kinetics?: KineticsData
  stability?: StabilityData
  structures?: StructureData
  evolution?: EvolutionData
}

type KineticsData = {
  parameters?: KineticParam[]
}

type KineticParam = {
  type?: string
  value?: string | number
  unit?: string
  source?: string
  substrate?: string
  ph?: string | number
  temp_c?: string | number
  mutant?: string
  organism?: string
}

type StabilityData = {
  records?: StabilityRecord[]
}

type StabilityRecord = {
  mutation?: string
  wt?: string
  mt?: string
  position?: number
  ddg?: number | null
  dtm?: number | null
  ph?: string | number | null
  method?: string | null
}

type StructureData = {
  pdb?: PdbStructure[]
  alphafold?: AlphaFoldStructure[]
}

type PdbStructure = {
  pdb_id: string
  method?: string | null
  resolution?: number | null
  title?: string | null
}

type AlphaFoldStructure = {
  plddt_mean?: number | null
  plddt_scores?: number[]
}

type EvolutionData = {
  experiments?: EvolutionExperiment[]
}

type EvolutionExperiment = {
  method?: string
  rounds?: number
  fold_improvement?: number
  selection?: string
  library_size?: string | number
  metric?: string
  best_variant?: string
}

type SubstrateCompound = {
  cid?: string | number
  name?: string
  iupac?: string
  formula?: string
  weight?: string | number
  xlogp?: string | number
  tpsa?: string | number
  inchikey?: string
  smiles?: string
}

type SubstrateSearchResult = ApiRecord & {
  compound?: SubstrateCompound
  results?: SubstrateCompound[]
}

type SimpleEnzymeFamilyStatus = {
  family: string
  label?: string
  status?: string
  read_only?: boolean
  path?: { exists?: boolean; size_bytes?: number; updated_at?: string | null }
  tables?: Record<string, number>
  missing_tables?: string[]
  metadata_policy_decisions?: {
    status?: string
    manifest_count?: number
    decision_count?: number
    record_types?: string[]
    review_statuses?: string[]
    manifests?: Array<Record<string, unknown>>
    errors?: Array<Record<string, unknown>>
  }
  quality?: { integrity_check?: string; ready_for_query?: boolean }
  metadata_quality?: {
    missing_doi?: number
    missing_pmid?: number
    patent_like_sources?: number
    preprint_papers?: number
    boundary_papers?: number
    boundary_measurements?: number
    policy_excluded_papers?: number
    policy_excluded_measurements?: number
    non_exportable_markers?: string[]
    export_policy?: {
      browser_scope?: string
      export_scope?: string
      patent_metadata?: string
      preprint_version_of_record?: string
      blocked_markers?: string[]
    }
    hold_papers?: number
    hold_measurements?: number
    export_safe_measurements?: number
    metadata_gap_count?: number
    browser_scope?: string
  }
}

type SimpleEnzymeFamiliesResponse = {
  status?: string
  read_only?: boolean
  families?: SimpleEnzymeFamilyStatus[]
}

type SimpleEnzymeRowResponse = {
  status?: string
  family?: string
  count?: number
  papers?: Array<Record<string, unknown>>
  variants?: Array<Record<string, unknown>>
  measurements?: Array<Record<string, unknown>>
  path?: SimpleEnzymeFamilyStatus['path']
  policy?: string
}

export default function DataBrowser() {
  const [tab, setTab] = useState<Tab>(initialDataTab)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [results, setResults] = useState<DataSearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<DataStats | null>(null)
  const [readiness, setReadiness] = useState<DeployDataReadiness | null>(null)
  const [toolCapabilities, setToolCapabilities] = useState<ToolCapabilityAudit | null>(null)
  const [lipaseStatus, setLipaseStatus] = useState<LipaseDbStatus | null>(null)
  const [enzymeFamilies, setEnzymeFamilies] = useState<SimpleEnzymeFamiliesResponse | null>(null)
  const [enzymeFamiliesLoading, setEnzymeFamiliesLoading] = useState(true)
  const [enzymeFamiliesError, setEnzymeFamiliesError] = useState<string | null>(null)
  const [opsSummary, setOpsSummary] = useState<OpsSummary | null>(null)
  const [selectedProtein, setSelectedProtein] = useState<SelectedProtein | null>(null)
  const [proteinDetail, setProteinDetail] = useState<ProteinDetailData | null>(null)
  const [proteinError, setProteinError] = useState(false)
  const [detailTab, setDetailTab] = useState<DetailTab>('overview')
  const statItems: StatItem[] = [
    ['酶蛋白', stats?.counts?.enzyme_records, Dna],
    ['EC分类', stats?.counts?.ec_numbers, Microscope],
    ['PDB结构', stats?.counts?.pdb_structures, Database],
    ['动力学', stats?.counts?.kinetic_parameters, BarChart3],
    ['稳定性', stats?.counts?.stability_records, FlaskConical],
    ['底物', stats?.counts?.substrate_compounds, Beaker],
    ['反应', stats?.counts?.reaction_equations, Search],
  ]
  const tabItems: TabItem[] = [
    ['search', '搜索', Search],
    ['substrates', '底物', Beaker],
    ['enzymes', '酶库', Layers3],
    ['lipase', '脂肪酶库', Database],
    ['feedback', '实验反馈', FlaskConical],
    ['capabilities', '能力边界', ShieldCheck],
    ['readiness', '就绪度', ShieldCheck],
    ['ops', '监控', Activity],
    ['stats', '统计', BarChart3],
  ]

  const selectTab = (nextTab: Tab) => {
    setTab(nextTab)
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    url.searchParams.set('tab', nextTab)
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }

  const loadEnzymeFamilies = useCallback(async () => {
    setEnzymeFamiliesLoading(true)
    setEnzymeFamiliesError(null)
    try {
      setEnzymeFamilies(await api.getEnzymeDbStatus())
    } catch (reason) {
      setEnzymeFamilies(null)
      setEnzymeFamiliesError(reason instanceof Error ? reason.message : '加载酶库目录失败')
    } finally {
      setEnzymeFamiliesLoading(false)
    }
  }, [])

  useEffect(() => {
    api.getDataStats().then(setStats).catch(() => {})
    api.getDataReadiness().then(setReadiness).catch(() => {})
    api.getToolCapabilities().then(setToolCapabilities).catch(() => {})
    api.getLipaseDbStatus().then(setLipaseStatus).catch(() => {})
    queueMicrotask(() => { void loadEnzymeFamilies() })
    if (getAccessToken()) {
      api.getOpsSummary().then(setOpsSummary).catch(() => {})
    }
  }, [loadEnzymeFamilies])

  const doSearch = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setSelectedProtein(null)
    setProteinDetail(null)
    try {
      const data = await api.searchData(query, category || undefined)
      setResults(data)
    } catch { setResults(null) }
    setLoading(false)
  }, [query, category])

  const selectProtein = async (uniprotId: string) => {
    setSelectedProtein({ uniprot_id: uniprotId })
    setProteinDetail(null)
    setProteinError(false)
    setDetailTab('overview')
    try {
      const [detail, kinetics, stability, structures, evolution] = await Promise.all([
        api.getProtein(uniprotId),
        api.getProteinKinetics(uniprotId),
        api.getProteinStability(uniprotId),
        api.getProteinStructures(uniprotId),
        api.getProteinEvolution(uniprotId),
      ])
      setProteinDetail({ ...detail, kinetics, stability, structures, evolution })
    } catch {
      setProteinError(true)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <a
            href="/chat/agent"
            className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            返回 Agent
          </a>
          <Database className="w-6 h-6 text-blue-600" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">数据浏览器</h1>
          <span className="text-sm text-gray-500 ml-2">
            UniProt · PDB · BRENDA · ProThermDB · PubChem · Rhea · EnzEngDB
          </span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats bar */}
        <div className="grid grid-cols-4 md:grid-cols-7 gap-3 mb-6">
          {statItems.map(([label, count, Icon]) => (
              <div key={label} className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                <Icon className="w-4 h-4 mx-auto mb-1 text-blue-500" />
                <div className="text-lg font-bold text-gray-900 dark:text-white">
                  {stats?.counts ? (count ?? 0) : <span className="mx-auto block h-6 w-10 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />}
                </div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
          ))}
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
          {tabItems.map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => selectTab(key)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Search tab */}
        {tab === 'search' && (
          <div className="flex gap-6">
            {/* Left: search + results */}
            <div className={`flex-1 min-w-0 ${selectedProtein ? 'max-w-md' : ''}`}>
              <div className="flex gap-2 mb-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                  <input
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && doSearch()}
                    placeholder="搜索蛋白质、EC编号、底物、反应..."
                    className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
                >
                  <option value="">全部</option>
                  <option value="protein">蛋白质</option>
                  <option value="substrate">底物</option>
                  <option value="ec">EC分类</option>
                  <option value="reaction">反应</option>
                </select>
                <button
                  onClick={doSearch}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : '搜索'}
                </button>
              </div>

              {/* Results */}
              {results && (
                <div className="space-y-4">
                  {(results.results?.proteins || []).length > 0 && (
                    <Section title="蛋白质" icon={Dna} count={(results.results?.proteins || []).length}>
                      {(results.results?.proteins || []).map((p) => (
                        <ResultRow key={p.uniprot_id} onClick={() => selectProtein(p.uniprot_id)}>
                          <span className="font-mono text-blue-600 dark:text-blue-400 text-sm">
                            <Highlight text={p.uniprot_id} query={query} />
                          </span>
                          <span className="text-sm text-gray-700 dark:text-gray-300 ml-3">
                            <Highlight text={p.name || p.gene || ''} query={query} />
                          </span>
                          {p.gene && <span className="text-xs text-gray-400 ml-2">(<Highlight text={p.gene} query={query} />)</span>}
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {(results.results?.substrates || []).length > 0 && (
                    <Section title="底物化合物" icon={Beaker} count={(results.results?.substrates || []).length}>
                      {(results.results?.substrates || []).map((s) => (
                        <ResultRow key={s.cid}>
                          <span className="text-sm font-medium"><Highlight text={s.name || ''} query={query} /></span>
                          <span className="text-xs text-gray-400 ml-2">{s.formula}</span>
                          <span className="text-xs font-mono text-gray-400 ml-2">CID:{s.cid}</span>
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {(results.results?.ec_numbers || []).length > 0 && (
                    <Section title="EC分类" icon={Microscope} count={(results.results?.ec_numbers || []).length}>
                      {(results.results?.ec_numbers || []).map((ec) => (
                        <ResultRow key={ec.ec}>
                          <span className="font-mono text-green-600 dark:text-green-400 text-sm">
                            <Highlight text={ec.ec} query={query} />
                          </span>
                          <span className="text-sm text-gray-700 dark:text-gray-300 ml-3">
                            <Highlight text={ec.name || ''} query={query} />
                          </span>
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {(results.results?.reactions || []).length > 0 && (
                    <Section title="反应方程" icon={FlaskConical} count={(results.results?.reactions || []).length}>
                      {(results.results?.reactions || []).map((r) => (
                        <ResultRow key={r.rhea_id}>
                          <span className="font-mono text-purple-600 text-sm">RHEA:{r.rhea_id}</span>
                          <span className="text-sm text-gray-600 dark:text-gray-400 ml-3 truncate max-w-md">
                            <Highlight text={r.equation || ''} query={query} />
                          </span>
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {Object.values(results.results || {}).flat().length === 0 && (
                    <div className="text-center py-12 text-gray-400">
                      <Search className="w-8 h-8 mx-auto mb-2" />
                      无结果
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right: protein detail panel */}
            {selectedProtein && (
              <div className="w-[520px] flex-shrink-0">
                <ProteinDetail
                  detail={proteinDetail}
                  error={proteinError}
                  selected={selectedProtein}
                  detailTab={detailTab}
                  setDetailTab={setDetailTab}
                  onClose={() => { setSelectedProtein(null); setProteinDetail(null); setProteinError(false) }}
                />
              </div>
            )}
          </div>
        )}

        {/* Substrates tab */}
        {tab === 'substrates' && <SubstrateBrowser />}

        {/* Lipase evidence tab */}
        {tab === 'enzymes' && (
          <SimpleEnzymeDbBrowser
            families={enzymeFamilies?.families || []}
            familiesLoading={enzymeFamiliesLoading}
            familiesError={enzymeFamiliesError}
            onRetryFamilies={() => { void loadEnzymeFamilies() }}
          />
        )}

        {/* Lipase evidence tab */}
        {tab === 'lipase' && <LipaseEvidenceBrowser status={lipaseStatus} />}

        {/* Experiment feedback tab */}
        {tab === 'feedback' && <ExperimentFeedbackPanel />}

        {/* Tool capability boundary tab */}
        {tab === 'capabilities' && <ToolCapabilitiesPanel audit={toolCapabilities} />}

        {/* Readiness tab */}
        {tab === 'readiness' && <ReadinessPanel readiness={readiness} lipaseStatus={lipaseStatus} />}

        {/* Ops tab */}
        {tab === 'ops' && <OpsPanel opsSummary={opsSummary} />}

        {/* Stats tab */}
        {tab === 'stats' && <StatsPanel stats={stats} />}
      </div>
    </div>
  )
}

// ============================================================================
// Sub-components
// ============================================================================

function Section({
  title,
  icon: Icon,
  count,
  children,
}: {
  title: string
  icon?: IconComponent
  count: number
  children: ReactNode
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-gray-500" />}
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{title}</span>
        <span className="text-xs text-gray-400">({count})</span>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-750">{children}</div>
    </div>
  )
}

function ResultRow({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      className={`px-4 py-2.5 flex items-center hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
    >
      {children}
    </div>
  )
}

function ProteinDetail({
  detail,
  error,
  selected,
  detailTab,
  setDetailTab,
  onClose,
}: {
  detail: ProteinDetailData | null
  error: boolean
  selected: SelectedProtein
  detailTab: DetailTab
  setDetailTab: (tab: DetailTab) => void
  onClose: () => void
}) {
  if (!detail) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 sticky top-6">
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-blue-600 font-medium">{selected.uniprot_id}</span>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><X className="w-4 h-4" /></button>
        </div>
        {error ? (
          <div className="text-center py-8">
            <X className="w-5 h-5 mx-auto mb-2 text-red-400" />
            <div className="text-sm text-red-500">加载失败，请检查网络连接</div>
          </div>
        ) : (
          <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
        )}
      </div>
    )
  }

  const tabs: Array<readonly [DetailTab, string]> = [
    ['overview', '概览'],
    ['kinetics', '动力学'],
    ['stability', '稳定性'],
    ['structures', '结构'],
    ['evolution', '进化'],
  ]

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 sticky top-6 max-h-[calc(100vh-120px)] overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between sticky top-0 bg-white dark:bg-gray-800 z-10">
        <div>
          <div className="font-mono text-blue-600 dark:text-blue-400 font-bold">{detail.uniprot_id}</div>
          <div className="text-sm font-medium text-gray-900 dark:text-white mt-0.5">{detail.protein_name || detail.entry_name}</div>
          {detail.gene_name && <div className="text-xs text-gray-500">基因：{detail.gene_name}</div>}
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><X className="w-4 h-4" /></button>
      </div>

      {/* Tab row */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 px-2">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setDetailTab(key)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              detailTab === key ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {detailTab === 'overview' && <OverviewTab detail={detail} />}
        {detailTab === 'kinetics' && <KineticsTab data={detail.kinetics} />}
        {detailTab === 'stability' && <StabilityTab data={detail.stability} />}
        {detailTab === 'structures' && <StructuresTab data={detail.structures} />}
        {detailTab === 'evolution' && <EvolutionTab data={detail.evolution} />}
      </div>
    </div>
  )
}

function OverviewTab({ detail }: { detail: ProteinDetailData }) {
  return (
    <div className="space-y-4 text-sm">
      <KV label="条目名称" value={detail.entry_name} />
      <KV label="序列长度" value={`${detail.seq_length} aa`} />
      <KV label="生物体" value={detail.organism?.name} />
      {detail.organism?.lineage && <KV label="分类谱系" value={detail.organism.lineage} />}
      <KV label="EC编号" value={detail.ec_numbers?.map((ec) => `${ec.ec} (${ec.name || ''})${ec.primary ? ' ★' : ''}`).join(', ')} />
      {detail.function && (
        <div>
          <div className="text-xs font-medium text-gray-500 mb-1">功能</div>
          <div className="text-gray-700 dark:text-gray-300 leading-relaxed">{detail.function}</div>
        </div>
      )}
      {detail.catalytic_activity && (
        <div>
          <div className="text-xs font-medium text-gray-500 mb-1">催化活性</div>
          <div className="text-gray-700 dark:text-gray-300">{detail.catalytic_activity}</div>
        </div>
      )}
      {detail.cofactors && (
        <KV label="辅因子" value={Array.isArray(detail.cofactors) ? detail.cofactors.join(', ') : detail.cofactors} />
      )}
      {detail.alphafold && (
        <KV label="AlphaFold pLDDT" value={detail.alphafold.plddt_mean?.toFixed(1)} />
      )}
      <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
        <div className="text-xs text-gray-500">序列</div>
        <div className="mt-1 font-mono text-xs text-gray-600 dark:text-gray-400 break-all leading-relaxed max-h-32 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-2 rounded">
          {detail.sequence}
        </div>
      </div>
    </div>
  )
}

function KineticsTab({ data }: { data?: KineticsData }) {
  const params = data?.parameters || []
  if (!params.length) return <Empty text="无动力学数据" />
  return (
    <div className="space-y-2">
      {params.map((p, i) => (
        <div key={i} className="bg-gray-50 dark:bg-gray-750 rounded p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-blue-600">{p.type}</span>
            <span className="font-bold">{p.value}</span>
            <span className="text-gray-500">{p.unit}</span>
            <span className="text-xs bg-gray-200 dark:bg-gray-600 px-1.5 py-0.5 rounded">{p.source}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {p.substrate && <>底物: {p.substrate} · </>}
            {p.ph && <>pH {p.ph} · </>}
            {p.temp_c && <>{p.temp_c}°C · </>}
            {p.mutant && <>突变体: {p.mutant}</>}
            {p.organism && <> · {p.organism}</>}
          </div>
        </div>
      ))}
    </div>
  )
}

function StabilityTab({ data }: { data?: StabilityData }) {
  const records = data?.records || []
  if (!records.length) return <Empty text="无稳定性数据" />
  return (
    <div className="space-y-2">
      {records.map((r, i) => (
        <div key={i} className={`bg-gray-50 dark:bg-gray-750 rounded p-3 text-sm border-l-2 ${typeof r.ddg === 'number' && r.ddg > 0 ? 'border-red-400' : 'border-green-400'}`}>
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold">{r.mutation}</span>
            <span className="text-gray-500">({r.wt}→{r.mt} @ {r.position})</span>
          </div>
          <div className="flex gap-4 mt-1 text-xs">
            {r.ddg != null && <span className={r.ddg > 0 ? 'text-red-500' : 'text-green-500'}>ΔΔG: {r.ddg} kcal/mol</span>}
            {r.dtm != null && <span>ΔTm: {r.dtm}°C</span>}
            {r.ph != null && <span className="text-gray-500">pH {r.ph}</span>}
            {r.method && <span className="text-gray-400">{r.method}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function StructuresTab({ data }: { data?: StructureData }) {
  const pdb = data?.pdb || []
  const af = data?.alphafold || []
  return (
    <div className="space-y-4">
      {pdb.length > 0 && (
        <div>
          <div className="text-sm font-medium mb-2">PDB 实验结构 ({pdb.length})</div>
          <div className="space-y-2">
            {pdb.map((s) => (
              <div key={s.pdb_id} className="bg-gray-50 dark:bg-gray-750 rounded p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-green-600">{s.pdb_id}</span>
                  <span className="text-xs bg-gray-200 dark:bg-gray-600 px-1 rounded">{s.method || '?'}</span>
                  {s.resolution && <span className="text-xs text-gray-500">{s.resolution}Å</span>}
                </div>
                {s.title && <div className="text-xs text-gray-500 mt-1 truncate">{s.title}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
      {af.map((s) => (
        <div key="af">
          <div className="text-sm font-medium mb-2">AlphaFold 预测结构</div>
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-3 text-sm">
            <span>pLDDT: <strong>{s.plddt_mean?.toFixed(1)}</strong></span>
          </div>
          {(s.plddt_scores || []).length > 0 && (
            <div className="mt-3">
              <AlphaFoldChart scores={s.plddt_scores || []} />
            </div>
          )}
        </div>
      ))}
      {!pdb.length && !af.length && <Empty text="无结构数据" />}
    </div>
  )
}

function EvolutionTab({ data }: { data?: EvolutionData }) {
  const exps = data?.experiments || []
  if (!exps.length) return <Empty text="无定向进化数据" />
  return (
    <div className="space-y-2">
      {exps.map((e, i) => (
        <div key={i} className="bg-gray-50 dark:bg-gray-750 rounded p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium">{e.method}</span>
            {e.rounds && <span className="text-xs text-gray-500">{e.rounds}轮</span>}
            {e.fold_improvement && (
              <span className="text-xs bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400 px-1.5 py-0.5 rounded font-bold">
                {e.fold_improvement}x
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {e.selection && <>筛选: {e.selection} · </>}
            {e.library_size && <>文库大小: {e.library_size} · </>}
            {e.metric && <>指标: {e.metric}</>}
          </div>
          {e.best_variant && <div className="text-xs mt-1 font-mono text-gray-600 dark:text-gray-400">最优: {e.best_variant}</div>}
        </div>
      ))}
    </div>
  )
}

function SubstrateBrowser() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SubstrateSearchResult | null>(null)
  const [loading, setLoading] = useState(false)

  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    try { setResults(await api.searchSubstrate(q)) } catch { setResults(null) }
    setLoading(false)
  }

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="搜索化合物名称（如 ATP、glucose）或 CID..."
          className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
        />
        <button onClick={search} disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : '搜索'}
        </button>
      </div>

      {results && (
        <div className="space-y-4">
          {(results.compound ? [results.compound] : results.results || []).map((c) => (
            <article
              key={c.cid || c.name}
              className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 md:p-6 text-sm shadow-sm"
            >
              <div className="flex flex-col gap-5 lg:grid lg:grid-cols-[minmax(0,1.2fr)_360px] lg:items-start">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-white">
                      {c.name || c.cid}
                    </h3>
                    {c.cid && (
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
                        PubChem CID {c.cid}
                      </span>
                    )}
                  </div>

                  {c.iupac && (
                    <div className="mt-3 rounded-xl bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-600 dark:bg-gray-900 dark:text-gray-300 break-words">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">
                        IUPAC
                      </div>
                      <div>{c.iupac}</div>
                    </div>
                  )}

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <InfoBlock label="分子式" value={c.formula} mono />
                    <InfoBlock label="分子量" value={c.weight != null ? `${c.weight}` : undefined} />
                    <InfoBlock label="LogP" value={c.xlogp != null ? `${c.xlogp}` : undefined} />
                    <InfoBlock label="TPSA" value={c.tpsa != null ? `${c.tpsa}` : undefined} />
                    <InfoBlock label="InChIKey" value={c.inchikey} mono />
                  </div>

                  {c.smiles && (
                    <div className="mt-4 rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">
                        SMILES
                      </div>
                      <div className="font-mono text-xs leading-6 text-gray-600 dark:text-gray-300 break-all">
                        {c.smiles}
                      </div>
                    </div>
                  )}
                </div>

                {c.smiles && (
                  <div className="lg:sticky lg:top-6">
                    <MoleculeCard cid={c.cid} smiles={c.smiles} name={String(c.name || c.cid || '')} />
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

function SimpleEnzymeDbBrowser({
  families,
  familiesLoading,
  familiesError,
  onRetryFamilies,
}: {
  families: SimpleEnzymeFamilyStatus[]
  familiesLoading: boolean
  familiesError: string | null
  onRetryFamilies: () => void
}) {
  const currentUser = useAuthStore((state) => state.user)
  const [family, setFamily] = useState<EnzymeDbFamily | ''>('')
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState<SimpleEnzymeRowResponse | null>(null)
  const [variants, setVariants] = useState<SimpleEnzymeRowResponse | null>(null)
  const [measurements, setMeasurements] = useState<SimpleEnzymeRowResponse | null>(null)
  const [policyPreview, setPolicyPreview] = useState<EnzymeDbPolicyDecisionPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [policyPreviewLoading, setPolicyPreviewLoading] = useState(false)
  const [policyPreviewError, setPolicyPreviewError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const first = families[0]
    if (!first || family) return
    queueMicrotask(() => setFamily(first.family as EnzymeDbFamily))
  }, [families, family])

  useEffect(() => {
    if (!family) return
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setError(null)
      setPolicyPreview(null)
      setPolicyPreviewError(null)
      setPapers(null)
      setVariants(null)
      setMeasurements(null)
      setLoading(true)
      Promise.allSettled([
        api.getEnzymeDbPapers(family as EnzymeDbFamily, undefined, 12),
        api.getEnzymeDbVariants(family as EnzymeDbFamily, undefined, 12),
        api.getEnzymeDbMeasurements(family as EnzymeDbFamily, undefined, 12),
      ])
        .then(([paperResult, variantResult, measurementResult]) => {
          if (cancelled) return
          const rejected = [paperResult, variantResult, measurementResult].filter(
            (result): result is PromiseRejectedResult => result.status === 'rejected',
          )
          if (paperResult.status === 'fulfilled') setPapers(paperResult.value)
          if (variantResult.status === 'fulfilled') setVariants(variantResult.value)
          if (measurementResult.status === 'fulfilled') setMeasurements(measurementResult.value)
          if (rejected.length) {
            setError(rejected.map((result) => result.reason instanceof Error ? result.reason.message : '部分酶库数据加载失败').join('；'))
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    })
    return () => { cancelled = true }
  }, [families, family])

  const search = async () => {
    if (!family) return
    setLoading(true)
    setError(null)
    try {
      if (!query.trim()) {
        const [paperPayload, variantPayload, measurementPayload] = await Promise.all([
          api.getEnzymeDbPapers(family as EnzymeDbFamily, undefined, 12),
          api.getEnzymeDbVariants(family as EnzymeDbFamily, undefined, 12),
          api.getEnzymeDbMeasurements(family as EnzymeDbFamily, undefined, 12),
        ])
        setPapers(paperPayload)
        setVariants(variantPayload)
        setMeasurements(measurementPayload)
      } else {
        const result = await api.searchEnzymeDb(family as EnzymeDbFamily, query.trim(), 30)
        if (result.status !== 'ready') throw new Error(`酶库搜索不可用：${result.status}`)
        setPapers({ status: result.status, family, count: result.results?.papers?.length || 0, papers: result.results?.papers || [] })
        setVariants({ status: result.status, family, count: result.results?.variants?.length || 0, variants: result.results?.variants || [] })
        setMeasurements({ status: result.status, family, count: result.results?.measurements?.length || 0, measurements: result.results?.measurements || [] })
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '搜索酶库失败')
    } finally {
      setLoading(false)
    }
  }

  const previewPolicyDecisions = async () => {
    if (!family) return
    setPolicyPreviewLoading(true)
    setPolicyPreviewError(null)
    try {
      setPolicyPreview(await api.previewEnzymeDbPolicyDecisions(family as EnzymeDbFamily, 100))
    } catch (reason) {
      setPolicyPreview(null)
      setPolicyPreviewError(reason instanceof Error ? reason.message : '加载 policy decisions dry-run 预览失败')
    } finally {
      setPolicyPreviewLoading(false)
    }
  }

  const selected = families.find((item) => item.family === family) || null
  const isAdmin = currentUser?.role === 'admin'

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-blue-200 bg-white p-5 shadow-sm dark:border-blue-900/60 dark:bg-gray-800">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-300">Enzyme Evidence Libraries</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-gray-900 dark:text-white">多酶证据库</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-600 dark:text-gray-300">
              只读浏览 papers、variants 和 measurements；这些记录用于实验设计证据追溯，不直接替代 Claim Gate。
            </p>
          </div>
          <div className="flex min-w-0 gap-2 sm:min-w-[380px]">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') void search() }}
              placeholder="搜索突变、底物、性质、DOI..."
              className="min-w-0 flex-1 rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30 dark:border-blue-900 dark:bg-gray-950"
            />
            <button
              onClick={() => { void search() }}
              disabled={loading || !family}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : query.trim() ? '搜索' : '重置'}
            </button>
          </div>
        </div>
      </section>

      {familiesLoading && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800">
          <Loader2 className="mr-2 inline h-4 w-4 animate-spin" /> 正在读取酶库目录和完整性状态...
        </div>
      )}

      {familiesError && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          <span><AlertTriangle className="mr-1 inline h-4 w-4" />酶库目录加载失败：{familiesError}</span>
          <button onClick={onRetryFamilies} className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-950/50">重试</button>
        </div>
      )}

      {!familiesLoading && !familiesError && families.length === 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle className="mr-1 inline h-4 w-4" />未配置任何可浏览的酶库。
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {families.map((item) => {
          const active = item.family === family
          const counts = item.tables || {}
          const gaps = item.metadata_quality || {}
          return (
            <button
              key={item.family}
              onClick={() => { setFamily(item.family as EnzymeDbFamily); setQuery('') }}
              className={`rounded-xl border p-3 text-left transition-colors ${active ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/30' : 'border-gray-200 bg-white hover:border-blue-300 dark:border-gray-700 dark:bg-gray-800'}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-900 dark:text-white">{item.label || item.family}</span>
                <span className={`h-2 w-2 rounded-full ${item.status === 'ready' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              </div>
              <div className="mt-2 text-[11px] text-gray-500">
                papers {counts.papers ?? 0} · variants {counts.variants ?? 0} · measurements {counts.measurements ?? 0}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-gray-500">
                <span className="rounded bg-gray-100 px-1.5 py-1 dark:bg-gray-900">DOI 缺 {gaps.missing_doi ?? 0}</span>
                <span className="rounded bg-gray-100 px-1.5 py-1 dark:bg-gray-900">PMID 缺 {gaps.missing_pmid ?? 0}</span>
                <span className="rounded bg-amber-50 px-1.5 py-1 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300">hold 文献 {gaps.hold_papers ?? 0}</span>
                <span className="rounded bg-emerald-50 px-1.5 py-1 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">可导出 {gaps.export_safe_measurements ?? 0}</span>
                <span className="rounded bg-rose-50 px-1.5 py-1 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300">策略排除 {gaps.policy_excluded_measurements ?? 0}</span>
                <span className="rounded bg-slate-100 px-1.5 py-1 text-slate-600 dark:bg-slate-900 dark:text-slate-300">边界 {gaps.boundary_measurements ?? 0}</span>
                <span className="rounded bg-indigo-50 px-1.5 py-1 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">策略 {item.metadata_policy_decisions?.decision_count ?? 0}</span>
              </div>
              <div className="mt-1 text-[10px] text-gray-400">{item.read_only ? '只读' : '状态未知'} · {item.status || 'unknown'}</div>
            </button>
          )
        })}
      </div>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">{error}</div>}

      {selected?.status !== 'ready' && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle className="mr-1 inline h-4 w-4" />该酶库当前状态为 {selected?.status || 'unknown'}，不应将空列表解释为没有实验数据。请检查只读数据库挂载和完整性。
        </div>
      )}

      {selected && (
        <section className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">{selected.label || selected.family}</span>
            <span className="rounded-full bg-white px-2 py-1 text-xs text-gray-500 dark:bg-gray-800">{selected.status || 'unknown'}</span>
            <span className="text-xs text-gray-500">integrity: {selected.quality?.integrity_check || 'unknown'}</span>
            <span className="text-xs text-gray-500">read-only: {selected.read_only ? 'yes' : 'no'}</span>
            <span className="text-xs text-gray-500">metadata gaps: {selected.metadata_quality?.metadata_gap_count ?? 0}</span>
            <span className="text-xs text-gray-500">hold measurements: {selected.metadata_quality?.hold_measurements ?? 0}</span>
            <span className="text-xs text-gray-500">boundary measurements: {selected.metadata_quality?.boundary_measurements ?? 0}</span>
            <span className="text-xs text-gray-500">policy excluded: {selected.metadata_quality?.policy_excluded_measurements ?? 0}</span>
            <span className="text-xs text-gray-500">policy decisions: {selected.metadata_policy_decisions?.decision_count ?? 0}</span>
            <span className="text-xs text-gray-500">export-safe: {selected.metadata_quality?.export_safe_measurements ?? 0}</span>
            {(selected.metadata_quality?.preprint_papers ?? 0) > 0 && (
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                preprint {selected.metadata_quality?.preprint_papers}
              </span>
            )}
            {(selected.metadata_quality?.patent_like_sources ?? 0) > 0 && (
              <span className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
                专利来源 {selected.metadata_quality?.patent_like_sources}
              </span>
            )}
          </div>
        </section>
      )}

      {selected && (
        <PolicyDecisionPreviewPanel
          selected={selected}
          preview={policyPreview}
          loading={policyPreviewLoading}
          error={policyPreviewError}
          onPreview={() => { void previewPolicyDecisions() }}
        />
      )}

      {selected && isAdmin && (
        <EnzymeMetadataCurationPanel family={selected.family as EnzymeDbFamily} />
      )}

      <div className="grid gap-5 xl:grid-cols-3">
        <SimpleEnzymeListCard title="文献 Papers" rows={papers?.papers || []} loading={loading && !papers} unavailable={papers?.status === 'missing_database'} empty="暂无文献（当前显示前 12 条）" renderRow={(row) => (
          <>
            <div className="font-medium text-gray-900 dark:text-white">{asText(row.title || row.id)}</div>
            <div className="mt-1 text-xs text-gray-500">{asText(row.author)} · {asText(row.year || '年份未知')}</div>
            <div className="mt-1 text-xs text-gray-500">DOI {asText(row.doi || '未记录')} · PMID {asText(row.pmid || '未记录')}</div>
          </>
        )} />
        <SimpleEnzymeListCard title="变体 Variants" rows={variants?.variants || []} loading={loading && !variants} unavailable={variants?.status === 'missing_database'} empty="暂无变体（当前显示前 12 条）" renderRow={(row) => (
          <>
            <div className="font-mono font-semibold text-blue-700 dark:text-blue-300">{asText(row.name || row.norm || row.id)}</div>
            <div className="mt-1 text-xs text-gray-500">{asText(row.mtype || '突变类型未记录')} · {asText(row.effect || '效果未记录')}</div>
            <div className="mt-1 text-xs text-gray-500">paper {asText(row.pid || '未关联')}</div>
          </>
        )} />
        <SimpleEnzymeListCard title="实验 Measurements" rows={measurements?.measurements || []} loading={loading && !measurements} unavailable={measurements?.status === 'missing_database'} empty="暂无测量数据（当前显示前 12 条）" renderRow={(row) => (
          <>
            <div className="font-medium text-gray-900 dark:text-white">{asText(row.prop || row.cat || row.mid)}</div>
            <div className="mt-1 font-mono text-sm text-emerald-700 dark:text-emerald-300">{asText(row.val || '未记录')} {asText(row.unit)}</div>
            <div className="mt-1 text-xs text-gray-500">{asText(row.sub || '底物未记录')} · {asText(row.conf || '证据等级未知')}</div>
          </>
        )} />
      </div>
    </div>
  )
}

function PolicyDecisionPreviewPanel({
  selected,
  preview,
  loading,
  error,
  onPreview,
}: {
  selected: SimpleEnzymeFamilyStatus
  preview: EnzymeDbPolicyDecisionPreview | null
  loading: boolean
  error: string | null
  onPreview: () => void
}) {
  const records = preview?.export_payload?.records || []
  const recordTypes = preview?.manifest?.record_types || selected.metadata_policy_decisions?.record_types || []
  const statusPolicy = preview?.manifest?.status_policy || 'Dry-run/manual review only; no SQLite mutation and no export-safe release.'

  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-4 shadow-sm dark:border-indigo-900/60 dark:bg-gray-800">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-600 dark:text-indigo-300" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Policy decisions dry-run / manual review</h3>
            <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:border-indigo-900/60 dark:bg-indigo-950/30 dark:text-indigo-300">
              no SQLite mutation
            </span>
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-gray-600 dark:text-gray-300">
            仅预览 sidecar policy decisions，供人工审核专利和 preprint 升级判断；此入口不会写入 SQLite，也不会让任何记录进入 export-safe。
          </p>
        </div>
        <button
          onClick={onPreview}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50 dark:border-indigo-900/60 dark:text-indigo-300 dark:hover:bg-indigo-950/30"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          生成 dry-run 预览
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle className="mr-1 inline h-4 w-4" />
          {error}
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <PolicyPreviewMetric label="family" value={preview?.family || selected.family} mono />
        <PolicyPreviewMetric label="record_count" value={String(preview?.manifest?.record_count ?? selected.metadata_policy_decisions?.decision_count ?? 0)} />
        <PolicyPreviewMetric label="record_types" value={recordTypes.length ? recordTypes.join(', ') : 'none'} mono />
        <PolicyPreviewMetric label="confirmation_token" value={preview?.confirmation_token || 'MANUAL_ENZYME_POLICY_DECISION_REVIEW'} mono />
      </div>

      <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
        {statusPolicy}
      </div>

      {preview && (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">Manual review records</div>
            <div className="text-xs text-gray-400">{records.length} shown from dry-run preview</div>
          </div>
          <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
            {records.length > 0 ? records.map((record, index) => (
              <div key={`${asText(record.paper_id || record.id)}:${index}`} className="border-b border-gray-100 px-3 py-2 text-xs last:border-0 dark:border-gray-700">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-indigo-700 dark:text-indigo-300">
                    paper_id: {asText(record.paper_id || '未记录')}
                  </span>
                  <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-300">
                    {asText(record.record_type || 'unknown')}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-gray-500 dark:text-gray-400">
                  <span>review_status: {asText(record.review_status || 'pending')}</span>
                  {record.reason ? <span>reason: {asText(record.reason)}</span> : null}
                  {record.action ? <span>action: {asText(record.action)}</span> : null}
                </div>
              </div>
            )) : (
              <div className="p-4"><Empty text="dry-run 无待审核 policy decisions" /></div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function PolicyPreviewMetric({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string | number
  mono?: boolean
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs dark:border-gray-700 dark:bg-gray-900">
      <div className="text-gray-400">{label}</div>
      <div className={`mt-1 break-all font-semibold text-gray-900 dark:text-white ${mono ? 'font-mono' : ''}`}>{value}</div>
    </div>
  )
}

function EnzymeMetadataCurationPanel({ family }: { family: EnzymeDbFamily }) {
  const [records, setRecords] = useState<EnzymeMetadataCurationList | null>(null)
  const [batches, setBatches] = useState<EnzymeMetadataCurationBatch[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [materializeResult, setMaterializeResult] = useState<EnzymeMetadataCurationMaterializeResult | null>(null)
  const [batchPreview, setBatchPreview] = useState<ApiRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [recordPayload, batchPayload] = await Promise.all([
        api.listEnzymeMetadataCurationRecords({ family, limit: 100 }),
        api.listEnzymeMetadataCurationBatches({ family, limit: 50 }),
      ])
      setRecords(recordPayload)
      setBatches(batchPayload.batches || [])
      setSelectedIds((current) => current.filter((id) => recordPayload.records.some((record) => record.id === id)))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载 metadata curation queue 失败')
    } finally {
      setLoading(false)
    }
  }, [family])

  useEffect(() => {
    queueMicrotask(() => { void loadQueue() })
  }, [loadQueue])

  const materialize = async (dryRun: boolean) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.materializeEnzymeMetadataCuration(family, dryRun, 100)
      setMaterializeResult(result)
      if (!dryRun) await loadQueue()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'materialize policy decisions 失败')
    } finally {
      setLoading(false)
    }
  }

  const reviewSelected = async (status: string) => {
    if (!selectedIds.length) return
    setLoading(true)
    setError(null)
    try {
      for (const id of selectedIds) {
        await api.reviewEnzymeMetadataCurationRecord(id, status, `Reviewed from /data queue as ${status}`)
      }
      await loadQueue()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '更新 queue review 状态失败')
    } finally {
      setLoading(false)
    }
  }

  const batchSelected = async (dryRun: boolean) => {
    if (!selectedIds.length) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.createEnzymeMetadataCurationBatch({ record_ids: selectedIds, dry_run: dryRun })
      if (dryRun) {
        setBatchPreview((result.manifest || {}) as ApiRecord)
      } else {
        setBatchPreview(null)
        await loadQueue()
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建 metadata curation batch 失败')
    } finally {
      setLoading(false)
    }
  }

  const archiveBatch = async (batch: EnzymeMetadataCurationBatch) => {
    setLoading(true)
    setError(null)
    try {
      await api.archiveEnzymeMetadataCurationBatch(
        batch.id,
        batch.confirmation_token,
        'Archived from /data queue; external SQLite remains unchanged'
      )
      await loadQueue()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '归档 metadata curation batch 失败')
    } finally {
      setLoading(false)
    }
  }

  const toggleSelected = (id: number) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  const recordRows = records?.records || []
  const acceptedSelectedCount = recordRows.filter((record) => selectedIds.includes(record.id) && record.status === 'accepted').length
  const preparedBatches = batches.filter((batch) => batch.status === 'prepared')

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-gray-800">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-slate-600 dark:text-slate-300" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Metadata curation queue</h3>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
              platform DB only
            </span>
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-gray-600 dark:text-gray-300">
            将 sidecar policy decisions 写入平台内部人工审核队列；归档只表示已形成后续升级脚本输入，不会修改 acid/xylanase SQLite，也不会释放 export-safe。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { void loadQueue() }} disabled={loading} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900">
            刷新
          </button>
          <button onClick={() => { void materialize(true) }} disabled={loading} className="rounded-lg border border-indigo-200 px-3 py-2 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50 dark:border-indigo-900/60 dark:text-indigo-300">
            materialize dry-run
          </button>
          <button onClick={() => { void materialize(false) }} disabled={loading} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            写入内部 queue
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle className="mr-1 inline h-4 w-4" />
          {error}
        </div>
      )}

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <PolicyPreviewMetric label="queued records" value={recordRows.filter((record) => record.status === 'queued').length} />
        <PolicyPreviewMetric label="accepted" value={recordRows.filter((record) => record.status === 'accepted').length} />
        <PolicyPreviewMetric label="prepared batches" value={preparedBatches.length} />
        <PolicyPreviewMetric label="selected" value={selectedIds.length} />
      </div>

      {materializeResult && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          materialize: {materializeResult.status} · planned {materializeResult.planned_count} · skipped {materializeResult.skipped_count} · sqlite_mutated {String(materializeResult.sqlite_mutated)} · export_safe_released {String(materializeResult.export_safe_released)}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => { void reviewSelected('accepted') }} disabled={loading || !selectedIds.length} className="rounded-lg border border-emerald-200 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-900/60 dark:text-emerald-300">
          选中设为 accepted
        </button>
        <button onClick={() => { void reviewSelected('needs_more_evidence') }} disabled={loading || !selectedIds.length} className="rounded-lg border border-amber-200 px-3 py-2 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50 dark:border-amber-900/60 dark:text-amber-300">
          选中需补证据
        </button>
        <button onClick={() => { void reviewSelected('rejected') }} disabled={loading || !selectedIds.length} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/60 dark:text-rose-300">
          选中 rejected
        </button>
        <button onClick={() => { void batchSelected(true) }} disabled={loading || !acceptedSelectedCount} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300">
          batch dry-run
        </button>
        <button onClick={() => { void batchSelected(false) }} disabled={loading || !acceptedSelectedCount} className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50">
          内部 batch 归档准备
        </button>
      </div>

      {batchPreview && (
        <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          batch dry-run: record_count {asText(batchPreview.record_count || 0)} · paper_ids {Array.isArray(batchPreview.paper_ids) ? batchPreview.paper_ids.join(', ') : 'none'}
        </div>
      )}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="max-h-80 overflow-y-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
          {recordRows.length > 0 ? recordRows.map((record) => (
            <label key={record.id} className="flex cursor-pointer gap-3 border-b border-gray-100 px-3 py-2 text-xs last:border-0 dark:border-gray-700">
              <input
                type="checkbox"
                checked={selectedIds.includes(record.id)}
                onChange={() => toggleSelected(record.id)}
                className="mt-1 h-4 w-4 rounded border-gray-300"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-slate-800 dark:text-slate-100">{record.paper_id}</span>
                  <span className={`rounded px-2 py-0.5 font-mono ${metadataStatusTone(record.status)}`}>{record.status}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-gray-500 dark:text-gray-400">
                  <span>{record.record_type}</span>
                  <span>{asText(record.decision || 'no decision')}</span>
                  {record.source_identifier ? <span className="font-mono">{record.source_identifier}</span> : null}
                </div>
                {record.reviewer_notes ? <div className="mt-1 text-gray-400">{record.reviewer_notes}</div> : null}
              </div>
            </label>
          )) : (
            <div className="p-4"><Empty text="暂无 metadata curation records" /></div>
          )}
        </div>

        <div className="space-y-2">
          <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">Prepared batches</div>
          {preparedBatches.length > 0 ? preparedBatches.map((batch) => (
            <div key={batch.id} className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs dark:border-gray-700 dark:bg-gray-900">
              <div className="font-mono font-semibold text-gray-800 dark:text-gray-100">{batch.batch_key}</div>
              <div className="mt-1 text-gray-500">records {batch.record_ids.length} · {batch.status}</div>
              <button
                onClick={() => { void archiveBatch(batch) }}
                disabled={loading}
                className="mt-2 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-white disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-gray-800"
              >
                内部归档 batch
              </button>
            </div>
          )) : (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-500 dark:border-gray-700 dark:bg-gray-900">
              无 prepared batch
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function metadataStatusTone(status: string): string {
  if (status === 'accepted') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300'
  if (status === 'rejected') return 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300'
  if (status === 'needs_more_evidence') return 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
  if (status === 'batched' || status === 'archived') return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
  return 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300'
}

function SimpleEnzymeListCard({
  title,
  rows,
  loading = false,
  unavailable = false,
  empty,
  renderRow,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  loading?: boolean
  unavailable?: boolean
  empty: string
  renderRow: (row: Record<string, unknown>) => ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
        <span className="text-xs text-gray-400">{rows.length}</span>
      </div>
      <div className="space-y-2">
        {loading ? (
          <div className="rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />加载中...</div>
        ) : unavailable ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">数据源未挂载，无法判断该库是否为空。</div>
        ) : rows.length ? rows.map((row, index) => (
          <article key={`${asText(row.id || row.mid || row.name)}:${index}`} className="rounded-xl border border-gray-200 bg-white p-4 text-sm dark:border-gray-700 dark:bg-gray-800">
            {renderRow(row)}
          </article>
        )) : <Empty text={empty} />}
      </div>
    </section>
  )
}

function LipaseEvidenceBrowser({ status }: { status: LipaseDbStatus | null }) {
  const [q, setQ] = useState('')
  const [papers, setPapers] = useState<LipasePaperList | null>(null)
  const [variants, setVariants] = useState<LipaseVariantList | null>(null)
  const [gaps, setGaps] = useState<LipaseGapList | null>(null)
  const [searchResult, setSearchResult] = useState<LipaseSearchResult | null>(null)
  const [paperDetail, setPaperDetail] = useState<LipasePaperDetail | null>(null)
  const [detailLoadingKey, setDetailLoadingKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [paperPayload, variantPayload, gapPayload] = await Promise.all([
        api.getLipasePapers(undefined, 20),
        api.getLipaseVariants(undefined, 30),
        api.getLipaseGaps({ status: 'open', limit: 30 }),
      ])
      setPapers(paperPayload)
      setVariants(variantPayload)
      setGaps(gapPayload)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载 Lipase DB 失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) void loadOverview()
    })
    return () => {
      cancelled = true
    }
  }, [loadOverview])

  const search = async () => {
    if (!q.trim()) {
      setSearchResult(null)
      setPaperDetail(null)
      await loadOverview()
      return
    }
    setLoading(true)
    setError(null)
    try {
      setSearchResult(await api.searchLipaseEvidence(q.trim(), 50))
    } catch (e) {
      setError(e instanceof Error ? e.message : '搜索 Lipase DB 失败')
    } finally {
      setLoading(false)
    }
  }

  const loadPaperDetail = async (paperKey: string) => {
    if (!paperKey) return
    setDetailLoadingKey(paperKey)
    setError(null)
    try {
      setPaperDetail(await api.getLipasePaperDetail(paperKey))
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载文献详情失败')
    } finally {
      setDetailLoadingKey(null)
    }
  }

  const summary = status?.summary
  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-2xl border border-emerald-200 bg-[linear-gradient(135deg,rgba(236,253,245,0.98),rgba(255,255,255,0.98))] p-5 dark:border-emerald-900/60 dark:bg-[linear-gradient(135deg,rgba(6,78,59,0.28),rgba(17,24,39,0.96))]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300">
              KWB Lipase Evidence
            </div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-gray-900 dark:text-white">
              科为博脂肪酶文献证据库
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-600 dark:text-gray-300">
              只读接入文献 / 变体 / 突变 / 主张 / 指标 / 底物 / 缺口，用于突变推荐、结构分析和实验复核证据追溯。
            </p>
          </div>
          <div className="flex min-w-0 gap-2 sm:min-w-[360px]">
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') void search() }}
              placeholder="搜索 D223G、CALB、half-life、substrate..."
              className="min-w-0 flex-1 rounded-xl border border-emerald-200 bg-white px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-emerald-900 dark:bg-gray-950"
            />
            <button
              onClick={() => { void search() }}
              disabled={loading}
              className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : '搜索'}
            </button>
          </div>
        </div>

        {summary && (
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <LipaseMetric label="文献" value={summary.paper_count} />
            <LipaseMetric label="变体" value={summary.variant_count} />
            <LipaseMetric label="突变" value={summary.mutation_count} />
            <LipaseMetric label="证据" value={summary.claim_count} />
            <LipaseMetric label="指标" value={summary.metric_count} />
            <LipaseMetric label="底物" value={summary.substrate_count} />
            <LipaseMetric label="缺口" value={summary.gap_count} />
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      {searchResult ? (
        <LipaseSearchResults
          data={searchResult}
          onSelectPaper={(paperKey) => { void loadPaperDetail(paperKey) }}
          detailLoadingKey={detailLoadingKey}
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <LipasePaperListCard
            papers={papers?.papers || []}
            onSelectPaper={(paperKey) => { void loadPaperDetail(paperKey) }}
            detailLoadingKey={detailLoadingKey}
          />
          <div className="space-y-5">
            <LipaseVariantListCard variants={variants?.variants || []} />
            <LipaseGapListCard gaps={gaps?.gaps || []} />
          </div>
        </div>
      )}

      {paperDetail && <LipasePaperDetailPanel detail={paperDetail} onClose={() => setPaperDetail(null)} />}
    </div>
  )
}

function LipaseMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-white/70 bg-white/75 px-4 py-3 text-sm shadow-sm dark:border-gray-800 dark:bg-gray-950/60">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{value}</div>
    </div>
  )
}

function LipasePaperListCard({
  papers,
  onSelectPaper,
  detailLoadingKey,
}: {
  papers: Array<Record<string, unknown>>
  onSelectPaper?: (paperKey: string) => void
  detailLoadingKey?: string | null
}) {
  return (
    <LipasePanel title="文献证据" count={papers.length}>
      {papers.map((paper) => (
        <div key={asText(paper.paper_key)} className="rounded-xl border border-gray-200 bg-white p-4 text-sm dark:border-gray-700 dark:bg-gray-800">
          {(() => {
            const readyForDb = typeof paper.ready_for_db === 'string' && paper.ready_for_db.startsWith('provisional_')
            return (
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono font-semibold text-emerald-700 dark:text-emerald-300">{asText(paper.paper_key)}</span>
            {paper.year ? <span className="text-xs text-gray-400">{asText(paper.year)}</span> : null}
            {readyForDb ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">已就绪</span> : null}
          </div>
            )
          })()}
          <div className="mt-2 font-medium text-gray-900 dark:text-white">{asText(paper.title || paper.citation)}</div>
          <div className="mt-2 text-xs leading-5 text-gray-500">
            {asText(paper.enzyme_name)} · 变体 {asText(paper.variant_count || 0)} · 主张 {asText(paper.claim_count || 0)} · 缺口 {asText(paper.gap_count || 0)}
          </div>
          {onSelectPaper && (
            <button
              onClick={() => onSelectPaper(asText(paper.paper_key))}
              disabled={detailLoadingKey === asText(paper.paper_key)}
              className="mt-3 rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-900 dark:text-emerald-300 dark:hover:bg-emerald-950/30"
            >
              {detailLoadingKey === asText(paper.paper_key) ? '加载中...' : '查看详情'}
            </button>
          )}
        </div>
      ))}
    </LipasePanel>
  )
}

function LipaseVariantListCard({ variants }: { variants: Array<Record<string, unknown>> }) {
  return (
    <LipasePanel title="突变体/变体" count={variants.length}>
      {variants.map((variant, index) => (
        <div key={`${asText(variant.variant_id)}:${index}`} className="rounded-xl border border-gray-200 bg-white p-4 text-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-white">{asText(variant.variant_label || variant.anchor_display)}</span>
            <span className="font-mono text-xs text-gray-400">{asText(variant.paper_key)}</span>
          </div>
          <div className="mt-2 text-xs text-gray-500">突变：{asText(variant.mutations || variant.anchor_display || '未解析')}</div>
          {variant.claim_summary ? <div className="mt-2 text-xs leading-5 text-gray-600 dark:text-gray-300">{asText(variant.claim_summary)}</div> : null}
          {variant.metrics ? <div className="mt-2 font-mono text-[11px] text-emerald-700 dark:text-emerald-300">{asText(variant.metrics)}</div> : null}
        </div>
      ))}
    </LipasePanel>
  )
}

function LipaseGapListCard({ gaps }: { gaps: Array<Record<string, unknown>> }) {
  return (
    <LipasePanel title="待补缺口" count={gaps.length}>
      {gaps.map((gap) => (
        <div key={asText(gap.id)} className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{asText(gap.gap_type)}</span>
            <span className="rounded-full bg-white/60 px-2 py-0.5 text-xs dark:bg-gray-950/30">{asText(gap.priority || '无')}</span>
            <span className="font-mono text-xs opacity-70">{asText(gap.paper_key || '')}</span>
          </div>
          <div className="mt-2 text-xs leading-5">{asText(gap.gap_detail)}</div>
        </div>
      ))}
    </LipasePanel>
  )
}

function LipaseSearchResults({
  data,
  onSelectPaper,
  detailLoadingKey,
}: {
  data: LipaseSearchResult
  onSelectPaper?: (paperKey: string) => void
  detailLoadingKey?: string | null
}) {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-gray-200 bg-white p-4 text-sm dark:border-gray-700 dark:bg-gray-800">
        搜索：<span className="font-semibold">{data.query}</span>
        {data.counts ? <span className="ml-2 text-gray-500">({Object.entries(data.counts).map(([key, value]) => `${key}:${value}`).join(' · ')})</span> : null}
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <LipasePaperListCard papers={data.results.papers || []} onSelectPaper={onSelectPaper} detailLoadingKey={detailLoadingKey} />
        <LipaseVariantListCard variants={data.results.variants || []} />
        <LipasePanel title="证据主张" count={(data.results.claims || []).length}>
          {(data.results.claims || []).map((claim) => (
            <div key={asText(claim.id)} className="rounded-xl border border-gray-200 bg-white p-4 text-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="font-semibold text-gray-900 dark:text-white">{asText(claim.claim_group)} · {asText(claim.evidence_level)}</div>
              <div className="mt-2 text-xs leading-5 text-gray-600 dark:text-gray-300">{asText(claim.claim_summary || claim.direct_evidence)}</div>
              <div className="mt-2 font-mono text-[11px] text-gray-400">{asText(claim.paper_key)} / {asText(claim.variant_label)}</div>
            </div>
          ))}
        </LipasePanel>
        <LipaseGapListCard gaps={data.results.gaps || []} />
      </div>
    </div>
  )
}

function LipasePaperDetailPanel({ detail, onClose }: { detail: LipasePaperDetail; onClose: () => void }) {
  const paper = detail.paper || {}
  return (
    <section className="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm dark:border-emerald-900/60 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-xs font-semibold text-emerald-700 dark:text-emerald-300">{asText(paper.paper_key)}</div>
          <h3 className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{asText(paper.title || paper.citation)}</h3>
          <div className="mt-2 text-xs text-gray-500">
            {asText(paper.enzyme_name)} · {asText(paper.year || '年份未知')} · 变体 {asText(detail.counts.variants || 0)} · 主张 {asText(detail.counts.claims || 0)} · 缺口 {asText(detail.counts.gaps || 0)}
          </div>
        </div>
        <button onClick={onClose} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
          关闭
        </button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <LipaseDetailColumn title="证据主张" rows={detail.claims} fields={['claim_group', 'evidence_level', 'claim_summary', 'metrics']} />
        <LipaseDetailColumn title="变体" rows={detail.variants} fields={['variant_label', 'anchor_display', 'variant_type', 'mutations']} />
        <LipaseDetailColumn title="缺口" rows={detail.gaps} fields={['gap_type', 'priority', 'status', 'gap_detail']} warning />
      </div>
    </section>
  )
}

function LipaseDetailColumn({
  title,
  rows,
  fields,
  warning = false,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  fields: string[]
  warning?: boolean
}) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">{title}</div>
      <div className="space-y-2">
        {rows.length > 0 ? rows.map((row, index) => (
          <div key={`${title}:${index}`} className={`rounded-xl border p-3 text-xs leading-5 ${warning ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200' : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300'}`}>
            {fields.map((field) => {
              const value = asText(row[field])
              return value ? <div key={field}><span className="font-medium">{field}:</span> {value}</div> : null
            })}
          </div>
        )) : <Empty text="暂无数据" />}
      </div>
    </div>
  )
}

function LipasePanel({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
        <span className="text-xs text-gray-400">{count}</span>
      </div>
      <div className="space-y-3">
        {count > 0 ? children : <Empty text="暂无数据" />}
      </div>
    </section>
  )
}

type FeedbackFormState = {
  enzyme_name: string
  variant_name: string
  parent_variant: string
  mutations: string
  assay: string
  activity_retention_pct: string
  activity_fold_vs_wt: string
  tm_delta_c: string
  soluble_expression_pct_wt: string
  sec_monomer_pct: string
  degradation_observed: boolean
  notes: string
}

type FeedbackAnalysisScope = {
  schema_version: string
  hash_input_policy: string
  scientific_boundary: string
  generated_at?: string
  scope_hash?: string
  project_id: string | null
  project_name: string | null
  enzyme_filter: string | null
  decision_filter: string | null
  record_count: number
  validated_single_mutant_count: number
  feedback_record_fingerprint: string
  validated_mutation_fingerprint: string
  evidence_inputs: {
    structural_distances: string
    mechanism_tags: string
    same_region_groups: string
    residue_distance_graph: string
  }
}

const initialFeedbackForm: FeedbackFormState = {
  enzyme_name: '',
  variant_name: '',
  parent_variant: 'WT',
  mutations: '',
  assay: '',
  activity_retention_pct: '',
  activity_fold_vs_wt: '',
  tm_delta_c: '',
  soluble_expression_pct_wt: '',
  sec_monomer_pct: '',
  degradation_observed: false,
  notes: '',
}

function buildAnalysisScopeSnapshot(scope: FeedbackAnalysisScope, scopeKey: string): FeedbackAnalysisScope {
  return {
    ...scope,
    generated_at: new Date().toISOString(),
    scope_hash: stableScopeHash(scopeKey),
  }
}

function stableScopeHash(value: string): string {
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function ExperimentFeedbackPanel() {
  const [records, setRecords] = useState<ExperimentFeedbackRecord[]>([])
  const [summary, setSummary] = useState<ExperimentFeedbackSummary | null>(null)
  const [form, setForm] = useState<FeedbackFormState>(initialFeedbackForm)
  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [projectFilter, setProjectFilter] = useState('')
  const [decisionFilter, setDecisionFilter] = useState('')
  const [enzymeFilter, setEnzymeFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [epistasisLoading, setEpistasisLoading] = useState(false)
  const [epistasisResult, setEpistasisResult] = useState<MutationEpistasisCheckResult | null>(null)
  const [epistasisScope, setEpistasisScope] = useState<FeedbackAnalysisScope | null>(null)
  const [epistasisDistances, setEpistasisDistances] = useState('')
  const [epistasisMechanismTags, setEpistasisMechanismTags] = useState('')
  const [epistasisSameRegions, setEpistasisSameRegions] = useState('')
  const [epistasisDistanceGraph, setEpistasisDistanceGraph] = useState('')
  const [iterationPlanLoading, setIterationPlanLoading] = useState(false)
  const [iterationPlan, setIterationPlan] = useState<ExperimentFeedbackIterationPlan | null>(null)
  const [iterationPlanScope, setIterationPlanScope] = useState<FeedbackAnalysisScope | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const selectedProject = projects.find((project) => project.id === projectFilter.trim())

  const loadFeedback = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const filters = {
        project_id: projectFilter.trim() || undefined,
        enzyme_name: enzymeFilter.trim() || undefined,
        decision: decisionFilter || undefined,
        limit: 100,
      }
      const [listPayload, summaryPayload] = await Promise.all([
        api.listExperimentFeedback(filters),
        api.summarizeExperimentFeedback({ ...filters, limit: 500 }),
      ])
      setRecords(listPayload.records)
      setSummary(summaryPayload)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载实验反馈失败')
    } finally {
      setLoading(false)
    }
  }, [decisionFilter, enzymeFilter, projectFilter])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) void loadFeedback()
    })
    return () => {
      cancelled = true
    }
  }, [loadFeedback])

  useEffect(() => {
    let cancelled = false
    api.getProjects()
      .then((items) => {
        if (!cancelled) setProjects(items)
      })
      .catch(() => {
        if (!cancelled) setProjects([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updateForm = (key: keyof FeedbackFormState, value: string | boolean) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    setNotice(null)
    try {
      const metricsPayload = compactObject({
        activity_retention_pct: numberOrUndefined(form.activity_retention_pct),
        activity_fold_vs_wt: numberOrUndefined(form.activity_fold_vs_wt),
        tm_delta_c: numberOrUndefined(form.tm_delta_c),
        soluble_expression_pct_wt: numberOrUndefined(form.soluble_expression_pct_wt),
      })
      const qualityPayload = compactObject({
        sec_monomer_pct: numberOrUndefined(form.sec_monomer_pct),
        degradation_observed: form.degradation_observed ? true : undefined,
      })
      const assayPayload = compactObject({
        assay: form.assay.trim() || undefined,
      })
      const mutations = form.mutations
        .split(/[,\s，、]+/)
        .map((item) => item.trim())
        .filter(Boolean)

      const response = await api.submitExperimentFeedback({
        project_id: projectFilter.trim() || null,
        enzyme_name: form.enzyme_name.trim() || null,
        variant_name: form.variant_name.trim(),
        parent_variant: form.parent_variant.trim() || null,
        mutations,
        assay_payload: Object.keys(assayPayload).length ? assayPayload : null,
        metrics_payload: Object.keys(metricsPayload).length ? metricsPayload : null,
        quality_payload: Object.keys(qualityPayload).length ? qualityPayload : null,
        notes: form.notes.trim() || null,
      })
      setForm(initialFeedbackForm)
      setNotice(`已记录 ${response.record.variant_name}：${decisionLabel(response.record.interpretation_payload?.decision)} · 项目 ${selectedProject ? selectedProject.name : projectFilter.trim() || '未绑定'}`)
      await loadFeedback()
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交实验反馈失败')
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = form.variant_name.trim().length > 0 && (form.variant_name.trim().toUpperCase() === 'WT' || form.mutations.trim().length > 0)
  const decisions = summary?.decision_counts || {}
  const validatedFeedbackRecords = records.filter((record) => (
    (record.interpretation_payload?.decision || '') === 'go' && (record.mutations || []).length === 1
  ))
  const validatedMutations = Array.from(new Set(validatedFeedbackRecords.map((record) => record.mutations[0]).filter(Boolean))).sort((left, right) => left.localeCompare(right))
  const feedbackRecordFingerprint = records.map((record) => String(record.id)).sort((left, right) => left.localeCompare(right)).join('|')
  const validatedMutationFingerprint = validatedMutations.join('|')
  const analysisScope = useMemo<FeedbackAnalysisScope>(() => ({
    schema_version: 'feedback_analysis_scope_v1',
    hash_input_policy: 'stable_json_scope_without_generated_at_or_scope_hash',
    scientific_boundary: 'audit_metadata_not_scientific_or_wet_lab_evidence',
    project_id: projectFilter.trim() || null,
    project_name: selectedProject?.name || null,
    enzyme_filter: enzymeFilter.trim() || null,
    decision_filter: decisionFilter || null,
    record_count: records.length,
    validated_single_mutant_count: validatedMutations.length,
    feedback_record_fingerprint: feedbackRecordFingerprint,
    validated_mutation_fingerprint: validatedMutationFingerprint,
    evidence_inputs: {
      structural_distances: epistasisDistances.trim() ? 'provided' : 'missing',
      mechanism_tags: epistasisMechanismTags.trim() ? 'provided' : 'missing',
      same_region_groups: epistasisSameRegions.trim() ? 'provided' : 'missing',
      residue_distance_graph: epistasisDistanceGraph.trim() ? 'provided' : 'missing',
    },
  }), [
    decisionFilter,
    enzymeFilter,
    epistasisDistanceGraph,
    epistasisDistances,
    epistasisMechanismTags,
    epistasisSameRegions,
    projectFilter,
    feedbackRecordFingerprint,
    records.length,
    selectedProject?.name,
    validatedMutationFingerprint,
    validatedMutations.length,
  ])
  const analysisScopeKey = JSON.stringify(analysisScope)
  const analysisScopeKeyRef = useRef(analysisScopeKey)

  useEffect(() => {
    analysisScopeKeyRef.current = analysisScopeKey
  }, [analysisScopeKey])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      setEpistasisResult(null)
      setEpistasisScope(null)
      setIterationPlan(null)
      setIterationPlanScope(null)
    })
    return () => {
      cancelled = true
    }
  }, [
    decisionFilter,
    enzymeFilter,
    epistasisDistanceGraph,
    epistasisDistances,
    epistasisMechanismTags,
    epistasisSameRegions,
    projectFilter,
    records,
  ])

  const runEpistasisCheck = async () => {
    if (loading || validatedMutations.length < 2) return
    const requestScopeKey = analysisScopeKey
    const requestScope = buildAnalysisScopeSnapshot(analysisScope, requestScopeKey)
    setEpistasisLoading(true)
    setError(null)
    try {
      const singleMutantFeedback = Object.fromEntries(
        validatedFeedbackRecords.map((record) => [
          record.mutations[0],
          {
            decision: record.interpretation_payload?.decision || 'go',
            metrics: record.metrics_payload || {},
            quality: record.quality_payload || {},
            variant_name: record.variant_name,
          },
        ])
      )
      const response = await api.runMutationEpistasisCheck({
        mutations: validatedMutations,
        mechanism_tags: parseMechanismTags(epistasisMechanismTags),
        structural_distances: parseStructuralDistances(epistasisDistances),
        residue_distance_graph: parseResidueDistanceGraph(epistasisDistanceGraph),
        same_region_groups: parseSameRegionGroups(epistasisSameRegions),
        single_mutant_feedback: singleMutantFeedback,
      })
      if (analysisScopeKeyRef.current !== requestScopeKey) return
      setEpistasisResult(response.result)
      setEpistasisScope(requestScope)
    } catch (e) {
      setError(e instanceof Error ? e.message : '组合突变上位性检查失败')
    } finally {
      setEpistasisLoading(false)
    }
  }

  const runIterationPlan = async () => {
    if (loading || records.length === 0) return
    const requestScopeKey = analysisScopeKey
    const requestScope = buildAnalysisScopeSnapshot(analysisScope, requestScopeKey)
    setIterationPlanLoading(true)
    setError(null)
    try {
      const response = await api.planExperimentFeedbackIteration({
        project_id: projectFilter.trim() || undefined,
        enzyme_name: enzymeFilter.trim() || undefined,
        objective: 'multi_objective',
        mechanism_tags: parseMechanismTags(epistasisMechanismTags),
        structural_distances: parseStructuralDistances(epistasisDistances),
        residue_distance_graph: parseResidueDistanceGraph(epistasisDistanceGraph),
        same_region_groups: parseSameRegionGroups(epistasisSameRegions),
      })
      if (analysisScopeKeyRef.current !== requestScopeKey) return
      setIterationPlan(response)
      setIterationPlanScope(requestScope)
    } catch (e) {
      setError(e instanceof Error ? e.message : '下一轮设计预览失败')
    } finally {
      setIterationPlanLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-4 flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-blue-500" />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">湿实验反馈录入</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <FeedbackInput label="酶名称" value={form.enzyme_name} onChange={(value) => updateForm('enzyme_name', value)} placeholder="KWB 脂肪酶" />
            <FeedbackInput label="变体名" value={form.variant_name} onChange={(value) => updateForm('variant_name', value)} placeholder="M1" required />
            <FeedbackInput label="亲本" value={form.parent_variant} onChange={(value) => updateForm('parent_variant', value)} placeholder="WT" />
            <FeedbackInput label="突变" value={form.mutations} onChange={(value) => updateForm('mutations', value)} placeholder="A10V, D80N" />
            <FeedbackInput label="活性保留 %" value={form.activity_retention_pct} onChange={(value) => updateForm('activity_retention_pct', value)} inputMode="decimal" />
            <FeedbackInput label="活性倍数 vs WT" value={form.activity_fold_vs_wt} onChange={(value) => updateForm('activity_fold_vs_wt', value)} inputMode="decimal" />
            <FeedbackInput label="ΔTm °C" value={form.tm_delta_c} onChange={(value) => updateForm('tm_delta_c', value)} inputMode="decimal" />
            <FeedbackInput label="可溶表达 %WT" value={form.soluble_expression_pct_wt} onChange={(value) => updateForm('soluble_expression_pct_wt', value)} inputMode="decimal" />
            <FeedbackInput label="SEC 单体 %" value={form.sec_monomer_pct} onChange={(value) => updateForm('sec_monomer_pct', value)} inputMode="decimal" />
            <FeedbackInput label="检测方法" value={form.assay} onChange={(value) => updateForm('assay', value)} placeholder="DSF + 活性测定" />
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={form.degradation_observed}
              onChange={(event) => updateForm('degradation_observed', event.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            观察到降解条带
          </label>
          <div className="mt-3">
            <label className="mb-1 block text-xs font-medium text-gray-500">备注</label>
            <textarea
              value={form.notes}
              onChange={(event) => updateForm('notes', event.target.value)}
              rows={3}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              onClick={() => { void submit() }}
              disabled={!canSubmit || submitting}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              提交
            </button>
            {notice && <span className="text-sm text-green-600 dark:text-green-400">{notice}</span>}
          </div>
        </section>

        <section className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <FeedbackMetric label="记录" value={summary?.count ?? 0} />
            <FeedbackMetric label="通过" value={decisions.go ?? 0} tone="go" />
            <FeedbackMetric label="关注" value={decisions.watch ?? 0} tone="watch" />
            <FeedbackMetric label="不通过" value={decisions.no_go ?? 0} tone="no_go" />
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <div className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">组合设计就绪</div>
            <div className="text-sm text-gray-600 dark:text-gray-300">{summary?.next_strategy ? strategyLabel(summary.next_strategy) : '暂无汇总'}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(summary?.validated_single_mutants || []).map((item) => (
                <span key={`${item.variant_name}:${item.mutation}`} className="rounded-md border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300">
                  {item.variant_name || '变体'} · {item.mutation}
                </span>
              ))}
              {(!summary?.validated_single_mutants || summary.validated_single_mutants.length === 0) && (
                <span className="text-xs text-gray-400">暂无已验证单点突变</span>
              )}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                onClick={() => { void runEpistasisCheck() }}
                disabled={loading || validatedMutations.length < 2 || epistasisLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-200 px-3 py-2 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50 dark:border-blue-900/60 dark:text-blue-300 dark:hover:bg-blue-950/30"
              >
                {epistasisLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Dna className="h-4 w-4" />}
                运行组合上位性检查
              </button>
              <span className="text-xs text-gray-400">
                {validatedMutations.length >= 2 ? `${validatedMutations.length} 个通过单点可检查` : '至少需要 2 个通过单点'}
              </span>
              <button
                onClick={() => { void runIterationPlan() }}
                disabled={loading || records.length === 0 || iterationPlanLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-900/60 dark:text-emerald-300 dark:hover:bg-emerald-950/30"
              >
                {iterationPlanLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardList className="h-4 w-4" />}
                生成下一轮设计预览
              </button>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-4">
              <EvidenceTextarea
                label="结构距离"
                value={epistasisDistances}
                onChange={setEpistasisDistances}
                placeholder={'A10V:D80N=22\nA10V,K120R=8.5'}
              />
              <EvidenceTextarea
                label="机制标签"
                value={epistasisMechanismTags}
                onChange={setEpistasisMechanismTags}
                placeholder={'A10V: core_packing, stability_gain\nD80N: charge_change'}
              />
              <EvidenceTextarea
                label="同一区域"
                value={epistasisSameRegions}
                onChange={setEpistasisSameRegions}
                placeholder={'A10V,D80N\nK120R+S130P'}
              />
              <EvidenceTextarea
                label="距离图 JSON"
                value={epistasisDistanceGraph}
                onChange={setEpistasisDistanceGraph}
                placeholder={'{"schema_version":"residue_distance_graph_v1","status":"ready","edges":[{"source_position":10,"target_position":80,"distance_ca_angstrom":22.0}]}'}
              />
            </div>
            {epistasisResult && <EpistasisResultCard result={epistasisResult} scope={epistasisScope} />}
            {iterationPlan && <IterationPlanCard plan={iterationPlan} scope={iterationPlanScope} />}
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
              <div className="grid gap-3 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,0.9fr)_minmax(0,1.1fr)_160px_96px]">
                <select
                  value={selectedProject ? projectFilter : ''}
                  onChange={(event) => setProjectFilter(event.target.value)}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
                >
                  <option value="">全部可见项目</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <input
                  value={projectFilter}
                  onChange={(event) => setProjectFilter(event.target.value)}
                  placeholder="按项目 ID 过滤"
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
                />
                <input
                  value={enzymeFilter}
                  onChange={(event) => setEnzymeFilter(event.target.value)}
                  placeholder="按酶名称过滤"
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
              />
              <select
                value={decisionFilter}
                onChange={(event) => setDecisionFilter(event.target.value)}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
              >
                <option value="">全部决策</option>
                <option value="go">通过</option>
                <option value="watch">关注</option>
                <option value="no_go">不通过</option>
              </select>
              <button
                onClick={() => { void loadFeedback() }}
                disabled={loading}
                className="inline-flex items-center justify-center rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : '刷新'}
              </button>
            </div>
            <div className="mt-3 text-[11px] text-gray-400">
              当前范围: {selectedProject ? `${selectedProject.name} (${selectedProject.id})` : projectFilter.trim() || '全部项目'} · {enzymeFilter.trim() || '全部酶'} · {decisionFilter || '全部决策'}
            </div>
          </div>
        </section>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
        <div className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-900 dark:border-gray-700 dark:text-white">最近反馈</div>
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {records.length > 0 ? records.map((record) => (
            <FeedbackRecordRow key={record.id} record={record} />
          )) : (
            <div className="p-6"><Empty text="暂无实验反馈记录" /></div>
          )}
        </div>
      </section>
    </div>
  )
}

function FeedbackInput({
  label,
  value,
  onChange,
  placeholder,
  inputMode,
  required = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  inputMode?: 'text' | 'decimal'
  required?: boolean
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-500">
        {label}{required ? <span className="text-red-500"> *</span> : null}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode={inputMode}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
      />
    </label>
  )
}

function EvidenceTextarea({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-500">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full resize-none rounded-lg border border-gray-300 bg-white px-3 py-2 font-mono text-xs leading-5 outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900"
      />
    </label>
  )
}

function FeedbackMetric({ label, value, tone }: { label: string; value: number; tone?: string }) {
  const toneClass = tone === 'go'
    ? 'text-green-700 dark:text-green-300'
    : tone === 'watch'
      ? 'text-amber-700 dark:text-amber-300'
      : tone === 'no_go'
        ? 'text-red-700 dark:text-red-300'
        : 'text-gray-900 dark:text-white'
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  )
}

function FeedbackRecordRow({ record }: { record: ExperimentFeedbackRecord }) {
  const interpretation = record.interpretation_payload || {}
  const decision = interpretation.decision || 'watch'
  const metrics = record.metrics_payload || {}
  const quality = record.quality_payload || {}
  const warnings = interpretation.warning_flags || []
  const blockers = interpretation.blocker_flags || []

  return (
    <div className="px-4 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-gray-900 dark:text-white">{record.variant_name}</span>
            <DecisionBadge decision={decision} />
            {record.enzyme_name ? <span className="text-xs text-gray-400">{record.enzyme_name}</span> : null}
          </div>
          <div className="mt-1 font-mono text-xs text-gray-500">
            {(record.mutations || []).length > 0 ? record.mutations.join(' + ') : 'WT'} · 亲本 {record.parent_variant || '无'}
          </div>
        </div>
        <div className="text-xs text-gray-400">{formatMaybeDate(record.created_at)}</div>
      </div>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-5">
        <FeedbackDatum label="活性" value={metrics.activity_retention_pct != null ? `${metrics.activity_retention_pct}%` : asText(metrics.activity_fold_vs_wt ? `${metrics.activity_fold_vs_wt}x` : '')} />
        <FeedbackDatum label="ΔTm" value={metrics.tm_delta_c != null ? `${metrics.tm_delta_c}°C` : ''} />
        <FeedbackDatum label="可溶" value={metrics.soluble_expression_pct_wt != null ? `${metrics.soluble_expression_pct_wt}%WT` : ''} />
          <FeedbackDatum label="SEC 单体" value={quality.sec_monomer_pct != null ? `${quality.sec_monomer_pct}%` : ''} />
        <FeedbackDatum label="策略" value={strategyLabel(asText(interpretation.strategy))} />
      </div>
      {(warnings.length > 0 || blockers.length > 0 || record.notes) && (
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {blockers.map((flag) => <span key={`b:${flag}`} className="rounded bg-red-50 px-2 py-1 text-red-600 dark:bg-red-950/30 dark:text-red-300">{flag}</span>)}
          {warnings.map((flag) => <span key={`w:${flag}`} className="rounded bg-amber-50 px-2 py-1 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300">{flag}</span>)}
          {record.notes ? <span className="text-gray-500">{record.notes}</span> : null}
        </div>
      )}
    </div>
  )
}

function EpistasisResultCard({ result, scope }: { result: MutationEpistasisCheckResult; scope: FeedbackAnalysisScope | null }) {
  const reportPayload = scope ? { ...result, analysis_scope: scope } : result
  if (result.status === 'blocked') {
    return (
      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>{result.blocked_reason || '组合检查被阻断'}</span>
          <button
            onClick={() => downloadReport('mutation_epistasis', reportPayload)}
            className="inline-flex items-center gap-1 rounded-md border border-amber-300 px-2 py-1 text-[11px] font-medium hover:bg-amber-100 dark:border-amber-800 dark:hover:bg-amber-900/40"
            title="下载组合上位性检查报告"
          >
            <Download className="h-3.5 w-3.5" />
            下载
          </button>
        </div>
        <AnalysisScopeSummary scope={scope} />
      </div>
    )
  }

  const recommendation = result.recommendation || 'watch'
  const reportContract = result.report_contract
  const evidenceInputs = Object.entries(reportContract?.evidence_inputs || {})
  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-700 dark:text-gray-200">上位性检查</span>
          <DecisionBadge decision={recommendation} />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-gray-400">{(result.mutations || []).join(' + ')}</span>
          <button
            onClick={() => downloadReport('mutation_epistasis', reportPayload)}
            className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-[11px] font-medium text-gray-500 hover:bg-white dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            title="下载组合上位性检查报告"
          >
            <Download className="h-3.5 w-3.5" />
            下载
          </button>
        </div>
      </div>
      <AnalysisScopeSummary scope={scope} />

      {result.summary && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <FeedbackDatum label="高风险" value={String(result.summary.high_risk_pairs)} />
          <FeedbackDatum label="关注" value={String(result.summary.medium_risk_pairs)} />
          <FeedbackDatum label="评分" value={String(result.summary.risk_score_total)} />
        </div>
      )}

      {(result.required_missing_evidence || []).length > 0 && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          缺失证据：{(result.required_missing_evidence || []).join('、')}
        </div>
      )}

      {reportContract && (
        <div className="mt-3 rounded-md bg-white px-3 py-2 text-xs dark:bg-gray-800">
          <div className="font-semibold text-gray-800 dark:text-gray-100">报告合同</div>
          {evidenceInputs.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {evidenceInputs.map(([key, value]) => (
                <span key={key} className="rounded-md border border-gray-200 px-2 py-1 text-[11px] text-gray-500 dark:border-gray-700 dark:text-gray-300">
                  {key}: <span className="font-mono">{value}</span>
                </span>
              ))}
            </div>
          )}
          {(reportContract.must_not_claim || []).length > 0 && (
            <div className="mt-2 text-[11px] leading-5 text-gray-500">
              禁止声明：{(reportContract.must_not_claim || []).slice(0, 4).join('、')}
            </div>
          )}
          {reportContract.boundary && (
            <div className="mt-2 text-[11px] leading-5 text-gray-500">{reportContract.boundary}</div>
          )}
        </div>
      )}

      {(result.pairwise_risks || []).length > 0 && (
        <div className="mt-3 space-y-2">
          {(result.pairwise_risks || []).map((risk) => (
            <div key={risk.pair.join(':')} className="rounded-md bg-white px-3 py-2 text-xs dark:bg-gray-800">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-gray-800 dark:text-gray-100">{risk.pair.join(' + ')}</span>
                <span className={risk.risk === 'high' ? 'text-red-600 dark:text-red-300' : risk.risk === 'medium' ? 'text-amber-600 dark:text-amber-300' : 'text-green-600 dark:text-green-300'}>
                  {risk.risk} · score {risk.score}
                </span>
              </div>
              <div className="mt-1 leading-5 text-gray-500">{risk.reasons.join('；')}</div>
              <div className="mt-1 text-[11px] text-gray-400">
                distance source: {risk.distance_source || 'not_available'}
              </div>
            </div>
          ))}
        </div>
      )}

      {(result.gradient_experiment_plan || []).length > 0 && (
        <div className="mt-3 rounded-md bg-white px-3 py-2 text-xs dark:bg-gray-800">
          <div className="font-semibold text-gray-800 dark:text-gray-100">梯度实验计划</div>
          <div className="mt-2 space-y-1 text-gray-600 dark:text-gray-300">
            {(result.gradient_experiment_plan || []).map((step) => (
              <div key={`${step.step}:${step.variant}`}>{step.step}. {step.variant} · {step.purpose}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function IterationPlanCard({ plan, scope }: { plan: ExperimentFeedbackIterationPlan; scope: FeedbackAnalysisScope | null }) {
  const reportPayload = scope ? { ...plan, analysis_scope: scope } : plan
  const library = asPlainRecord(plan.next_round_library_design)
  const sourceEvidence = asPlainRecord(library.source_evidence)
  const contract = asPlainRecord(library.combination_evidence_contract)
  const singlePointPool = asPlainRecordArray(library.single_point_pool)
  const combinationPool = asPlainRecordArray(library.combination_pool)
  const assayRequired = Array.isArray(library.assay_required)
    ? library.assay_required.map((item) => String(item || '')).filter(Boolean)
    : []
  const mustNotClaim = Array.isArray(contract.must_not_claim)
    ? contract.must_not_claim.map((item) => String(item || '')).filter(Boolean)
    : []
  const boundaryText = asText(plan.scientific_boundary || library.boundary)

  return (
    <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 text-xs dark:border-emerald-900/60 dark:bg-emerald-950/20">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
          <span className="font-semibold text-gray-800 dark:text-gray-100">下一轮设计预览</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-white px-2 py-1 font-mono text-[11px] text-emerald-700 dark:bg-gray-900 dark:text-emerald-300">
            {plan.status}
          </span>
          <button
            onClick={() => downloadReport('feedback_iteration_plan', reportPayload)}
            className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-white px-2 py-1 text-[11px] font-medium text-emerald-700 hover:bg-emerald-50 dark:border-emerald-900/60 dark:bg-gray-900 dark:text-emerald-300 dark:hover:bg-emerald-950/30"
            title="下载下一轮设计预览报告"
          >
            <Download className="h-3.5 w-3.5" />
            下载
          </button>
        </div>
      </div>
      <AnalysisScopeSummary scope={scope} />

      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <FeedbackDatum label="结构距离来源" value={asText(plan.structural_distance_source || library.structural_distance_source || 'none')} />
        <FeedbackDatum label="组合证据合同" value={asText(contract.status || 'unknown')} />
        <FeedbackDatum label="通过单点" value={asText(sourceEvidence.validated_single_mutants || singlePointPool.length || 0)} />
        <FeedbackDatum label="可控组合" value={asText(sourceEvidence.eligible_pair_candidates || combinationPool.length || 0)} />
      </div>

      {singlePointPool.length > 0 && (
        <div className="mt-3 rounded-md bg-white px-3 py-2 dark:bg-gray-800">
          <div className="font-semibold text-gray-800 dark:text-gray-100">Single Point Pool</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {singlePointPool.slice(0, 8).map((item, index) => (
              <span key={`${asText(item.mutation)}:${index}`} className="rounded-md border border-emerald-200 px-2 py-1 font-mono text-[11px] text-emerald-700 dark:border-emerald-900/60 dark:text-emerald-300">
                {asText(item.mutation || item.variant_name || 'unknown')}
              </span>
            ))}
          </div>
        </div>
      )}

      {combinationPool.length > 0 && (
        <div className="mt-3 rounded-md bg-white px-3 py-2 dark:bg-gray-800">
          <div className="font-semibold text-gray-800 dark:text-gray-100">Combination Pool</div>
          <div className="mt-2 space-y-1.5">
            {combinationPool.slice(0, 6).map((item, index) => (
              <div key={`${asText(item.status)}:${index}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-gray-50 px-2 py-1.5 dark:bg-gray-900">
                <span className="font-mono text-gray-800 dark:text-gray-100">{Array.isArray(item.mutations) ? item.mutations.join(' + ') : 'unknown pair'}</span>
                <span className="text-[11px] text-gray-500">
                  {asText(item.epistasis_recommendation || item.status)} · {Array.isArray(item.distance_sources) ? item.distance_sources.join(', ') : 'source unknown'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {assayRequired.length > 0 && (
        <div className="mt-3 rounded-md bg-white px-3 py-2 text-[11px] leading-5 text-gray-500 dark:bg-gray-800">
          必需实验：{assayRequired.slice(0, 3).join('；')}
        </div>
      )}
      {mustNotClaim.length > 0 && (
        <div className="mt-2 text-[11px] leading-5 text-gray-500">
          禁止声明：{mustNotClaim.slice(0, 4).join('、')}
        </div>
      )}
      {boundaryText && (
        <div className="mt-2 text-[11px] leading-5 text-gray-500">
          {boundaryText}
        </div>
      )}
    </div>
  )
}

function AnalysisScopeSummary({ scope }: { scope: FeedbackAnalysisScope | null }) {
  if (!scope) return null
  const projectLabel = scope.project_name
    ? `${scope.project_name} (${scope.project_id || 'no project id'})`
    : scope.project_id || '全部项目'
  const evidenceInputs = scope.evidence_inputs
  return (
    <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-3 xl:grid-cols-6">
      <FeedbackDatum label="分析范围" value={`${projectLabel} · ${scope.enzyme_filter || '全部酶'} · ${scope.decision_filter || '全部决策'}`} />
      <FeedbackDatum label="反馈记录" value={`${scope.record_count} 条 · ${scope.validated_single_mutant_count} 个通过单点`} />
      <FeedbackDatum label="结构证据" value={`距离 ${evidenceInputs.structural_distances} · 图 ${evidenceInputs.residue_distance_graph}`} />
      <FeedbackDatum label="人工标签" value={`机制 ${evidenceInputs.mechanism_tags} · 区域 ${evidenceInputs.same_region_groups}`} />
      <FeedbackDatum label="生成时间" value={scope.generated_at || 'unknown'} />
      <FeedbackDatum label="Scope Hash" value={scope.scope_hash || 'unknown'} />
      <FeedbackDatum label="Scope Schema" value={scope.schema_version || 'unknown'} />
      <FeedbackDatum label="Hash Policy" value={scope.hash_input_policy || 'unknown'} />
      <FeedbackDatum label="反馈池指纹" value={scope.feedback_record_fingerprint || 'empty'} />
      <FeedbackDatum label="单点池指纹" value={scope.validated_mutation_fingerprint || 'empty'} />
      <FeedbackDatum label="Scope Boundary" value={scope.scientific_boundary || 'unknown'} />
    </div>
  )
}

function FeedbackDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900">
      <div className="text-gray-400">{label}</div>
      <div className="mt-1 min-h-4 break-words font-medium text-gray-800 dark:text-gray-100">{value || '—'}</div>
    </div>
  )
}

function asPlainRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asPlainRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => item !== null && typeof item === 'object' && !Array.isArray(item))
    : []
}

function DecisionBadge({ decision }: { decision: string }) {
  const tone = decision === 'go'
    ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300'
    : decision === 'no_go'
      ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300'
      : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'
  return <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${tone}`}>{decisionLabel(decision)}</span>
}

function decisionLabel(decision?: string): string {
  if (decision === 'go') return '通过'
  if (decision === 'no_go') return '不通过'
  if (decision === 'watch') return '关注'
  return decision || '关注'
}

function strategyLabel(strategy?: string): string {
  return {
    eligible_for_combination_design: '可进入组合设计',
    use_as_validated_parent_or_compare_epistasis: '可作为亲本或复核上位性',
    repeat_or_add_missing_qc_before_combination: '补 QC 或重复验证后再组合',
    do_not_combine_without_rescue_rationale: '无 rescue 逻辑不建议组合',
    collect_more_single_mutant_data: '继续补单点数据',
    validate_one_more_orthogonal_single_mutant: '再验证一个正交单点',
    run_epistasis_check_before_combination: '组合前运行上位性检查',
    collect_more_data: '继续补实验数据',
  }[strategy || ''] || strategy || '暂无策略'
}

function numberOrUndefined(value: string): number | undefined {
  if (!value.trim()) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function compactObject<T extends Record<string, unknown>>(value: T): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== ''))
}

function parseStructuralDistances(value: string): Record<string, number> {
  const distances: Record<string, number> = {}
  for (const rawLine of value.split(/\n+/)) {
    const line = rawLine.trim()
    if (!line) continue
    const match = line.match(/^([A-Za-z][0-9]+[A-Za-z])\s*[:+,]\s*([A-Za-z][0-9]+[A-Za-z])\s*=\s*([0-9.]+)$/)
    if (!match) continue
    distances[[match[1].toUpperCase(), match[2].toUpperCase()].sort().join(':')] = Number(match[3])
  }
  return distances
}

function parseMechanismTags(value: string): Record<string, string[]> {
  const tags: Record<string, string[]> = {}
  for (const rawLine of value.split(/\n+/)) {
    const [mutation, rawTags] = rawLine.split(':')
    const code = mutation?.trim().toUpperCase()
    if (!code || !rawTags) continue
    const parsedTags = rawTags
      .split(/[,\s，、]+/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (parsedTags.length) tags[code] = parsedTags
  }
  return tags
}

function parseSameRegionGroups(value: string): string[][] {
  return value
    .split(/\n+/)
    .map((line) => line.split(/[,+，、\s]+/).map((item) => item.trim().toUpperCase()).filter(Boolean))
    .filter((group) => group.length >= 2)
}

function parseResidueDistanceGraph(value: string): Record<string, unknown> | undefined {
  const text = value.trim()
  if (!text) return undefined
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function InfoBlock({
  label,
  value,
  mono = false,
}: {
  label: string
  value?: string
  mono?: boolean
}) {
  if (!value) return null

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">{label}</div>
      <div className={`mt-1 text-sm text-gray-800 dark:text-gray-100 break-all ${mono ? 'font-mono' : ''}`}>
        {value}
      </div>
    </div>
  )
}

function StatsPanel({ stats }: { stats: (DataStats & { ingestion_hashes?: Record<string, string> }) | null }) {
  const counts = stats?.counts || {}
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Object.entries(counts).map(([k, v]) => (
        <div key={k} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-2xl font-bold text-blue-600">{v}</div>
          <div className="text-sm text-gray-500 mt-1">{k.replace(/_/g, ' ')}</div>
        </div>
      ))}
      {stats?.ingestion_hashes && (
        <div className="col-span-full mt-4">
          <div className="text-sm font-medium mb-2">已同步数据源</div>
          <div className="flex gap-2 flex-wrap">
            {Object.keys(stats.ingestion_hashes).map(k => (
              <span key={k} className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-1 rounded">
                {k.replace('ingest:', '').replace(':hash', '')}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ToolCapabilitiesPanel({ audit }: { audit: ToolCapabilityAudit | null }) {
  if (!audit) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        <span className="text-sm">加载工具能力边界...</span>
      </div>
    )
  }

  const statusEntries = Object.entries(audit.summary.status_counts)
    .sort((a, b) => b[1] - a[1])

  return (
    <div className="space-y-5">
      <div className={`rounded-lg border px-5 py-4 ${
        audit.summary.unknown_count === 0
          ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300'
          : 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300'
      }`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            {audit.summary.unknown_count === 0
              ? <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0" />
              : <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" />}
            <div>
              <div className="text-sm font-semibold">报告级工具能力审计：{audit.status}</div>
              <div className="mt-1 text-xs opacity-80">
                共 {audit.summary.tool_count} 个工具，未知能力 {audit.summary.unknown_count} 个
              </div>
            </div>
          </div>
          <div className="text-xs font-medium">
            {audit.summary.unknown_count === 0 ? '能力标签完整' : '存在发布阻断项'}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {statusEntries.map(([status, count]) => (
          <span
            key={status}
            className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${capabilityStatusTone(status)}`}
          >
            {capabilityStatusLabel(status)} {count}
          </span>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {audit.capabilities.map((row) => (
          <article
            key={row.tool}
            className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-mono text-sm font-semibold text-gray-900 dark:text-white">{row.tool}</h3>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  报告动作：{capabilityActionLabel(row.report_action)}
                </div>
              </div>
              <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${capabilityStatusTone(row.capability_status)}`}>
                {capabilityStatusLabel(row.capability_status)}
              </span>
            </div>

            <div className="mt-4 text-sm leading-6 text-gray-700 dark:text-gray-200">
              {row.boundary}
            </div>

            <div className="mt-4 border-t border-gray-100 pt-3 dark:border-gray-700">
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">升级为报告级证据所需产物</div>
              <ul className="mt-2 space-y-1.5 text-xs leading-5 text-gray-600 dark:text-gray-300">
                {row.minimum_artifacts.map((artifact) => (
                  <li key={artifact} className="flex items-start gap-2">
                    <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-gray-400" />
                    <span>{artifact}</span>
                  </li>
                ))}
              </ul>
            </div>
          </article>
        ))}
      </div>

      {audit.unknown_tools.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          未建立能力合同：{audit.unknown_tools.join('、')}。这些工具不得进入报告级结论。
        </div>
      )}
    </div>
  )
}

function capabilityStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    real_runtime: '真实运行',
    real_runtime_gated: '真实运行受门控',
    external_service: '外部服务',
    external_service_or_cache: '外部服务/缓存',
    proxy: '代理/MVP',
    proxy_ranker: '代理排序',
    proxy_or_external_lookup: '代理/外部检索',
    runtime_unverified: '运行时未核验',
    evidence_synthesis: '证据聚合',
    foundation_dependent_explainer: '依赖身份门控',
    foundation_or_proxy_prediction: '身份派生/代理预测',
    objective_gate: '目标门控',
    structure_similarity_search: '结构相似检索',
    numbering_evidence_gated: '编号证据受门控',
    background_baseline: '背景基线',
    blocked: '已阻断',
    unknown: '未知',
  }
  return labels[status] || status
}

function capabilityStatusTone(status: string): string {
  if (status === 'real_runtime' || status === 'external_service' || status === 'evidence_synthesis') {
    return 'border-green-200 bg-green-50 text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300'
  }
  if (status.includes('proxy') || status.includes('unverified') || status.includes('gated')) {
    return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'
  }
  if (status === 'blocked' || status === 'unknown') {
    return 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300'
  }
  return 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-300'
}

function capabilityActionLabel(action: string): string {
  if (action === 'allow_with_artifacts') return '产物齐全后可用于报告'
  if (action === 'label_as_proxy_or_block_until_artifacts_exist') return '标记为代理，或在产物齐全前阻断'
  if (action === 'block_report_grade_claims') return '阻断报告级声明'
  return action
}

function ReadinessPanel({
  readiness,
  lipaseStatus,
}: {
  readiness: DeployDataReadiness | null
  lipaseStatus: LipaseDbStatus | null
}) {
  if (!readiness) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        <span className="text-sm">加载数据就绪度...</span>
      </div>
    )
  }

  const components = Object.entries(readiness.components)
  const summaryTone = readiness.live_ready
    ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300'
    : readiness.summary === 'demo-ready'
      ? 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'
      : 'border-gray-200 bg-white text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'

  return (
    <div className="space-y-5">
      <div className={`rounded-lg border px-5 py-4 ${summaryTone}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {readiness.live_ready ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
            <div>
              <div className="text-sm font-semibold">deploy_data 状态：{readiness.summary}</div>
              <div className="mt-1 font-mono text-xs opacity-80">{readiness.root.project_relative_path || readiness.root.path}</div>
            </div>
          </div>
          <div className="text-xs font-medium">
            {readiness.live_ready ? '真实数据可上线验收' : `${readiness.missing_or_demo_components.length} 项仍需处理`}
          </div>
        </div>
      </div>

      <LipaseDbCard status={lipaseStatus} />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {components.map(([key, component]) => (
          <ReadinessCard key={key} name={key} component={component} />
        ))}
      </div>

      {readiness.next_actions.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">下一步动作</div>
          <div className="space-y-2">
            {readiness.next_actions.map((action) => (
              <div key={action} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
                <span>{action}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {readiness.updates?.manifests?.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-gray-900 dark:text-white">更新记录</div>
            <div className="text-xs text-gray-400">{readiness.updates.manifest_count} 个 manifest 已存在</div>
          </div>
          <div className="space-y-2">
            {readiness.updates.manifests.map((manifest) => (
              <div
                key={`${manifest.label}:${manifest.path}`}
                className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-xs dark:border-gray-700 dark:bg-gray-900"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-gray-800 dark:text-gray-100">{manifest.label}</span>
                  <span className={manifest.exists ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                    {manifest.exists ? '已存在' : '缺失'}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[11px] leading-5 text-gray-400 break-all">
                  {manifest.project_relative_path || manifest.path}
                </div>
                {manifest.exists && (
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-gray-500 dark:text-gray-400">
                    {manifest.updated_at && <span>更新时间: {manifest.updated_at}</span>}
                    {manifest.size_bytes != null && <span>{formatBytes(manifest.size_bytes)}</span>}
                    {manifest.counts && Object.entries(manifest.counts).map(([key, value]) => (
                      <span key={key}>{key}: {value}</span>
                    ))}
                    {manifest.parse_error && <span className="text-red-500">解析失败</span>}
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

function LipaseDbCard({ status }: { status: LipaseDbStatus | null }) {
  if (!status) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        加载科为博 Lipase DB...
      </div>
    )
  }

  const ready = status.status === 'ready'
  const tone = ready
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300'
    : status.status === 'missing' || status.status === 'error'
      ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300'
      : 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'

  return (
    <div className={`rounded-lg border px-5 py-4 ${tone}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">科为博 Lipase DB：{lipaseStatusLabel(status.status)}</div>
          <div className="mt-1 font-mono text-xs opacity-80 break-all">
            {status.path.exists ? `${formatBytes(status.path.size_bytes)} · ${status.path.updated_at || '未知更新时间'}` : '未找到数据库文件'}
          </div>
          <div className="mt-1 text-xs opacity-80">
            {status.read_only ? '只读接入' : '可写'} · integrity {status.quality.integrity_check} · 外键问题 {status.quality.foreign_key_issues.length}
          </div>
        </div>
        <div className="text-right text-xs font-medium">
          {status.quality.ready_for_ingestion ? '可进入导入预演' : '需要先处理质量项'}
        </div>
      </div>

      {status.summary && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs md:grid-cols-4 xl:grid-cols-7">
          <MiniMetric label="文献" value={status.summary.paper_count} />
          <MiniMetric label="变体" value={status.summary.variant_count} />
          <MiniMetric label="突变" value={status.summary.mutation_count} />
          <MiniMetric label="证据" value={status.summary.claim_count} />
          <MiniMetric label="指标" value={status.summary.metric_count} />
          <MiniMetric label="底物" value={status.summary.substrate_count} />
          <MiniMetric label="缺口" value={status.summary.gap_count} />
        </div>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <StatusList title="证据等级" items={(status.evidence_levels || []).map((item) => `${item.evidence_level || '未知'}: ${item.count}`)} />
        <StatusList title="证据主张类型" items={(status.claim_groups || []).map((item) => `${item.claim_group || '未知'}: ${item.count}`)} />
        <StatusList title="缺失项" items={(status.gap_summary || []).slice(0, 5).map((item) => `${item.gap_type || '未知'} · ${item.priority || '无'} · ${item.status || '无'}: ${item.count}`)} />
      </div>

      {status.next_actions.length > 0 && (
        <div className="mt-3 rounded-md bg-white/50 px-3 py-2 text-xs leading-5 dark:bg-gray-950/30">
          {status.next_actions.join('；')}
        </div>
      )}
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-white/55 px-3 py-2 dark:bg-gray-950/30">
      <div className="opacity-70">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  )
}

function StatusList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md bg-white/55 px-3 py-2 text-xs dark:bg-gray-950/30">
      <div className="font-semibold">{title}</div>
      <div className="mt-2 space-y-1">
        {items.length > 0 ? items.map((item) => <div key={item}>{item}</div>) : <div className="opacity-60">无</div>}
      </div>
    </div>
  )
}

function ReadinessCard({ name, component }: { name: string; component: DeployDataReadiness['components'][string] }) {
  const tone = component.status === 'ready'
    ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300'
    : component.status === 'demo'
      ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300'
      : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300'
  const previewCount = Array.isArray(component.preview)
    ? component.preview.length
    : Object.values(component.preview || {}).reduce((sum, items) => sum + items.length, 0)
  const missingItems = component.missing_items || []

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white">{readinessLabel(name)}</div>
          <div className="mt-1 font-mono text-[11px] leading-5 text-gray-400 break-all">
            {component.path.project_relative_path || component.path.path}
          </div>
        </div>
        <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}>
          {readinessStatusLabel(component.status)}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900">
          <div className="text-gray-400">文件/索引</div>
          <div className="mt-1 font-semibold text-gray-800 dark:text-gray-100">
            {component.count ?? Object.values(component.counts || {}).reduce((sum, value) => sum + value, 0)}
          </div>
        </div>
        <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900">
          <div className="text-gray-400">预览</div>
          <div className="mt-1 font-semibold text-gray-800 dark:text-gray-100">{previewCount}</div>
        </div>
      </div>
      <div className="mt-3 grid gap-2 text-xs">
        <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900">
          <div className="text-gray-400">版本</div>
          <div className="mt-1 break-all font-mono text-[11px] text-gray-700 dark:text-gray-200">
            {component.version || '未版本化'}
          </div>
        </div>
        <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900">
          <div className="text-gray-400">更新时间</div>
          <div className="mt-1 font-mono text-[11px] text-gray-700 dark:text-gray-200">
            {formatMaybeDate(component.updated_at)}
          </div>
        </div>
      </div>
      {missingItems.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
          <div className="font-semibold">缺失项</div>
          <div className="mt-1 leading-5">
            {missingItems.join('；')}
          </div>
        </div>
      )}
      {component.failure_reason && (
        <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs leading-5 text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
          {component.failure_reason}
        </div>
      )}
    </div>
  )
}

function OpsPanel({ opsSummary }: { opsSummary: OpsSummary | null }) {
  if (!opsSummary) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        <span className="text-sm">加载运维状态...</span>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        <OpsMetric icon={Activity} label="API 状态" value={opsSummary.status} hint={`运行时长 ${opsSummary.uptime_seconds}s`} />
        <OpsMetric icon={HardDrive} label="磁盘使用" value={`${opsSummary.storage.disk.used_percent ?? 0}%`} hint={`${formatBytes(opsSummary.storage.disk.free_bytes)} 可用`} />
        <OpsMetric icon={Database} label="告警数量" value={opsSummary.monitoring?.alert_count ?? 0} hint={opsSummary.data.live_ready ? '真实数据就绪' : `${opsSummary.data.missing_or_demo_components.length} 项待处理`} />
        <OpsMetric icon={Server} label="Worker 在线" value={opsSummary.runtime?.celery?.online_workers ?? 0} hint={`${opsSummary.runtime?.celery?.active_tasks ?? 0} 个活跃任务`} />
        <OpsMetric icon={Activity} label="Redis 状态" value={opsSummary.runtime?.redis?.status || '未知'} hint={opsSummary.runtime?.redis?.broker_url || '消息代理'} />
        <OpsMetric icon={Database} label="队列数量" value={Object.keys(opsSummary.runtime?.redis?.queues || {}).length} hint="已跟踪队列" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <Activity className="h-4 w-4 text-blue-500" />
            健康检查
          </div>
          <div className="space-y-2">
            {(opsSummary.monitoring?.checks || []).map((check) => (
              <div key={check.name} className="rounded-md bg-gray-50 px-3 py-2 text-xs dark:bg-gray-900">
                <div className="flex items-start justify-between gap-3">
                  <span className="font-mono text-[11px] text-gray-800 dark:text-gray-100">{check.name}</span>
                  <span className={check.status === 'ok' ? 'text-green-600 dark:text-green-400' : check.severity === 'critical' ? 'text-red-500' : 'text-amber-500'}>
                    {check.status}
                  </span>
                </div>
                <div className="mt-1 leading-5 text-gray-500">{check.message}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <Server className="h-4 w-4 text-blue-500" />
            Worker 队列策略
          </div>
          <div className="space-y-2">
            {Object.entries(opsSummary.workers).map(([name, worker]) => (
              <div key={name} className="rounded-md bg-gray-50 px-3 py-2 text-xs dark:bg-gray-900">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-gray-800 dark:text-gray-100">{name}</span>
                  <span className="font-mono text-blue-600 dark:text-blue-400">{worker.queue}</span>
                </div>
                <div className="mt-1 text-gray-500">
                  软限制 {worker.soft_time_limit}s · 硬限制 {worker.time_limit}s
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <Server className="h-4 w-4 text-blue-500" />
            Worker 运行态
          </div>
          <div className="space-y-2">
            <div className="rounded-md bg-gray-50 px-3 py-2 text-xs dark:bg-gray-900">
              <div className="flex items-center justify-between gap-3">
                <span className="text-gray-500">任务队列</span>
                <span className={opsSummary.runtime?.celery?.status === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-amber-500'}>
                  {opsSummary.runtime?.celery?.status || '未知'}
                </span>
              </div>
              <div className="mt-1 text-gray-500">
                在线 {opsSummary.runtime?.celery?.online_workers ?? 0} · 活跃 {opsSummary.runtime?.celery?.active_tasks ?? 0}
              </div>
            </div>
            {Object.entries(opsSummary.runtime?.redis?.queues || {}).map(([queue, detail]) => (
              <div key={queue} className="rounded-md bg-gray-50 px-3 py-2 text-xs dark:bg-gray-900">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-gray-800 dark:text-gray-100">{queue}</span>
                  <span className="text-blue-600 dark:text-blue-400">{detail.length ?? '—'}</span>
                </div>
                <div className="mt-1 text-gray-500">Redis 积压</div>
              </div>
            ))}
            {opsSummary.runtime?.redis?.error && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {opsSummary.runtime.redis.error}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">外部依赖</div>
          <div className="space-y-2">
            {Object.entries(opsSummary.external_endpoints).map(([key, value]) => (
              <div key={key} className="flex items-start justify-between gap-4 rounded-md bg-gray-50 px-3 py-2 text-xs dark:bg-gray-900">
                <span className="text-gray-500">{key}</span>
                <span className="max-w-[70%] break-all text-right font-mono text-gray-800 dark:text-gray-100">{value || 'unset'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function OpsMetric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: IconComponent
  label: string
  value: ReactNode
  hint: ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <Icon className="mb-3 h-5 w-5 text-blue-500" />
      <div className="text-xs font-medium text-gray-400">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs text-gray-500">{hint}</div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

function formatMaybeDate(value?: string | null): string {
  if (!value) return '未知'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function readinessLabel(name: string): string {
  return {
    annotations: '注释库',
    sifts: 'SIFTS 映射',
    pdb: 'PDB 结构库',
    alphafold: 'AlphaFold 结构库',
    foldseek: 'Foldseek 索引',
    smoke_query: '烟雾测试查询结构',
  }[name] || name
}

function readinessStatusLabel(status: string): string {
  return {
    ready: '就绪',
    demo: '演示',
    missing: '缺失',
    empty: '空',
    error: '错误',
    partial: '部分就绪',
  }[status] || status
}

function lipaseStatusLabel(status: string): string {
  return {
    ready: '就绪',
    partial: '部分就绪',
    missing: '缺失',
    error: '错误',
    empty: '空',
  }[status] || status
}

function KV({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null
  return (
    <div>
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div className="text-gray-700 dark:text-gray-300">{value}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="text-center py-8 text-sm text-gray-400">{text}</div>
}

// ============================================================================
// Highlight — wraps matching query substring in <mark>
// ============================================================================

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query || !text) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-200 dark:bg-yellow-800 rounded px-0.5">{text.slice(idx, idx + query.length)}</mark>
      <Highlight text={text.slice(idx + query.length)} query={query} />
    </>
  )
}

// ============================================================================
// MoleculeCard — renders a SMILES string as chemical structure SVG via smiles-drawer
// ============================================================================

function MoleculeCard({ cid, smiles, name }: { cid?: string | number; smiles: string; name?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imageFailureKey = cid == null ? '' : String(cid)
  const [failedImageKey, setFailedImageKey] = useState<string | null>(null)
  const [failedRenderKey, setFailedRenderKey] = useState<string | null>(null)
  const imageFailed = imageFailureKey !== '' && failedImageKey === imageFailureKey
  const renderFailed = failedRenderKey === smiles
  const structureImageUrl = cid
    ? `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${encodeURIComponent(String(cid))}/PNG?image_size=large`
    : null

  useEffect(() => {
    if (!canvasRef.current || !smiles || (structureImageUrl && !imageFailed)) return
    try {
      SmilesDrawerNS.parse(
        smiles,
        (tree: unknown) => {
          const drawer = new SmilesDrawerNS.Drawer({
            width: 320,
            height: 220,
            bondThickness: 1.4,
            shortBondLength: 0.82,
            compactDrawing: true,
            explicitHydrogens: false,
            padding: 12,
          })
          drawer.draw(tree, canvasRef.current!, 'light', false)
          setFailedRenderKey((current) => current === smiles ? null : current)
        },
        () => { setFailedRenderKey(smiles) }
      )
    } catch {
      queueMicrotask(() => setFailedRenderKey(smiles))
    }
  }, [smiles, imageFailed, structureImageUrl])

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/80">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400">
          2D 结构
        </div>
        {name && <div className="max-w-[14rem] truncate text-xs font-medium text-gray-500">{name}</div>}
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-white">
        {structureImageUrl && !imageFailed ? (
          <img
            src={structureImageUrl}
          alt={name ? `${name} 二维结构` : '二维结构'}
            className="mx-auto block h-auto w-full max-w-[320px] object-contain"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFailedImageKey(imageFailureKey)}
          />
        ) : (
          <canvas
            ref={canvasRef}
            width={320}
            height={220}
            className={`${renderFailed ? 'hidden' : 'h-auto w-full'}`}
          />
        )}
        {((!structureImageUrl || imageFailed) && renderFailed) && (
          <div className="flex min-h-[220px] items-center justify-center px-4 text-center text-xs leading-6 text-gray-500">
            当前结构图无法自动绘制，已在下方完整展示 SMILES。
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// AlphaFoldChart — per-residue pLDDT bar chart via recharts
// ============================================================================

function AlphaFoldChart({ scores }: { scores: number[] }) {
  const data = useMemo(() => scores.map((plddt, i) => ({ position: i + 1, plddt })), [scores])

  if (!scores?.length) return null

  const getColor = (plddt: number) => {
    if (plddt >= 90) return '#1a9850'
    if (plddt >= 70) return '#91cf60'
    if (plddt >= 50) return '#fee08b'
    return '#d73027'
  }

  const avg = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)

  return (
    <div>
      <div className="text-sm font-medium mb-1">AlphaFold pLDDT 逐残基质量</div>
      <div className="text-xs text-gray-500 mb-2">
        均值 <strong>{avg}</strong> · 长度 {scores.length} aa
        <span className="ml-3 inline-flex gap-1">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#1a9850' }} />
          <span className="text-[10px]">≥90</span>
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#91cf60' }} />
          <span className="text-[10px]">70-90</span>
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#fee08b' }} />
          <span className="text-[10px]">50-70</span>
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#d73027' }} />
          <span className="text-[10px]">&lt;50</span>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data}>
          <XAxis dataKey="position" tick={false} axisLine={false} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}`} width={28} />
          <Tooltip
            formatter={(v: unknown) => [`${Number(v).toFixed(1)}`, 'pLDDT']}
            labelFormatter={(i: unknown) => `残基 ${i}`}
          />
          <Bar dataKey="plddt" radius={[0, 0, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.position} fill={getColor(d.plddt)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
