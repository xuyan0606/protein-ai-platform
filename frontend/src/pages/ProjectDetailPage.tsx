import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Play, Loader2, CheckCircle2, XCircle, Dna, Beaker, Zap, History, BookOpen, FileText, ChevronDown, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { MarkdownView } from '@/components/chat/MarkdownView'

interface SeqItem { id: string; name: string; sequence: string; notes?: string; created_at: string }
interface BatchItem { id: string; status: string; total: number; completed: number; results?: any; created_at: string }
interface ProjectData { id: string; name: string; description?: string; sequences: SeqItem[]; batch_jobs: BatchItem[] }
interface WikiFile { id: string; filename: string; sequence_name: string; file_type: string; object_name: string; size: number; created_at: string }
interface WikiGroup { tool: string; job_id: string; files: WikiFile[] }
interface WikiCollection { name: string; groups: WikiGroup[] }

const BATCH_TOOLS = [
  { id: 'protein_benchmark', label: 'Benchmark', icon: Beaker },
  { id: 'mutation_priority_score', label: 'Mutation Score', icon: Zap },
  { id: 'predict_properties', label: 'Properties', icon: Dna },
]

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectData | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAddSeq, setShowAddSeq] = useState(false)
  const [seqName, setSeqName] = useState('')
  const [seqData, setSeqData] = useState('')
  const [seqNotes, setSeqNotes] = useState('')
  const [adding, setAdding] = useState(false)
  const [running, setRunning] = useState(false)
  const [activeTab, setActiveTab] = useState<'sequences' | 'results' | 'wiki'>('sequences')
  const [selectedTool, setSelectedTool] = useState('protein_benchmark')
  const [wikiTree, setWikiTree] = useState<WikiCollection[]>([])
  const [selectedWikiFile, setSelectedWikiFile] = useState<{ projectId: string; fileId: string; filename: string } | null>(null)
  const [wikiContent, setWikiContent] = useState<string>('')
  const [wikiLoading, setWikiLoading] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  const fetchWikiTree = async () => {
    if (!id) return
    try {
      const files: any[] = await api.getProjectFiles(id)
      // Group files by source (batch, agent, upload) into WikiCollection structure
      const groupsBySource = new Map<string, WikiGroup>()
      for (const f of files) {
        const source = f.source || 'general'
        const job_id = f.tags?.batch_job_id || 'default'
        const key = `${source}:${job_id}`
        if (!groupsBySource.has(key)) {
          groupsBySource.set(key, { tool: source, job_id, files: [] })
        }
        groupsBySource.get(key)!.files.push(f as WikiFile)
      }
      const collections: WikiCollection[] = [{ name: '项目文件', groups: Array.from(groupsBySource.values()) }]
      setWikiTree(collections)
    } catch { /* ignore */ }
  }

  const handleViewWikiFile = async (projectId: string, fileId: string, filename: string) => {
    setSelectedWikiFile({ projectId, fileId, filename })
    setWikiLoading(true)
    try {
      const content = await api.getFileContent(projectId, fileId)
      setWikiContent(content)
    } catch {
      setWikiContent('Failed to load file content.')
    } finally {
      setWikiLoading(false)
    }
  }

  const toggleGroup = (key: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const fetchProject = async () => {
    if (!id) return
    try {
      setLoading(true)
      const data = await api.getProject(id)
      setProject(data)
    } catch { navigate('/projects') } finally { setLoading(false) }
  }

  useEffect(() => {
    fetchProject()
    fetchWikiTree()
  }, [id])

  useEffect(() => {
    if (activeTab === 'wiki') fetchWikiTree()
  }, [activeTab])

  const handleAddSeq = async () => {
    if (!id || !seqName.trim() || !seqData.trim()) return
    setAdding(true)
    try {
      await api.addSequence(id, seqName.trim(), seqData.trim(), seqNotes.trim() || undefined)
      setShowAddSeq(false)
      setSeqName('')
      setSeqData('')
      setSeqNotes('')
      fetchProject()
    } catch { /* ignore */ } finally { setAdding(false) }
  }

  const handleRemoveSeq = async (seqId: string) => {
    if (!id) return
    try {
      await api.removeSequence(id, seqId)
      fetchProject()
    } catch { /* ignore */ }
  }

  const handleBatchRun = async () => {
    if (!id) return
    setRunning(true)
    try {
      await api.batchRun(id, selectedTool)
      fetchProject()
      fetchWikiTree()  // Refresh wiki after batch auto-publish
    } catch { /* ignore */ } finally { setRunning(false) }
  }

  const batchResults = useMemo(() => {
    if (!project?.batch_jobs?.length) return []
    return project.batch_jobs.flatMap((job) => {
      if (!job.results?.items) return []
      return job.results.items.map((item: any) => ({
        ...item,
        jobId: job.id,
        jobStatus: job.status,
        jobDate: job.created_at,
        tool: job.results?.tool,
      }))
    })
  }, [project?.batch_jobs])

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!project) return null

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-1">
          <button onClick={() => navigate('/projects')} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-bold">{project.name}</h1>
        </div>
        {project.description && (
          <p className="text-sm text-muted-foreground ml-11 mb-6">{project.description}</p>
        )}

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-secondary rounded-lg p-0.5 w-fit mb-6">
          {[
            { key: 'sequences', label: `Sequences (${project.sequences.length})`, icon: Dna },
            { key: 'results', label: `Results (${batchResults.length})`, icon: History },
            { key: 'wiki', label: `Wiki (${wikiTree.reduce((acc, c) => acc + c.groups.length, 0)})`, icon: BookOpen },
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  activeTab === tab.key ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Sequences Tab */}
        {activeTab === 'sequences' && (
          <div>
            {/* Add button */}
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">
                Manage protein sequences for batch analysis
              </p>
              <button
                onClick={() => setShowAddSeq(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Sequence
              </button>
            </div>

            {/* Add sequence form */}
            {showAddSeq && (
              <div className="bg-card border border-border rounded-xl p-4 mb-4 space-y-3">
                <input
                  autoFocus
                  value={seqName}
                  onChange={(e) => setSeqName(e.target.value)}
                  placeholder="Sequence name (e.g. 'BLA-WT')"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm focus:outline-none focus:border-ring"
                />
                <textarea
                  value={seqData}
                  onChange={(e) => setSeqData(e.target.value.toUpperCase())}
                  placeholder="Amino acid sequence (single-letter code)"
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm font-mono focus:outline-none focus:border-ring resize-none"
                />
                <input
                  value={seqNotes}
                  onChange={(e) => setSeqNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm focus:outline-none focus:border-ring"
                />
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setShowAddSeq(false)} className="px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary rounded-lg">Cancel</button>
                  <button onClick={handleAddSeq} disabled={!seqName.trim() || !seqData.trim() || adding} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-xs font-medium rounded-lg disabled:opacity-40">
                    {adding && <Loader2 className="w-3 h-3 animate-spin" />}
                    Add
                  </button>
                </div>
              </div>
            )}

            {/* Sequence list */}
            {project.sequences.length === 0 ? (
              <div className="text-center py-16 bg-card border border-border rounded-xl">
                <Dna className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">No sequences in this project</p>
                <p className="text-sm text-muted-foreground/70 mt-1">Add sequences to start batch analysis</p>
              </div>
            ) : (
              <div className="space-y-2">
                {project.sequences.map((seq) => (
                  <div key={seq.id} className="group flex items-start gap-4 bg-card border border-border rounded-xl p-4">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                      <Dna className="w-4 h-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium">{seq.name}</h4>
                      <code className="text-xs text-muted-foreground break-all font-mono mt-1 block">{seq.sequence.length > 80 ? seq.sequence.slice(0, 80) + '...' : seq.sequence}</code>
                      {seq.notes && <p className="text-[10px] text-muted-foreground mt-1">{seq.notes}</p>}
                    </div>
                    <button
                      onClick={() => handleRemoveSeq(seq.id)}
                      className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Batch Run Panel */}
            {project.sequences.length > 0 && (
              <div className="mt-6 bg-card border border-border rounded-xl p-4">
                <h3 className="font-semibold text-sm mb-3">Batch Analysis</h3>
                <div className="flex flex-wrap items-end gap-3">
                  <div>
                    <label className="text-[10px] text-muted-foreground block mb-1">Tool</label>
                    <div className="flex gap-1">
                      {BATCH_TOOLS.map((tool) => {
                        const Icon = tool.icon
                        return (
                          <button
                            key={tool.id}
                            onClick={() => setSelectedTool(tool.id)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                              selectedTool === tool.id ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
                            }`}
                          >
                            <Icon className="w-3 h-3" />
                            {tool.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                  <button
                    onClick={handleBatchRun}
                    disabled={running}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-emerald-500 text-white text-xs font-medium hover:bg-emerald-600 disabled:opacity-40"
                  >
                    {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                    {running ? 'Running...' : `Run on ${project.sequences.length} sequences`}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && (
          <div>
            {batchResults.length === 0 ? (
              <div className="text-center py-16 bg-card border border-border rounded-xl">
                <History className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">No analysis results yet</p>
                <p className="text-sm text-muted-foreground/70 mt-1">Run a batch analysis on your sequences</p>
              </div>
            ) : (
              <div className="space-y-2">
                {batchResults.map((r: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 bg-card border border-border rounded-xl p-4">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${r.status === 'completed' ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                      {r.status === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-medium text-sm">{r.sequence_name}</span>
                        <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 bg-secondary rounded">{r.tool}</span>
                      </div>
                      {r.status === 'completed' && r.result && (
                        <details className="mt-1">
                          <summary className="text-xs text-primary cursor-pointer hover:underline">View results</summary>
                          <pre className="mt-2 text-[10px] text-muted-foreground bg-secondary/30 rounded-lg p-3 overflow-x-auto max-h-48">
                            {JSON.stringify(r.result, null, 2)}
                          </pre>
                        </details>
                      )}
                      {r.error && <p className="text-xs text-red-400 mt-1">{r.error}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Wiki Tab */}
        {activeTab === 'wiki' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Wiki sidebar tree */}
            <div className="lg:col-span-1 bg-card border border-border rounded-xl p-4 max-h-[70vh] overflow-y-auto">
              <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4" />
                知识库
              </h3>
              {wikiTree.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">暂无Wiki文档</p>
                  <p className="text-[10px] text-muted-foreground/70 mt-1">运行批量分析后自动生成</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {wikiTree.map((col, ci) => (
                    <div key={ci}>
                      <div className="text-xs font-medium text-muted-foreground px-2 py-1">{col.name}</div>
                      {col.groups.map((group, gi) => {
                        const groupKey = `${group.tool}:${group.job_id}`
                        const isExpanded = expandedGroups.has(groupKey)
                        return (
                          <div key={gi} className="ml-2">
                            <button
                              onClick={() => toggleGroup(groupKey)}
                              className="flex items-center gap-1.5 w-full text-left px-2 py-1 rounded text-xs hover:bg-secondary transition-colors"
                            >
                              {isExpanded ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
                              <span className="truncate">{group.tool}</span>
                              <span className="text-[10px] text-muted-foreground ml-auto">{group.files.length}</span>
                            </button>
                            {isExpanded && (
                              <div className="ml-4 space-y-0.5">
                                {group.files.map((f, fi) => (
                                  <button
                                    key={fi}
                                    onClick={() => id && handleViewWikiFile(id, f.id, f.filename)}
                                    className={`flex items-center gap-1.5 w-full text-left px-2 py-1 rounded text-[11px] transition-colors ${
                                      selectedWikiFile?.filename === f.filename
                                        ? 'bg-primary/10 text-primary'
                                        : 'hover:bg-secondary text-muted-foreground'
                                    }`}
                                  >
                                    <FileText className="w-3 h-3 shrink-0" />
                                    <span className="truncate">{f.sequence_name === '__summary__' ? '📊 汇总' : f.sequence_name}</span>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Wiki content viewer */}
            <div className="lg:col-span-2 bg-card border border-border rounded-xl p-4 min-h-[50vh] max-h-[70vh] overflow-y-auto">
              {selectedWikiFile ? (
                wikiLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <div>
                    <h3 className="font-semibold text-sm mb-3 pb-2 border-b border-border">{selectedWikiFile.filename}</h3>
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <MarkdownView content={wikiContent} />
                    </div>
                  </div>
                )
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <BookOpen className="w-12 h-12 text-muted-foreground/20 mb-4" />
                  <p className="text-sm text-muted-foreground">选择左侧文档查看内容</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">批量分析结果会自动生成为Wiki页面</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
