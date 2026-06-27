import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Search, Database, Beaker, Dna, Microscope, FlaskConical, Loader2, X, BarChart3 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import SmilesDrawerNS from 'smiles-drawer'
import { api } from '../lib/api'

type Tab = 'search' | 'substrates' | 'stats'

export default function DataBrowser() {
  const [tab, setTab] = useState<Tab>('search')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [selectedProtein, setSelectedProtein] = useState<any>(null)
  const [proteinDetail, setProteinDetail] = useState<any>(null)
  const [detailTab, setDetailTab] = useState('overview')

  useEffect(() => { api.getDataStats().then(setStats).catch(() => {}) }, [])

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
    } catch {}
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <Database className="w-6 h-6 text-blue-600" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">数据浏览器</h1>
          <span className="text-sm text-gray-500 ml-2">
            UniProt · PDB · BRENDA · ProThermDB · PubChem · Rhea · EnzEngDB
          </span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats bar */}
        {stats?.counts && (
          <div className="grid grid-cols-4 md:grid-cols-7 gap-3 mb-6">
            {[
              ['酶蛋白', stats.counts.enzyme_records, Dna],
              ['EC分类', stats.counts.ec_numbers, Microscope],
              ['PDB结构', stats.counts.pdb_structures, Database],
              ['动力学', stats.counts.kinetic_parameters, BarChart3],
              ['稳定性', stats.counts.stability_records, FlaskConical],
              ['底物', stats.counts.substrate_compounds, Beaker],
              ['反应', stats.counts.reaction_equations, Search],
            ].map(([label, count, Icon]: any) => (
              <div key={label} className="bg-white dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-200 dark:border-gray-700">
                <Icon className="w-4 h-4 mx-auto mb-1 text-blue-500" />
                <div className="text-lg font-bold text-gray-900 dark:text-white">{count ?? 0}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
          {[
            ['search', '搜索', Search],
            ['substrates', '底物', Beaker],
            ['stats', '统计', BarChart3],
          ].map(([key, label, Icon]: any) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
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
                  {results.results?.proteins?.length > 0 && (
                    <Section title="蛋白质" icon={Dna} count={results.results.proteins.length}>
                      {results.results.proteins.map((p: any) => (
                        <ResultRow key={p.uniprot_id} onClick={() => selectProtein(p.uniprot_id)}>
                          <span className="font-mono text-blue-600 dark:text-blue-400 text-sm">
                            <Highlight text={p.uniprot_id} query={query} />
                          </span>
                          <span className="text-sm text-gray-700 dark:text-gray-300 ml-3">
                            <Highlight text={p.name || p.gene} query={query} />
                          </span>
                          {p.gene && <span className="text-xs text-gray-400 ml-2">(<Highlight text={p.gene} query={query} />)</span>}
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {results.results?.substrates?.length > 0 && (
                    <Section title="底物化合物" icon={Beaker} count={results.results.substrates.length}>
                      {results.results.substrates.map((s: any) => (
                        <ResultRow key={s.cid}>
                          <span className="text-sm font-medium"><Highlight text={s.name} query={query} /></span>
                          <span className="text-xs text-gray-400 ml-2">{s.formula}</span>
                          <span className="text-xs font-mono text-gray-400 ml-2">CID:{s.cid}</span>
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {results.results?.ec_numbers?.length > 0 && (
                    <Section title="EC分类" icon={Microscope} count={results.results.ec_numbers.length}>
                      {results.results.ec_numbers.map((ec: any) => (
                        <ResultRow key={ec.ec}>
                          <span className="font-mono text-green-600 dark:text-green-400 text-sm">
                            <Highlight text={ec.ec} query={query} />
                          </span>
                          <span className="text-sm text-gray-700 dark:text-gray-300 ml-3">
                            <Highlight text={ec.name} query={query} />
                          </span>
                        </ResultRow>
                      ))}
                    </Section>
                  )}

                  {results.results?.reactions?.length > 0 && (
                    <Section title="反应方程" icon={FlaskConical} count={results.results.reactions.length}>
                      {results.results.reactions.map((r: any) => (
                        <ResultRow key={r.rhea_id}>
                          <span className="font-mono text-purple-600 text-sm">RHEA:{r.rhea_id}</span>
                          <span className="text-sm text-gray-600 dark:text-gray-400 ml-3 truncate max-w-md">
                            <Highlight text={r.equation} query={query} />
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
                  selected={selectedProtein}
                  detailTab={detailTab}
                  setDetailTab={setDetailTab}
                  onClose={() => { setSelectedProtein(null); setProteinDetail(null) }}
                />
              </div>
            )}
          </div>
        )}

        {/* Substrates tab */}
        {tab === 'substrates' && <SubstrateBrowser />}

        {/* Stats tab */}
        {tab === 'stats' && <StatsPanel stats={stats} />}
      </div>
    </div>
  )
}

// ============================================================================
// Sub-components
// ============================================================================

function Section({ title, icon: Icon, count, children }: any) {
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

function ResultRow({ children, onClick }: any) {
  return (
    <div
      onClick={onClick}
      className={`px-4 py-2.5 flex items-center hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
    >
      {children}
    </div>
  )
}

function ProteinDetail({ detail, selected, detailTab, setDetailTab, onClose }: any) {
  if (!detail) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 sticky top-6">
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-blue-600 font-medium">{selected.uniprot_id}</span>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
      </div>
    )
  }

  const tabs = [
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
          {detail.gene_name && <div className="text-xs text-gray-500">Gene: {detail.gene_name}</div>}
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

function OverviewTab({ detail }: any) {
  return (
    <div className="space-y-4 text-sm">
      <KV label="Entry Name" value={detail.entry_name} />
      <KV label="序列长度" value={`${detail.seq_length} aa`} />
      <KV label="生物体" value={detail.organism?.name} />
      {detail.organism?.lineage && <KV label="分类谱系" value={detail.organism.lineage} />}
      <KV label="EC编号" value={detail.ec_numbers?.map((ec: any) => `${ec.ec} (${ec.name || ''})${ec.primary ? ' ★' : ''}`).join(', ')} />
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

function KineticsTab({ data }: any) {
  const params = data?.parameters || []
  if (!params.length) return <Empty text="无动力学数据" />
  return (
    <div className="space-y-2">
      {params.map((p: any, i: number) => (
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

function StabilityTab({ data }: any) {
  const records = data?.records || []
  if (!records.length) return <Empty text="无稳定性数据" />
  return (
    <div className="space-y-2">
      {records.map((r: any, i: number) => (
        <div key={i} className={`bg-gray-50 dark:bg-gray-750 rounded p-3 text-sm border-l-2 ${r.ddg > 0 ? 'border-red-400' : 'border-green-400'}`}>
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

function StructuresTab({ data }: any) {
  const pdb = data?.pdb || []
  const af = data?.alphafold || []
  return (
    <div className="space-y-4">
      {pdb.length > 0 && (
        <div>
          <div className="text-sm font-medium mb-2">PDB 实验结构 ({pdb.length})</div>
          <div className="space-y-2">
            {pdb.map((s: any) => (
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
      {af.map((s: any) => (
        <div key="af">
          <div className="text-sm font-medium mb-2">AlphaFold 预测结构</div>
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-3 text-sm">
            <span>pLDDT: <strong>{s.plddt_mean?.toFixed(1)}</strong></span>
          </div>
          {s.plddt_scores?.length > 0 && (
            <div className="mt-3">
              <AlphaFoldChart scores={s.plddt_scores} />
            </div>
          )}
        </div>
      ))}
      {!pdb.length && !af.length && <Empty text="无结构数据" />}
    </div>
  )
}

function EvolutionTab({ data }: any) {
  const exps = data?.experiments || []
  if (!exps.length) return <Empty text="无定向进化数据" />
  return (
    <div className="space-y-2">
      {exps.map((e: any, i: number) => (
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
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    try { setResults(await api.searchSubstrate(q)) } catch {}
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(results.compound ? [results.compound] : results.results || []).map((c: any) => (
            <div key={c.cid || c.name} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm">
              <div className="font-bold text-gray-900 dark:text-white">{c.name || c.cid}</div>
              {c.iupac && <div className="text-xs text-gray-500 mt-1 line-clamp-2">{c.iupac}</div>}
              {c.smiles && (
                <div className="mt-3">
                  <MoleculeCard smiles={c.smiles} />
                </div>
              )}
              <div className="mt-2 space-y-1 text-xs">
                {c.formula && <div className="font-mono text-gray-600">{c.formula}</div>}
                {c.weight && <div>MW: {c.weight}</div>}
                {c.smiles && <div className="font-mono text-gray-500 truncate">SMILES: {c.smiles}</div>}
                {c.xlogp != null && <div>LogP: {c.xlogp}</div>}
                {c.tpsa != null && <div>TPSA: {c.tpsa}</div>}
                {c.inchikey && <div className="font-mono text-gray-400 truncate text-[10px]">{c.inchikey}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatsPanel({ stats }: any) {
  const counts = stats?.counts || {}
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Object.entries(counts).map(([k, v]: any) => (
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

function MoleculeCard({ smiles, name }: { smiles: string; name?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current || !smiles) return
    try {
      SmilesDrawerNS.parse(
        smiles,
        (tree: any) => {
          const drawer = new SmilesDrawerNS.SmilesDrawer()
          drawer.draw(tree, canvasRef.current!, 'light', {
            bondThickness: 1.4,
            shortBondLength: 0.82,
            bondSpacing: 0.16,
            compactDrawing: true,
          })
        },
        () => {} // silently ignore parse errors
      )
    } catch {}
  }, [smiles])

  return (
    <div className="bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700 p-3 flex flex-col items-center gap-2">
      {name && <div className="text-xs font-medium text-gray-500 truncate max-w-full">{name}</div>}
      <canvas ref={canvasRef} width={220} height={160} className="max-w-full" />
    </div>
  )
}

// ============================================================================
// AlphaFoldChart — per-residue pLDDT bar chart via recharts
// ============================================================================

function AlphaFoldChart({ scores }: { scores: number[] }) {
  if (!scores?.length) return null

  const data = useMemo(() => scores.map((plddt, i) => ({ position: i + 1, plddt })), [scores])

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
