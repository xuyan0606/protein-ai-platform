import { useEffect, useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Plus, Trash2, Play, Loader2, CheckCircle2, XCircle,
  Dna, Beaker, Zap, History, BookOpen, FileText, MessageSquare,
  LayoutDashboard, Download, ExternalLink, FolderOpen, RefreshCw,
  FileDown, Filter, ChevronRight, ChevronDown, File,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SeqItem { id: string; name: string; sequence: string; notes?: string; created_at: string }
interface BatchItem { id: string; status: string; total: number; completed: number; results?: any; created_at: string }
interface ProjectData {
  id: string; name: string; description?: string; user_id: number
  sequences: SeqItem[]; batch_jobs: BatchItem[]
  outline_collection_id?: string | null; outline_root_doc_id?: string | null
  wiki_auto_publish?: boolean; file_count?: number
}
interface WikiDoc { id: string; title: string; parent_id: string | null; url_id: string | null; updated_at: string | null; emoji: string | null }
interface WikiTreeNode extends WikiDoc { children: WikiTreeNode[] }
interface ProjectFileItem {
  id: string; filename: string; object_name: string; file_type: string
  file_size: number; source: string; conversation_id: number | null
  outline_doc_id: string | null; created_at: string | null
}
interface ProjectConv { id: number; title: string; created_at: string | null; updated_at: string | null }

type TabKey = 'overview' | 'chat' | 'wiki' | 'files'

const BATCH_TOOLS = [
  { id: 'protein_benchmark', label: 'Benchmark', icon: Beaker },
  { id: 'mutation_priority_score', label: 'Mutation Score', icon: Zap },
  { id: 'predict_properties', label: 'Properties', icon: Dna },
]

const FILE_TYPE_LABELS: Record<string, string> = {
  md: 'Markdown', pdb: 'PDB结构', csv: 'CSV数据', fasta: 'FASTA', json: 'JSON',
}
const SOURCE_LABELS: Record<string, string> = {
  agent: 'Agent自动', manual: '手动上传', batch: '批量分析', upload: '文件上传',
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  const fetchProject = async () => {
    if (!id) return
    try {
      setLoading(true)
      const data = await api.getProject(id)
      setProject(data)
    } catch { navigate('/projects') } finally { setLoading(false) }
  }

  useEffect(() => { fetchProject() }, [id])

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!project) return null

  const tabs: { key: TabKey; label: string; icon: typeof LayoutDashboard }[] = [
    { key: 'overview', label: '概览', icon: LayoutDashboard },
    { key: 'chat', label: '对话分析', icon: MessageSquare },
    { key: 'wiki', label: 'Wiki知识库', icon: BookOpen },
    { key: 'files', label: `文件${project.file_count ? ` (${project.file_count})` : ''}`, icon: FileText },
  ]

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-1">
          <button onClick={() => navigate('/projects')} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{project.name}</h1>
            {project.outline_collection_id && (
              <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full font-medium">Wiki</span>
            )}
          </div>
        </div>
        {project.description && (
          <p className="text-sm text-muted-foreground ml-11 mb-6">{project.description}</p>
        )}

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-secondary rounded-lg p-0.5 w-fit mb-6">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
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

        {/* Tab Content */}
        {activeTab === 'overview' && <OverviewTab project={project} onRefresh={fetchProject} />}
        {activeTab === 'chat' && <ChatTab projectId={project.id} />}
        {activeTab === 'wiki' && <WikiTab projectId={project.id} collectionId={project.outline_collection_id || null} />}
        {activeTab === 'files' && <FilesTab projectId={project.id} />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview Tab — sequences, batch, stats
// ---------------------------------------------------------------------------

function OverviewTab({ project, onRefresh }: { project: ProjectData; onRefresh: () => void }) {
  const [showAddSeq, setShowAddSeq] = useState(false)
  const [seqName, setSeqName] = useState('')
  const [seqData, setSeqData] = useState('')
  const [seqNotes, setSeqNotes] = useState('')
  const [adding, setAdding] = useState(false)
  const [running, setRunning] = useState(false)
  const [selectedTool, setSelectedTool] = useState('protein_benchmark')

  const batchResults = useMemo(() => {
    if (!project?.batch_jobs?.length) return []
    return project.batch_jobs.flatMap((job) => {
      if (!job.results?.items) return []
      return job.results.items.map((item: any) => ({ ...item, jobId: job.id, tool: job.results?.tool }))
    })
  }, [project?.batch_jobs])

  const handleAddSeq = async () => {
    if (!project.id || !seqName.trim() || !seqData.trim()) return
    setAdding(true)
    try {
      await api.addSequence(project.id, seqName.trim(), seqData.trim(), seqNotes.trim() || undefined)
      setShowAddSeq(false); setSeqName(''); setSeqData(''); setSeqNotes('')
      onRefresh()
    } catch { /* ignore */ } finally { setAdding(false) }
  }

  const handleRemoveSeq = async (seqId: string) => {
    try { await api.removeSequence(project.id, seqId); onRefresh() } catch { /* ignore */ }
  }

  const handleBatchRun = async () => {
    setRunning(true)
    try { await api.batchRun(project.id, selectedTool); onRefresh() } catch { /* ignore */ } finally { setRunning(false) }
  }

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: '序列', value: project.sequences.length, icon: Dna },
          { label: '批量任务', value: project.batch_jobs.length, icon: History },
          { label: '分析结果', value: batchResults.length, icon: Beaker },
          { label: '知识库文件', value: project.file_count || 0, icon: FileText },
        ].map((s) => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <s.icon className="w-4 h-4 text-primary" />
            </div>
            <div>
              <p className="text-lg font-bold">{s.value}</p>
              <p className="text-[10px] text-muted-foreground">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Sequences */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm flex items-center gap-2"><Dna className="w-4 h-4" /> 蛋白序列</h3>
          <button onClick={() => setShowAddSeq(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90">
            <Plus className="w-3.5 h-3.5" /> 添加序列
          </button>
        </div>

        {showAddSeq && (
          <div className="bg-card border border-border rounded-xl p-4 mb-3 space-y-3">
            <input autoFocus value={seqName} onChange={(e) => setSeqName(e.target.value)} placeholder="序列名称 (如 'BLA-WT')" className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm focus:outline-none focus:border-ring" />
            <textarea value={seqData} onChange={(e) => setSeqData(e.target.value.toUpperCase())} placeholder="氨基酸序列 (单字母编码)" rows={3} className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm font-mono focus:outline-none focus:border-ring resize-none" />
            <input value={seqNotes} onChange={(e) => setSeqNotes(e.target.value)} placeholder="备注 (可选)" className="w-full px-3 py-2 rounded-lg border border-border bg-transparent text-sm focus:outline-none focus:border-ring" />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowAddSeq(false)} className="px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary rounded-lg">取消</button>
              <button onClick={handleAddSeq} disabled={!seqName.trim() || !seqData.trim() || adding} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-xs font-medium rounded-lg disabled:opacity-40">
                {adding && <Loader2 className="w-3 h-3 animate-spin" />} 添加
              </button>
            </div>
          </div>
        )}

        {project.sequences.length === 0 ? (
          <div className="text-center py-12 bg-card border border-border rounded-xl">
            <Dna className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground text-sm">暂无序列</p>
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
                <button onClick={() => handleRemoveSeq(seq.id)} className="p-1.5 rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Batch Run */}
      {project.sequences.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2"><Play className="w-4 h-4" /> 批量分析</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="text-[10px] text-muted-foreground block mb-1">工具</label>
              <div className="flex gap-1">
                {BATCH_TOOLS.map((tool) => {
                  const Icon = tool.icon
                  return (
                    <button key={tool.id} onClick={() => setSelectedTool(tool.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        selectedTool === tool.id ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
                      }`}>
                      <Icon className="w-3 h-3" /> {tool.label}
                    </button>
                  )
                })}
              </div>
            </div>
            <button onClick={handleBatchRun} disabled={running}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-emerald-500 text-white text-xs font-medium hover:bg-emerald-600 disabled:opacity-40">
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              {running ? '运行中...' : `分析 ${project.sequences.length} 个序列`}
            </button>
          </div>
        </div>
      )}

      {/* Recent batch results */}
      {batchResults.length > 0 && (
        <div>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2"><History className="w-4 h-4" /> 最近结果</h3>
          <div className="space-y-2">
            {batchResults.slice(0, 5).map((r: any, i: number) => (
              <div key={i} className="flex items-start gap-3 bg-card border border-border rounded-xl p-4">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${r.status === 'completed' ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                  {r.status === 'completed' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-medium text-sm">{r.sequence_name}</span>
                    <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 bg-secondary rounded">{r.tool}</span>
                  </div>
                  {r.status === 'completed' && r.result && (
                    <details className="mt-1">
                      <summary className="text-xs text-primary cursor-pointer hover:underline">查看结果</summary>
                      <pre className="mt-2 text-[10px] text-muted-foreground bg-secondary/30 rounded-lg p-3 overflow-x-auto max-h-48">{JSON.stringify(r.result, null, 2)}</pre>
                    </details>
                  )}
                  {r.error && <p className="text-xs text-red-400 mt-1">{r.error}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat Tab — project conversations + link to new chat
// ---------------------------------------------------------------------------

function ChatTab({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<ProjectConv[]>([])
  const [loading, setLoading] = useState(true)

  const fetchConvs = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getProjectConversations(projectId)
      setConversations(data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [projectId])

  useEffect(() => { fetchConvs() }, [fetchConvs])

  return (
    <div className="space-y-4">
      {/* CTA to start new chat in project context */}
      <a
        href={`/chat/agent?project_id=${projectId}`}
        className="flex items-center gap-4 bg-card border border-border rounded-xl p-5 hover:border-primary/50 transition-colors group"
      >
        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
          <MessageSquare className="w-6 h-6 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-sm">开始新对话</h3>
          <p className="text-xs text-muted-foreground mt-0.5">在此项目上下文中与 AI Agent 对话分析，报告将自动发布到 Wiki</p>
        </div>
        <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
      </a>

      {/* Conversation list */}
      <div>
        <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
          <History className="w-4 h-4" /> 项目对话历史 ({conversations.length})
        </h3>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-12 bg-card border border-border rounded-xl">
            <MessageSquare className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground text-sm">暂无对话记录</p>
            <p className="text-xs text-muted-foreground/70 mt-1">对话分析完成后会自动关联到此项目</p>
          </div>
        ) : (
          <div className="space-y-2">
            {conversations.map((conv) => (
              <a
                key={conv.id}
                href={`/chat/agent?project_id=${projectId}&conversation_id=${conv.id}`}
                className="flex items-center gap-3 bg-card border border-border rounded-xl p-4 hover:border-primary/50 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                  <MessageSquare className="w-4 h-4 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium truncate">{conv.title}</h4>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {conv.updated_at ? new Date(conv.updated_at).toLocaleDateString('zh-CN') : '—'}
                  </p>
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-muted-opacity-0 group-hover:opacity-100 transition-opacity" />
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Wiki Tab — tree navigation + Markdown rendering
// ---------------------------------------------------------------------------

function WikiTab({ projectId, collectionId }: { projectId: string; collectionId: string | null }) {
  const [docs, setDocs] = useState<WikiDoc[]>([])
  const [rootDocId, setRootDocId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [pageContent, setPageContent] = useState('')
  const [pageTitle, setPageTitle] = useState('')
  const [pageLoading, setPageLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchTree = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getWikiTree(projectId)
      setDocs(data.documents || [])
      setRootDocId(data.root_doc_id || null)
      setError('')
    } catch (e: any) {
      setError(e.message || 'Failed to load wiki tree')
    } finally { setLoading(false) }
  }, [projectId])

  useEffect(() => { fetchTree() }, [fetchTree])

  // Auto-select root doc
  useEffect(() => {
    if (rootDocId && !selectedDocId) {
      setSelectedDocId(rootDocId)
    }
  }, [rootDocId, selectedDocId])

  // Load page content when selection changes
  useEffect(() => {
    if (!selectedDocId) return
    let cancelled = false
    setPageLoading(true)
    api.getWikiPage(projectId, selectedDocId)
      .then((data) => {
        if (!cancelled) {
          setPageContent(data.text || '')
          setPageTitle(data.title || '')
        }
      })
      .catch((e) => {
        if (!cancelled) setPageContent(`加载失败: ${e.message}`)
      })
      .finally(() => { if (!cancelled) setPageLoading(false) })
    return () => { cancelled = true }
  }, [projectId, selectedDocId])

  // Build tree from flat list
  const tree = useMemo(() => buildTree(docs, rootDocId), [docs, rootDocId])

  if (!collectionId) {
    return (
      <div className="text-center py-16 bg-card border border-border rounded-xl">
        <BookOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
        <p className="text-muted-foreground">此项目尚未启用 Wiki</p>
        <p className="text-sm text-muted-foreground/70 mt-1">创建项目时会自动初始化 Outline Wiki Collection</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex gap-4 min-h-[500px]">
      {/* Left: Tree */}
      <div className="w-64 shrink-0 bg-card border border-border rounded-xl p-3 overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">文档目录</h3>
          <button onClick={fetchTree} className="p-1 rounded hover:bg-secondary text-muted-foreground" title="刷新">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
        {tree.length === 0 ? (
          <p className="text-xs text-muted-foreground">暂无文档</p>
        ) : (
          <div className="space-y-0.5">
            {tree.map((node) => (
              <TreeNodeItem key={node.id} node={node} selectedId={selectedDocId} onSelect={setSelectedDocId} depth={0} />
            ))}
          </div>
        )}
      </div>

      {/* Right: Content */}
      <div className="flex-1 bg-card border border-border rounded-xl overflow-hidden">
        {selectedDocId ? (
          <>
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="font-semibold text-sm truncate">{pageTitle || '加载中...'}</h2>
              <div className="flex items-center gap-2">
                {pageLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
              </div>
            </div>
            <div className="p-5 overflow-y-auto max-h-[600px] prose prose-sm prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex, rehypeHighlight]}
              >
                {pageContent || '_（空白页面）_'}
              </ReactMarkdown>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <div className="text-center">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>选择一个文档查看内容</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Tree node component
function TreeNodeItem({ node, selectedId, onSelect, depth }: {
  node: WikiTreeNode; selectedId: string | null; onSelect: (id: string) => void; depth: number
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = node.children.length > 0
  const isSelected = node.id === selectedId

  return (
    <div>
      <button
        onClick={() => onSelect(node.id)}
        className={`w-full flex items-center gap-1 px-2 py-1.5 rounded-md text-xs transition-colors text-left ${
          isSelected ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {hasChildren ? (
          <span onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }} className="p-0.5 -ml-0.5 cursor-pointer">
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
        ) : (
          <span className="w-4" />
        )}
        <File className="w-3.5 h-3.5 shrink-0" />
        <span className="truncate">{node.emoji ? `${node.emoji} ` : ''}{node.title}</span>
      </button>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeItem key={child.id} node={child} selectedId={selectedId} onSelect={onSelect} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

// Build tree from flat document list
function buildTree(docs: WikiDoc[], rootDocId: string | null): WikiTreeNode[] {
  const nodeMap = new Map<string, WikiTreeNode>()
  for (const doc of docs) {
    nodeMap.set(doc.id, { ...doc, children: [] })
  }
  const roots: WikiTreeNode[] = []
  for (const node of nodeMap.values()) {
    if (node.parent_id && nodeMap.has(node.parent_id)) {
      nodeMap.get(node.parent_id)!.children.push(node)
    } else if (!rootDocId || node.id === rootDocId || !node.parent_id) {
      roots.push(node)
    }
  }
  // Put root doc first if it exists
  if (rootDocId) {
    const rootIdx = roots.findIndex((r) => r.id === rootDocId)
    if (rootIdx > 0) {
      const [root] = roots.splice(rootIdx, 1)
      roots.unshift(root)
    }
  }
  return roots
}

// ---------------------------------------------------------------------------
// Files Tab — file browser with filters
// ---------------------------------------------------------------------------

function FilesTab({ projectId }: { projectId: string }) {
  const [files, setFiles] = useState<ProjectFileItem[]>([])
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [sourceFilter, setSourceFilter] = useState<string>('')

  const fetchFiles = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getProjectFiles(projectId, typeFilter || undefined)
      setFiles(data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [projectId, typeFilter])

  useEffect(() => { fetchFiles() }, [fetchFiles])

  const filteredFiles = useMemo(() => {
    if (!sourceFilter) return files
    return files.filter((f) => f.source === sourceFilter)
  }, [files, sourceFilter])

  const handleDownload = async (file: ProjectFileItem) => {
    try {
      const resp = await api.downloadProjectFile(projectId, file.id)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  const handleDelete = async (file: ProjectFileItem) => {
    if (!confirm(`确定删除 "${file.filename}"？`)) return
    try {
      await api.deleteProjectFile(projectId, file.id)
      setFiles((prev) => prev.filter((f) => f.id !== file.id))
    } catch { /* ignore */ }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">类型:</span>
          {['', 'md', 'pdb', 'csv', 'json'].map((t) => (
            <button key={t} onClick={() => setTypeFilter(t)}
              className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                typeFilter === t ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}>
              {t ? (FILE_TYPE_LABELS[t] || t) : '全部'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">来源:</span>
          {['', 'agent', 'manual', 'batch', 'upload'].map((s) => (
            <button key={s} onClick={() => setSourceFilter(s)}
              className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                sourceFilter === s ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}>
              {s ? (SOURCE_LABELS[s] || s) : '全部'}
            </button>
          ))}
        </div>
        <button onClick={fetchFiles} className="ml-auto p-1.5 rounded-md hover:bg-secondary text-muted-foreground" title="刷新">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* File list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : filteredFiles.length === 0 ? (
        <div className="text-center py-16 bg-card border border-border rounded-xl">
          <FolderOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
          <p className="text-muted-foreground text-sm">暂无文件</p>
          <p className="text-xs text-muted-foreground/70 mt-1">Agent 分析完成后报告会自动保存到这里</p>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left font-medium px-4 py-2.5">文件名</th>
                <th className="text-left font-medium px-3 py-2.5 w-20">类型</th>
                <th className="text-left font-medium px-3 py-2.5 w-20">大小</th>
                <th className="text-left font-medium px-3 py-2.5 w-20">来源</th>
                <th className="text-left font-medium px-3 py-2.5 w-28">时间</th>
                <th className="text-right font-medium px-4 py-2.5 w-24">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredFiles.map((file) => (
                <tr key={file.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileIcon type={file.file_type} />
                      <span className="font-medium truncate max-w-[200px]">{file.filename}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="px-1.5 py-0.5 bg-secondary rounded text-[10px]">{FILE_TYPE_LABELS[file.file_type] || file.file_type}</span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{formatSize(file.file_size)}</td>
                  <td className="px-3 py-2.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                      file.source === 'agent' ? 'bg-blue-500/10 text-blue-400' : 'bg-secondary text-muted-foreground'
                    }`}>
                      {SOURCE_LABELS[file.source] || file.source}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {file.created_at ? new Date(file.created_at).toLocaleDateString('zh-CN') : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleDownload(file)} className="p-1.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary" title="下载">
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(file)} className="p-1.5 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-400" title="删除">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-[10px] text-muted-foreground border-t border-border">
            共 {filteredFiles.length} 个文件
          </div>
        </div>
      )}
    </div>
  )
}

// File type icon
function FileIcon({ type }: { type: string }) {
  const colors: Record<string, string> = {
    md: 'text-blue-400 bg-blue-500/10',
    pdb: 'text-emerald-400 bg-emerald-500/10',
    csv: 'text-amber-400 bg-amber-500/10',
    fasta: 'text-purple-400 bg-purple-500/10',
    json: 'text-orange-400 bg-orange-500/10',
  }
  const color = colors[type] || 'text-muted-foreground bg-secondary'
  return (
    <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${color}`}>
      <File className="w-3.5 h-3.5" />
    </div>
  )
}
