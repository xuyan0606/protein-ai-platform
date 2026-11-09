import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Play, Loader2, CheckCircle2, XCircle, Dna, Beaker, Zap, History, BookOpen, FileText, ChevronDown, ChevronRight, Search, Activity, ClipboardList, AlertTriangle, FlaskConical, Layers3, RefreshCw, Download } from 'lucide-react'
import { api, type ApiRecord, type ProjectAccessRole, type ProjectDbtlTrace, type ProjectPermissions } from '@/lib/api'
import { downloadReport } from '@/lib/report'
import { MarkdownView } from '@/components/chat/MarkdownView'

interface SeqItem { id: string; name: string; sequence: string; notes?: string | null; created_at: string }
type ProjectDetailTab = 'sequences' | 'results' | 'wiki' | 'dbtl'
type BatchResultItem = ApiRecord & {
  status?: string
  sequence_name?: string
  tool?: string
  result?: unknown
  error?: string
  jobId?: string
  jobStatus?: string
  jobDate?: string
}
type BatchResultsPayload = ApiRecord & { items?: BatchResultItem[]; tool?: string }
interface BatchItem { id: string; status: string; total: number; completed: number; results?: BatchResultsPayload; created_at: string }
interface ProjectData { id: string; name: string; description?: string | null; access_role: ProjectAccessRole; permissions?: ProjectPermissions; sequences: SeqItem[]; batch_jobs: BatchItem[] }
interface WikiFile { id: string; filename: string; sequence_name: string; file_type: string; object_name: string; size: number; created_at: string }
type ProjectFileRecord = WikiFile & { source?: string | null; tags?: { batch_job_id?: string | null } | null }
interface WikiGroup { tool: string; job_id: string; files: WikiFile[] }
interface WikiCollection { name: string; groups: WikiGroup[] }

const BATCH_TOOLS = [
  { id: 'protein_benchmark', label: 'Benchmark', icon: Beaker },
  { id: 'mutation_priority_score', label: 'Mutation Score', icon: Zap },
  { id: 'predict_properties', label: 'Properties', icon: Dna },
  { id: 'mutation_scan', label: 'Scan', icon: Search },
  { id: 'rosetta_ddg', label: 'Rosetta ddG', icon: Beaker },
]

function isRecord(value: unknown): value is ApiRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asRecord(value: unknown): ApiRecord {
  return isRecord(value) ? value : {}
}

function asRecordArray(value: unknown): ApiRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || '').trim()).filter(Boolean)
    : []
}

