import { useState, useCallback, useEffect, useMemo } from 'react'
import { FileText, Pencil, Check, X, Loader2, BookOpen, ChevronRight, FolderTree } from 'lucide-react'
import { api } from '@/lib/api'

interface Props {
  content: string
  conversationId?: number
}

interface WikiCollectionOption {
  id: string
  name: string
  description?: string | null
  document_count?: number | null
}

interface WikiDocument {
  id: string
  title: string
  parent_id: string | null
  url_id: string | null
  updated_at: string | null
  emoji: string | null
}

interface WikiTreeResponse {
  collection_id: string | null
  root_doc_id: string | null
  documents: WikiDocument[]
}

interface WikiTreeNode extends WikiDocument {
  children: WikiTreeNode[]
}

const COLLECTION_ROOT = '__collection_root__'

function buildWikiTree(documents: WikiDocument[]): WikiTreeNode[] {
  const nodeMap = new Map<string, WikiTreeNode>()
  for (const doc of documents) {
    nodeMap.set(doc.id, { ...doc, children: [] })
  }

  const topLevel: WikiTreeNode[] = []
  for (const doc of documents) {
    const node = nodeMap.get(doc.id)
    if (!node) continue

    if (doc.parent_id && nodeMap.has(doc.parent_id)) {
      nodeMap.get(doc.parent_id)!.children.push(node)
      continue
    }
    topLevel.push(node)
  }

  const sortNodes = (nodes: WikiTreeNode[]) => {
    nodes.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))
    nodes.forEach((node) => sortNodes(node.children))
  }
  sortNodes(topLevel)
  return topLevel
}

