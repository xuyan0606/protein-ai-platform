import { useState, useCallback } from 'react'
import { FileText, Pencil, Check, X, Loader2, BookOpen } from 'lucide-react'
import { api } from '@/lib/api'

interface Props {
  content: string
  conversationId?: number
  projectId?: string | null
}

export function PublishToolbar({ content, conversationId, projectId }: Props) {
  const [showEditor, setShowEditor] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [title, setTitle] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(false)
  const [error, setError] = useState('')

  const openEditor = useCallback(() => {
    setEditContent(content)
    setTitle(`分析报告 ${new Date().toLocaleDateString('zh-CN')}`)
    setShowEditor(true)
    setError('')
    setPublished(false)
  }, [content])

  const handlePublish = useCallback(async () => {
    if (!projectId) {
      setError('请先将此对话关联到项目')
      return
    }
    setPublishing(true)
    setError('')
    try {
      const result = await api.publishReport(projectId, {
        title,
        content: editContent,
        conversation_id: conversationId,
      })
      setPublished(true)
      setShowEditor(false)
    } catch (e: any) {
      setError(e.message || '发布失败')
    } finally {
      setPublishing(false)
    }
  }, [projectId, title, editContent, conversationId])

  // Don't show for very short messages (likely not full reports)
  if (!content || content.length < 100) return null
  // Don't show if already published
  if (published) {
    return (
      <div className="flex items-center gap-2 mt-2 text-xs text-green-600">
        <Check className="w-3.5 h-3.5" />
        <span>已发布到Wiki知识库</span>
      </div>
    )
  }

  return (
    <>
      {/* Toolbar buttons */}
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={openEditor}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md
                     bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground
                     transition-colors"
          title="编辑并发布到Wiki"
        >
          <Pencil className="w-3 h-3" />
          发布到Wiki
        </button>
        {!projectId && (
          <span className="text-xs text-amber-500">需关联项目</span>
        )}
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
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="报告标题"
                className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded-md
                           focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
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
                  disabled={publishing || !title.trim() || !editContent.trim()}
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