function displayText(value: unknown, fallback = 'unknown') {
  const text = String(value ?? '').trim()
  return text || fallback
}

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
  const [activeTab, setActiveTab] = useState<ProjectDetailTab>('sequences')
  const [selectedTool, setSelectedTool] = useState('protein_benchmark')
  const [wikiTree, setWikiTree] = useState<WikiCollection[]>([])
  const [selectedWikiFile, setSelectedWikiFile] = useState<{ projectId: string; fileId: string; filename: string } | null>(null)
  const [wikiContent, setWikiContent] = useState<string>('')
  const [wikiLoading, setWikiLoading] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [dbtlTrace, setDbtlTrace] = useState<ProjectDbtlTrace | null>(null)
  const [dbtlLoading, setDbtlLoading] = useState(false)
  const [dbtlError, setDbtlError] = useState<string | null>(null)

  const fetchWikiTree = useCallback(async () => {
    if (!id) return
    try {
      const files = await api.getProjectFiles(id) as unknown as ProjectFileRecord[]
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
  }, [id])

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

  const fetchProject = useCallback(async () => {
    if (!id) return
    try {
      setLoading(true)
      const data = await api.getProject(id)
      setProject(data)
    } catch { navigate('/projects') } finally { setLoading(false) }
  }, [id, navigate])

  const fetchDbtlTrace = useCallback(async () => {
    if (!id) return
    setDbtlLoading(true)
    setDbtlError(null)
    try {
      const data = await api.getProjectDbtlTrace(id)
      setDbtlTrace(data)
    } catch (err) {
      setDbtlTrace(null)
      setDbtlError(err instanceof Error ? err.message : 'Failed to load DBTL trace')
    } finally {
      setDbtlLoading(false)
    }
  }, [id])

  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      void fetchProject()
      void fetchWikiTree()
      void fetchDbtlTrace()
    })
    return () => {
      cancelled = true
    }
  }, [fetchDbtlTrace, fetchProject, fetchWikiTree])

  useEffect(() => {
    if (activeTab !== 'wiki') return
    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) void fetchWikiTree()
    })
    return () => {
      cancelled = true
    }
  }, [activeTab, fetchWikiTree])

  const handleAddSeq = async () => {
    if (!id || !seqName.trim() || !seqData.trim()) return
    setAdding(true)
    try {
      await api.addSequence(id, seqName.trim(), seqData.trim(), seqNotes.trim() || undefined)
      setShowAddSeq(false)
      setSeqName('')
      setSeqData('')
      setSeqNotes('')
      void fetchProject()
    } catch { /* ignore */ } finally { setAdding(false) }
  }

  const handleRemoveSeq = async (seqId: string) => {
    if (!id) return
    try {
      await api.removeSequence(id, seqId)
      void fetchProject()
    } catch { /* ignore */ }
  }

  const handleBatchRun = async () => {
    if (!id) return
    setRunning(true)
    try {
      await api.batchRun(id, selectedTool)
      void fetchProject()
      void fetchWikiTree()  // Refresh wiki after batch auto-publish
    } catch { /* ignore */ } finally { setRunning(false) }
  }

  const batchJobs = project?.batch_jobs
  const batchResults = useMemo(() => {
    if (!batchJobs?.length) return []
    return batchJobs.flatMap((job): BatchResultItem[] => {
      if (!job.results?.items) return []
      return job.results.items.map((item) => ({
        ...item,
        jobId: job.id,
        jobStatus: job.status,
        jobDate: job.created_at,
        tool: job.results?.tool,
      }))
    })
  }, [batchJobs])

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!project) return null
  const canCreateSequence = project.permissions?.['project.sequence.create'] ?? (project.access_role === 'owner' || project.access_role === 'editor')
  const canDeleteSequence = project.permissions?.['project.sequence.delete'] ?? (project.access_role === 'owner' || project.access_role === 'editor')
  const canRunBatch = project.permissions?.['project.batch.run'] ?? (project.access_role === 'owner' || project.access_role === 'editor')

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-1">
          <button onClick={() => navigate('/projects')} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-xl font-bold">{project.name}</h1>
          <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {project.access_role}
          </span>
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
            { key: 'dbtl', label: 'DBTL', icon: Activity },
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as ProjectDetailTab)}
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
              {canCreateSequence && (
                <button
                  onClick={() => setShowAddSeq(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Sequence
                </button>
              )}
            </div>

            {/* Add sequence form */}
            {canCreateSequence && showAddSeq && (
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
                    {canDeleteSequence && (
                      <button
                        onClick={() => handleRemoveSeq(seq.id)}
                        className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Batch Run Panel */}
            {canRunBatch && project.sequences.length > 0 && (
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
                {batchResults.map((r, i) => (
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
                      {r.status === 'completed' && r.result != null && (
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

        {activeTab === 'dbtl' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">DBTL trace summary</p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => dbtlTrace && downloadReport('project_dbtl_trace', dbtlTrace)}
                  disabled={!dbtlTrace}
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary disabled:opacity-50"
                  title="Download DBTL trace report"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download
                </button>
                <button
                  onClick={() => { void fetchDbtlTrace() }}
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refresh
                </button>
              </div>
            </div>

            {dbtlLoading ? (
              <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-5 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading DBTL trace
              </div>
            ) : dbtlError ? (
              <div className="rounded-xl border border-border bg-card px-4 py-5 text-sm text-muted-foreground">
                {dbtlError}
              </div>
            ) : dbtlTrace ? (
              <>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {[
                    { label: 'Project Memory', value: dbtlTrace.trace_summary.project_memory_status, icon: Layers3 },
                    { label: 'Learning', value: dbtlTrace.trace_summary.learning_status, icon: FlaskConical },
                    { label: 'Next Round', value: dbtlTrace.trace_summary.next_round_status, icon: ClipboardList },
                    { label: 'Formal Decision', value: dbtlTrace.trace_summary.formal_decision_status, icon: AlertTriangle },
                  ].map((item) => {
                    const Icon = item.icon
                    return (
                      <div key={item.label} className="rounded-xl border border-border bg-card p-4">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Icon className="w-3.5 h-3.5" />
                          {item.label}
                        </div>
                        <div className="mt-2 text-sm font-medium">{item.value}</div>
                      </div>
                    )
                  })}
                </div>

                <ProjectMemoryReadinessPanel readiness={dbtlTrace.trace_summary.project_memory_readiness} />
                <ReadinessBridgePanel readiness={dbtlTrace.trace_summary.readiness_bridge} />
                <FeedbackReadinessPanel readiness={dbtlTrace.trace_summary.feedback_readiness} />
                <NextRoundConstraintsPanel design={dbtlTrace.next_round_library_design} />
                <P4ClosedLoopReadinessPanel readiness={dbtlTrace.trace_summary.p4_closed_loop_readiness} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.3fr_0.7fr]">
                  <div className="rounded-xl border border-border bg-card p-4">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <ClipboardList className="w-4 h-4" />
                      Required Actions
                    </div>
                    <div className="mt-3 space-y-2">
                      {dbtlTrace.trace_summary.required_actions.length === 0 ? (
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
                          No blocking actions.
                        </div>
                      ) : (
                        dbtlTrace.trace_summary.required_actions.map((action) => (
                          <div key={action.action} className="rounded-lg border border-border px-3 py-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-sm font-medium">{action.action}</div>
                              <div className="flex shrink-0 flex-wrap justify-end gap-1">
                                {action.priority && (
                                  <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                                    {action.priority}
                                  </span>
                                )}
                                {action.category && (
                                  <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                                    {action.category}
                                  </span>
                                )}
                              </div>
                            </div>
                            {action.blocks && action.blocks.length > 0 && (
                              <div className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                                {action.blocks.join(' · ')}
                              </div>
                            )}
                            <p className="mt-1 text-xs text-muted-foreground">{action.reason}</p>
                            {action.top_missing_reasons && action.top_missing_reasons.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {action.top_missing_reasons.map((missing) => (
                                  <span key={missing.reason} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                                    {missing.reason}: {missing.count}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-xl border border-border bg-card p-4">
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Rounds</div>
                          <div className="mt-1 font-medium">{dbtlTrace.trace_summary.counts.rounds}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Variants</div>
                          <div className="mt-1 font-medium">{dbtlTrace.trace_summary.counts.variants}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Feedback</div>
                          <div className="mt-1 font-medium">{dbtlTrace.trace_summary.counts.feedback_records}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Training-ready</div>
                          <div className="mt-1 font-medium">{dbtlTrace.trace_summary.counts.training_eligible_feedback_records}</div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-border bg-card p-4">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <AlertTriangle className="w-4 h-4" />
                        Missing
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {dbtlTrace.trace_summary.missing_entities.length === 0 ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                            none
                          </span>
                        ) : (
                          dbtlTrace.trace_summary.missing_entities.map((item) => (
                            <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                              {item}
                            </span>
                          ))
                        )}
                      </div>
                      <div className="mt-3 text-xs text-muted-foreground">
                        {dbtlTrace.trace_summary.report_contract.must_not_claim_training_or_wet_lab_validation
                          ? 'Computational outputs stay labeled as hypothesis.'
                          : ''}
                      </div>
                    </div>

                    <details className="rounded-xl border border-border bg-card p-4">
                      <summary className="cursor-pointer text-sm font-medium">Raw trace</summary>
                      <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-secondary/30 p-3 text-[10px] text-muted-foreground">
{JSON.stringify({
  project_model: dbtlTrace.project_model,
  learning_readiness: dbtlTrace.learning_readiness,
  next_round_library_design: dbtlTrace.next_round_library_design,
  trace_summary: dbtlTrace.trace_summary,
}, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-border bg-card px-4 py-5 text-sm text-muted-foreground">
                DBTL trace unavailable.
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
                    <MarkdownView content={wikiContent} />
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

function FeedbackReadinessPanel({ readiness }: { readiness?: ProjectDbtlTrace['trace_summary']['feedback_readiness'] }) {
  if (!readiness) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FlaskConical className="w-4 h-4" />
          Feedback Readiness
        </div>
        <p className="mt-2 text-xs text-muted-foreground">No feedback readiness contract in this DBTL trace.</p>
      </section>
    )
  }

  const qc = readiness.assay_qc_summary || {
    qc_status_counts: {},
    formal_decision_counts: {},
    assay_condition_counts: {},
    replicate_counts: {},
    measured_metric_counts: {},
  }
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <FlaskConical className="w-4 h-4" />
            Feedback Readiness
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {displayText(readiness.schema_version, 'dbtl_feedback_readiness_summary_v1')} · {displayText(readiness.status, 'unknown')} · read-only {readiness.read_only ? 'yes' : 'unknown'}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded-full bg-secondary px-2 py-0.5">
            records {displayText(readiness.record_count, '0')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            training-ready {displayText(readiness.training_eligible_count, '0')} / {displayText(readiness.training_batch_minimum, '12')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            next round {displayText(readiness.next_round_constraint_status, 'blocked')}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {([
          ['QC', qc.qc_status_counts],
          ['Assay conditions', qc.assay_condition_counts],
          ['Replicates', qc.replicate_counts],
          ['Measured metrics', qc.measured_metric_counts],
        ] as Array<[string, Record<string, number>]>).map(([label, values]) => (
          <div key={label} className="rounded-lg border border-border p-3">
            <div className="text-xs font-medium">{label}</div>
            <div className="mt-2 space-y-1">
              {Object.entries(values as Record<string, number>).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                  <span className="font-mono">{key}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {readiness.top_missing_for_training.length > 0 ? (
        <div className="mt-3">
          <div className="text-xs font-medium">Top missing training evidence</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {readiness.top_missing_for_training.map((item) => (
              <span key={item.reason} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {item.reason}: {item.count}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {readiness.must_not_claim.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {readiness.must_not_claim.map((item) => (
            <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              no claim: {item}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function ReadinessBridgePanel({ readiness }: { readiness?: ProjectDbtlTrace['trace_summary']['readiness_bridge'] }) {
  if (!readiness) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <ClipboardList className="w-4 h-4" />
          Readiness Bridge
        </div>
        <p className="mt-2 text-xs text-muted-foreground">No readiness bridge contract in this DBTL trace.</p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <ClipboardList className="w-4 h-4" />
            Readiness Bridge
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {displayText(readiness.schema_version, 'dbtl_readiness_bridge_v1')} · {displayText(readiness.status, 'unknown')} · read-only {readiness.read_only ? 'yes' : 'unknown'}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded-full bg-secondary px-2 py-0.5">
            project memory {displayText(readiness.project_memory_readiness_status)}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            feedback {displayText(readiness.feedback_readiness_status)}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            next round {displayText(readiness.next_round_constraint_status)}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Downstream Status Views</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {asStringArray(readiness.downstream_status_views).map((item) => (
              <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {item}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Required Actions</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {asStringArray(readiness.required_actions).map((item) => (
              <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>

      {readiness.combination_evidence_status ? (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Combination evidence: {readiness.combination_evidence_status}
        </p>
      ) : null}

      {readiness.must_not_claim.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {readiness.must_not_claim.map((item) => (
            <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              {item}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function ProjectMemoryReadinessPanel({ readiness }: { readiness?: ProjectDbtlTrace['trace_summary']['project_memory_readiness'] }) {
  if (!readiness) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Layers3 className="w-4 h-4" />
          Project Memory Readiness
        </div>
        <p className="mt-2 text-xs text-muted-foreground">No project memory readiness contract in this DBTL trace.</p>
      </section>
    )
  }

  const entities = Object.entries(readiness.entity_status || {})
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <Layers3 className="w-4 h-4" />
            Project Memory Readiness
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {displayText(readiness.schema_version, 'dbtl_project_memory_readiness_v1')} · {displayText(readiness.status, 'unknown')} · read-only {readiness.read_only ? 'yes' : 'unknown'}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded-full bg-secondary px-2 py-0.5">
            ready {displayText(readiness.ready_entity_count, '0')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            missing {displayText(readiness.missing_entity_count, '0')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            fraction {displayText(readiness.readiness_fraction, '0')}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {entities.map(([name, entity]) => (
          <div key={name} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="font-mono text-xs font-medium">{name}</div>
              <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {displayText(entity.status)}
              </span>
            </div>
            <div className="mt-2 text-[11px] text-muted-foreground">
              count {displayText(entity.count, '0')}
            </div>
          </div>
        ))}
      </div>

      {readiness.must_not_claim.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {readiness.must_not_claim.map((item) => (
            <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              {item}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function P4ClosedLoopReadinessPanel({ readiness }: { readiness?: ProjectDbtlTrace['trace_summary']['p4_closed_loop_readiness'] }) {
  if (!readiness) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Activity className="w-4 h-4" />
          P4 Closed Loop Readiness
        </div>
        <p className="mt-2 text-xs text-muted-foreground">No P4 readiness contract in this DBTL trace.</p>
      </section>
    )
  }

  const gates = Object.entries(readiness.gates || {})
  const contracts = [
    ['Active Learning Batch', readiness.active_learning_batch_contract],
    ['Model Calibration Registry', readiness.model_calibration_registry_contract],
    ['Manufacturing Constraints', readiness.manufacturing_constraint_contract],
    ['Operator Review', readiness.operator_review_contract],
  ] as Array<[string, {
    schema_version?: string
    status?: string
    read_only?: boolean
    blocked_reasons?: string[]
    must_not_claim?: string[]
  } | undefined]>
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <Activity className="w-4 h-4" />
            P4 Closed Loop Readiness
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {displayText(readiness.schema_version, 'p4_closed_loop_readiness_v1')} · {displayText(readiness.status, 'blocked')} · read-only {readiness.read_only ? 'yes' : 'unknown'}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded-full bg-secondary px-2 py-0.5">
            blocked {asStringArray(readiness.blocked_gates).length}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            actions {displayText(readiness.required_action_count, '0')}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {contracts.map(([label, contract]) => (
          <div key={label} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-medium">{label}</div>
              <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {displayText(contract?.status, 'missing_contract')}
              </span>
            </div>
            <div className="mt-2 text-[11px] text-muted-foreground">
              {displayText(contract?.schema_version, 'contract_not_available')} · read-only {contract?.read_only ? 'yes' : 'unknown'}
            </div>
            {Array.isArray(contract?.blocked_reasons) && contract.blocked_reasons.length > 0 ? (
              <div className="mt-2 space-y-1">
                {contract.blocked_reasons.slice(0, 3).map((reason) => (
                  <div key={reason} className="font-mono text-[11px] text-muted-foreground">{reason}</div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {gates.map(([name, gate]) => (
          <div key={name} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="font-mono text-xs font-medium">{name}</div>
              <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                {displayText(gate.status)}
              </span>
            </div>
            {Array.isArray(gate.requires) && gate.requires.length > 0 ? (
              <div className="mt-2 space-y-1">
                {gate.requires.slice(0, 3).map((item) => (
                  <div key={item} className="text-[11px] text-muted-foreground">{item}</div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {readiness.must_not_claim.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {readiness.must_not_claim.map((item) => (
            <span key={item} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              no claim: {item}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function NextRoundConstraintsPanel({ design }: { design: ApiRecord }) {
  const sourceEvidence = asRecord(design.source_evidence)
  const singlePointPool = asRecordArray(design.single_point_pool)
  const combinationPool = asRecordArray(design.combination_pool)
  const explorationPool = asRecordArray(design.exploration_pool)
  const plateLayout = asRecordArray(design.plate_layout)
  const assayRequired = asStringArray(design.assay_required)
  const allocationPolicy = asRecord(design.allocation_policy)
  const higherOrderRule = asRecord(design.higher_order_rule)
  const combinationEvidenceContract = asRecord(design.combination_evidence_contract)
  const hasDesign = Object.keys(design || {}).length > 0

  if (!hasDesign) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <ClipboardList className="w-4 h-4" />
          Next Round Constraints
        </div>
        <p className="mt-2 text-xs text-muted-foreground">No next-round design contract in the selected DBTL trace.</p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <ClipboardList className="w-4 h-4" />
            Next Round Constraints
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {displayText(design.status)} · objective {displayText(design.objective)}
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            structural distance source: {displayText(design.structural_distance_source, 'none')}
          </div>
          {Object.keys(combinationEvidenceContract).length > 0 ? (
            <div className="mt-1 text-[11px] text-muted-foreground">
              combination evidence contract: {displayText(combinationEvidenceContract.status)}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
          <span className="rounded-full bg-secondary px-2 py-0.5">
            singletons {displayText(sourceEvidence.validated_single_mutants, '0')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            pairs {displayText(sourceEvidence.eligible_pair_candidates, '0')}
          </span>
          <span className="rounded-full bg-secondary px-2 py-0.5">
            quality {displayText(sourceEvidence.data_quality_level)}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Single Point Pool</div>
          <div className="mt-2 space-y-2">
            {singlePointPool.length > 0 ? singlePointPool.map((item, index) => (
              <div key={`${displayText(item.mutation)}:${index}`} className="rounded-md bg-secondary/40 px-2.5 py-2 text-xs">
                <div className="font-mono font-medium">{displayText(item.mutation)}</div>
                <div className="mt-1 text-muted-foreground">
                  {displayText(item.variant_name, 'variant unknown')} · {displayText(item.use)}
                </div>
              </div>
            )) : (
              <div className="text-xs text-muted-foreground">No validated single-mutant pool.</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Combination Pool</div>
          <div className="mt-2 space-y-2">
            {combinationPool.length > 0 ? combinationPool.map((item, index) => (
              <div key={`${displayText(item.status)}:${index}`} className="rounded-md bg-secondary/40 px-2.5 py-2 text-xs">
                <div className="font-mono font-medium">{asStringArray(item.mutations).join(' + ') || 'unknown pair'}</div>
                <div className="mt-1 text-muted-foreground">
                  {displayText(item.status)} · {displayText(item.epistasis_recommendation)}
                </div>
                {Array.isArray(item.distance_sources) && item.distance_sources.length > 0 ? (
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    sources {item.distance_sources.join(' · ')}
                  </div>
                ) : null}
              </div>
            )) : (
              <div className="text-xs text-muted-foreground">No controlled pair promoted.</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Assay And Gate</div>
          <div className="mt-2 space-y-2 text-xs text-muted-foreground">
            <p>{displayText(higherOrderRule.rule, 'Higher-order rule unavailable.')}</p>
            <p>Combination contract {displayText(combinationEvidenceContract.status, 'unknown')}</p>
            <p>Exploit {displayText(allocationPolicy.exploit_fraction, 'n/a')} · Explore {displayText(allocationPolicy.explore_fraction, 'n/a')}</p>
            {assayRequired.slice(0, 4).map((item) => (
              <div key={item} className="rounded-md bg-secondary/40 px-2.5 py-1.5">{item}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_0.7fr]">
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Plate Layout</div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {plateLayout.map((group, index) => (
              <div key={`${displayText(group.well_group)}:${index}`} className="rounded-md bg-secondary/40 px-2.5 py-2 text-xs">
                <div className="font-medium">{displayText(group.well_group)}</div>
                <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {asStringArray(group.variants).join(' · ') || 'variants pending'}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  replicates {displayText(group.replicates, 'n/a')} · {displayText(group.purpose)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-border p-3">
          <div className="text-xs font-medium">Exploration Pool</div>
          <div className="mt-2 space-y-2">
            {explorationPool.length > 0 ? explorationPool.map((item, index) => (
              <div key={`${displayText(item.candidate)}:${index}`} className="rounded-md bg-secondary/40 px-2.5 py-2 text-xs">
                <div className="font-mono font-medium">{displayText(item.candidate)}</div>
                <div className="mt-1 text-muted-foreground">{displayText(item.state)}</div>
              </div>
            )) : (
              <div className="text-xs text-muted-foreground">No exploratory remote site promoted.</div>
            )}
          </div>
          <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{displayText(design.boundary)}</p>
        </div>
      </div>
    </section>
  )
}