export function PublishToolbar({ content, conversationId }: Props) {
  const [showEditor, setShowEditor] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [title, setTitle] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(false)
  const [error, setError] = useState('')
  const [collections, setCollections] = useState<WikiCollectionOption[]>([])
  const [collectionsLoading, setCollectionsLoading] = useState(false)
  const [selectedCollectionId, setSelectedCollectionId] = useState('')
  const [wikiTreeData, setWikiTreeData] = useState<WikiTreeResponse | null>(null)
  const [wikiTreeLoading, setWikiTreeLoading] = useState(false)
  const [selectedTargetId, setSelectedTargetId] = useState<string>('')

  const openEditor = useCallback(() => {
    setEditContent(content)
    setTitle(`分析报告 ${new Date().toLocaleDateString('zh-CN')}`)
    setShowEditor(true)
    setError('')
    setPublished(false)
    setWikiTreeData(null)
    setSelectedTargetId('')
    setSelectedCollectionId('')
    setCollectionsLoading(collections.length === 0)
  }, [collections.length, content])

  useEffect(() => {
    if (!showEditor) return
    if (collections.length > 0) return

    let active = true
    void api.getWikiCollections()
      .then((data) => {
        if (!active) return
        setCollections(data)
        if (data.length === 1) {
          setSelectedCollectionId(data[0].id)
          setWikiTreeLoading(true)
        }
      })
      .catch((e: unknown) => {
        if (!active) return
        setError(e instanceof Error ? e.message : '加载 Wiki collection 失败')
      })
      .finally(() => {
        if (active) setCollectionsLoading(false)
      })

    return () => {
      active = false
    }
  }, [showEditor, collections.length])

  useEffect(() => {
    if (!showEditor || !selectedCollectionId) {
      return
    }

    let active = true

    void api.getCollectionTree(selectedCollectionId)
      .then((data) => {
        if (!active) return
        setWikiTreeData(data)
        setSelectedTargetId(COLLECTION_ROOT)
      })
      .catch((e: unknown) => {
        if (!active) return
        setWikiTreeData(null)
        setSelectedTargetId(COLLECTION_ROOT)
        setError(e instanceof Error ? e.message : '加载知识库目录树失败')
      })
      .finally(() => {
        if (active) setWikiTreeLoading(false)
      })

    return () => {
      active = false
    }
  }, [showEditor, selectedCollectionId])

  const treeNodes = useMemo(
    () => buildWikiTree(wikiTreeData?.documents || []),
    [wikiTreeData]
  )

  function renderTreeNode(node: WikiTreeNode, depth = 0) {
    const selected = selectedTargetId === node.id
    return (
      <div key={node.id}>
        <button
          type="button"
          onClick={() => setSelectedTargetId(node.id)}
          className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
            selected ? 'bg-primary/10 text-foreground ring-1 ring-primary/30' : 'hover:bg-muted'
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          <ChevronRight className={`h-3.5 w-3.5 shrink-0 text-muted-foreground ${node.children.length ? '' : 'opacity-30'}`} />
          <span className="truncate">
            {node.emoji ? `${node.emoji} ` : ''}
            {node.title}
          </span>
        </button>
        {node.children.length > 0 && (
          <div>
            {node.children.map((child) => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  const handlePublish = useCallback(async () => {
    if (!selectedCollectionId) {
      setError('请选择 Wiki collection')
      return
    }
    if (!selectedTargetId) {
      setError('请选择知识库目录节点')
      return
    }
    setPublishing(true)
    setError('')
    try {
      await api.publishToWikiCollection({
        title,
        content: editContent,
        conversation_id: conversationId,
        collection_id: selectedCollectionId,
        parent_document_id: selectedTargetId === COLLECTION_ROOT ? undefined : selectedTargetId,
      })
      setPublished(true)
      setShowEditor(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '发布失败')
    } finally {
      setPublishing(false)
    }
  }, [selectedCollectionId, selectedTargetId, title, editContent, conversationId])

  // Don't show for very short messages (likely not full reports)
  if (!content || content.length < 100) return null
  // Don't show if already published
  if (published) {
    return (
      <div className="mx-auto mt-4 flex max-w-[860px] items-center gap-2 text-xs text-green-600">
        <Check className="w-3.5 h-3.5" />
        <span>已发布到Wiki知识库</span>
      </div>
    )
  }

  return (
    <>
      {/* Toolbar buttons */}
      <div className="mx-auto mt-5 flex max-w-[860px] items-center gap-3">
        <button
          onClick={openEditor}
          className="inline-flex items-center gap-1.5 rounded-full border border-border/80 px-3 py-1.5 text-xs
                     bg-background/80 text-muted-foreground hover:bg-muted/60 hover:text-foreground
                     transition-colors"
          title="编辑并发布到Wiki"
        >
          <Pencil className="w-3 h-3" />
          发布到Wiki
        </button>
      </div>

      {/* Editor Modal */}
      {showEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
             onClick={() => setShowEditor(false)}>
          <div className="bg-card border border-border rounded-xl shadow-2xl w-[90vw] max-w-4xl max-h-[85vh] flex flex-col"
               onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-primary" />
                <h3 className="font-medium text-sm">编辑并发布到Wiki知识库</h3>
              </div>
              <button onClick={() => setShowEditor(false)}
                      className="p-1 rounded hover:bg-muted">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Title input */}
            <div className="px-5 py-2 border-b border-border">
              <div className="mb-2 flex items-center gap-2">
                <BookOpen className="w-3.5 h-3.5 text-primary" />
                <span className="text-xs font-medium text-muted-foreground">Wiki Collection</span>
              </div>
              <select
                value={selectedCollectionId}
                onChange={(e) => {
                  const nextCollectionId = e.target.value
                  setSelectedCollectionId(nextCollectionId)
                  setWikiTreeData(null)
                  setSelectedTargetId(nextCollectionId ? COLLECTION_ROOT : '')
                  setWikiTreeLoading(Boolean(nextCollectionId))
                  setError('')
                }}
                className="mb-3 w-full px-3 py-2 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/30"
                disabled={collectionsLoading || publishing}
              >
                <option value="">
                  {collectionsLoading ? '正在加载 Wiki collections...' : '请选择已存在的 Wiki collection'}
                </option>
                {collections.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                    {typeof collection.document_count === 'number' ? ` (${collection.document_count})` : ''}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="报告标题"
                className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded-md
                           focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            <div className="px-5 py-3 border-b border-border">
              <div className="mb-2 flex items-center gap-2">
                <FolderTree className="w-3.5 h-3.5 text-primary" />
                <span className="text-xs font-medium text-muted-foreground">选择知识库目录</span>
              </div>
              <div className="max-h-52 overflow-y-auto rounded-lg border border-border bg-background p-2">
                {!selectedCollectionId ? (
                  <div className="px-2 py-3 text-sm text-muted-foreground">请先选择 Wiki collection</div>
                ) : wikiTreeLoading ? (
                  <div className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在加载目录树...
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => setSelectedTargetId(COLLECTION_ROOT)}
                      className={`mb-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                        selectedTargetId === COLLECTION_ROOT
                          ? 'bg-primary/10 text-foreground ring-1 ring-primary/30'
                          : 'hover:bg-muted'
                      }`}
                    >
                      <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>知识库根目录</span>
                    </button>
                    {treeNodes.length > 0 ? (
                      treeNodes.map((node) => renderTreeNode(node))
                    ) : (
                      <div className="px-2 py-3 text-sm text-muted-foreground">
                        当前知识库还没有目录文档，将发布到根目录。
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                选中节点后，新报告会作为该节点下的新文档发布。
              </div>
            </div>

            {/* Markdown Editor */}
            <div className="flex-1 min-h-0 p-5 overflow-hidden">
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                className="w-full h-full min-h-[400px] p-4 text-sm font-mono leading-relaxed
                           bg-background border border-border rounded-lg resize-none
                           focus:outline-none focus:ring-2 focus:ring-primary/30"
                spellCheck={false}
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-border">
              <div className="text-xs text-muted-foreground">
                {editContent.length} 字符 · Markdown 格式
                {error && <span className="text-red-500 ml-2">{error}</span>}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowEditor(false)}
                  className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handlePublish}
                  disabled={publishing || !title.trim() || !editContent.trim() || !selectedCollectionId || !selectedTargetId}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-md
                             bg-primary text-primary-foreground hover:bg-primary/90
                             disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {publishing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileText className="w-3.5 h-3.5" />
                  )}
                  发布到Wiki
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
