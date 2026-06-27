import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import { useChatStream } from '@/hooks/useChatStream'
import { ArrowUp, Paperclip, X, ChevronDown, Sparkles, Zap, Cpu, Loader2, CheckCircle, AlertCircle } from 'lucide-react'

interface AttachedFile {
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  progress: number
  error?: string
  objectName?: string
  downloadUrl?: string
  analysisData?: unknown
}

const MODEL_ICONS: Record<string, typeof Sparkles> = {
  deepseek: Zap,
  kuaPao: Sparkles,
  miniMax: Cpu,
}

const MODEL_COLORS: Record<string, string> = {
  deepseek: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
  kuaPao: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
  miniMax: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
}

export function ChatInput() {
  const { t } = useTranslation()
  const location = useLocation()
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<AttachedFile[]>([])
  const filesRef = useRef<AttachedFile[]>([])
  filesRef.current = files
  const [modelOpen, setModelOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const { addMessage, streaming, selectedModel, setSelectedModel, availableModels, fetchModels } = useChatStore()
  const { sendMessage } = useChatStream()
  const initialSent = useRef(false)

  useEffect(() => { fetchModels() }, [fetchModels])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) setModelOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Handle initial prompt from Home page navigation
  useEffect(() => {
    if (initialSent.current) return
    const state = location.state as { initialPrompt?: string; uploadFile?: File } | null
    if (state?.initialPrompt) {
      initialSent.current = true
      setInput(state.initialPrompt)
      const timer = setTimeout(() => {
        addMessage({
          role: 'user',
          content: state.initialPrompt!,
        })
        setInput('')
        sendMessage(state.initialPrompt!, useChatStore.getState().currentId ?? undefined)
        window.history.replaceState({}, '', '/chat/agent')
      }, 300)
      return () => clearTimeout(timer)
    }
    if (state?.uploadFile) {
      initialSent.current = true
      setFiles([{ file: state.uploadFile, status: 'pending', progress: 0 }])
      window.history.replaceState({}, '', '/chat/agent')
    }
  }, [location.state]) // eslint-disable-line react-hooks/exhaustive-deps

  const currentModel = availableModels.find((m) => m.id === selectedModel)
  const modelLabel = currentModel?.name || 'DeepSeek V4 Pro'
  const Icon = MODEL_ICONS[selectedModel] || Sparkles
  const colorClass = MODEL_COLORS[selectedModel] || MODEL_COLORS.deepseek

  const analyzePdb = async (objectName: string): Promise<unknown> => {
    const token = localStorage.getItem('token')
    const resp = await fetch('/api/pdb/analyze-by-name', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ object_name: objectName }),
    })
    if (!resp.ok) return null
    return resp.json()
  }

  // Helper: update both state and ref atomically
  const updateFiles = (updater: (prev: AttachedFile[]) => AttachedFile[]) => {
    setFiles((prev) => {
      const next = updater(prev)
      filesRef.current = next
      return next
    })
  }

  const uploadSingleFile = async (attached: AttachedFile, idx: number): Promise<{ objectName: string; downloadUrl: string }> => {
    const token = localStorage.getItem('token')
    const formData = new FormData()
    formData.append('file', attached.file)

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/files/upload')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          updateFiles((prev) =>
            prev.map((f, j) => (j === idx ? { ...f, progress: Math.round((e.loaded / e.total) * 100), status: 'uploading' } : f))
          )
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText)
          const objectName = data.object_name || data.id
          const downloadUrl = data.download_url
          updateFiles((prev) =>
            prev.map((f, j) =>
              j === idx ? { ...f, status: 'done', progress: 100, objectName, downloadUrl } : f
            )
          )
          resolve({ objectName, downloadUrl })
        } else {
          const err = JSON.parse(xhr.responseText || '{}')
          updateFiles((prev) =>
            prev.map((f, j) => (j === idx ? { ...f, status: 'error', error: err.detail || 'Upload failed' } : f))
          )
          reject(new Error(err.detail || 'Upload failed'))
        }
      }

      xhr.onerror = () => {
        updateFiles((prev) =>
          prev.map((f, j) => (j === idx ? { ...f, status: 'error', error: 'Network error' } : f))
        )
        reject(new Error('Network error'))
      }

      xhr.send(formData)
    })
  }

  const handleSend = async () => {
    const trimmed = input.trim()
    const currentFiles = filesRef.current
    if (!trimmed && currentFiles.length === 0) return
    if (streaming) return

    // Upload pending files and collect results
    interface FileResult { name: string; size: number; type: string; objectName?: string; downloadUrl?: string; analysisData?: unknown }
    const fileResults: FileResult[] = currentFiles.map((f) => ({
      name: f.file.name,
      size: f.file.size,
      type: f.file.type,
      objectName: f.objectName,
      downloadUrl: f.downloadUrl,
      analysisData: f.analysisData,
    }))

    const pending = currentFiles.filter((f) => f.status === 'pending')
    for (let i = 0; i < currentFiles.length; i++) {
      if (currentFiles[i].status === 'pending') {
        const result = await uploadSingleFile(currentFiles[i], i)
        fileResults[i].objectName = result.objectName
        fileResults[i].downloadUrl = result.downloadUrl
        // Auto-analyze PDB files after upload
        const ext = currentFiles[i].file.name.split('.').pop()?.toLowerCase()
        if ((ext === 'pdb' || ext === 'ent' || ext === 'cif') && result.objectName) {
          fileResults[i].analysisData = await analyzePdb(result.objectName)
        }
      }
    }

    addMessage({
      role: 'user',
      content: trimmed || t('chat.analyzingFiles'),
      files: fileResults,
    })
    setInput('')
    updateFiles(() => [])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    sendMessage(trimmed || t('chat.analyzingFiles'), useChatStore.getState().currentId ?? undefined)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles: AttachedFile[] = Array.from(e.target.files).map((f) => ({
        file: f,
        status: 'pending' as const,
        progress: 0,
      }))
      updateFiles((prev) => [...prev, ...newFiles])
    }
  }

  return (
    <div className="border-t border-border px-2 sm:px-4 py-2 sm:py-3">
      <div className="max-w-3xl mx-auto">
        {/* File previews */}
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {files.map((file, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-secondary rounded-lg text-xs">
                {file.status === 'uploading' ? (
                  <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
                ) : file.status === 'done' ? (
                  <CheckCircle className="w-3 h-3 text-green-500" />
                ) : file.status === 'error' ? (
                  <AlertCircle className="w-3 h-3 text-red-500" />
                ) : (
                  <Paperclip className="w-3 h-3 text-muted-foreground" />
                )}
                <span className="max-w-[120px] truncate">{file.file.name}</span>
                {file.status === 'uploading' && (
                  <span className="text-[10px] text-muted-foreground">{file.progress}%</span>
                )}
                <button onClick={() => updateFiles((p) => p.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground">
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Model selector bar */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[11px] text-muted-foreground shrink-0">{t('chat.model')}:</span>
          <div ref={modelRef} className="relative">
            <button
              onClick={() => setModelOpen(!modelOpen)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium transition-all
                hover:opacity-80 active:scale-[0.97] ${colorClass}`}
            >
              <Icon className="w-3 h-3" />
              <span>{modelLabel}</span>
              <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${modelOpen ? 'rotate-180' : ''}`} />
            </button>
            {modelOpen && (
              <div className="absolute bottom-full left-0 mb-1 w-60 bg-popover border border-border rounded-xl shadow-xl z-50 py-1.5 animate-in fade-in slide-in-from-bottom-2">
                <div className="px-3 py-1.5 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                  {t('chat.selectModel')}
                </div>
                {availableModels.map((m) => {
                  const MI = MODEL_ICONS[m.id] || Sparkles
                  const MC = MODEL_COLORS[m.id] || ''
                  return (
                    <button
                      key={m.id}
                      onClick={() => { setSelectedModel(m.id); setModelOpen(false) }}
                      disabled={!m.available}
                      className={`w-full text-left px-3 py-2.5 text-xs transition-colors flex items-center gap-2.5
                        ${m.id === selectedModel ? 'bg-secondary font-medium' : 'hover:bg-secondary/50'}
                        ${!m.available ? 'opacity-40 cursor-not-allowed' : ''}`}
                    >
                      <span className={`flex items-center justify-center w-6 h-6 rounded-md border shrink-0 ${MC}`}>
                        <MI className="w-3 h-3" />
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate">{m.name}</span>
                        <span className="block text-[10px] text-muted-foreground truncate">{m.description}</span>
                      </span>
                      {m.id === selectedModel && (
                        <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Input area */}
        <div className="flex items-end gap-2 bg-card border border-border rounded-2xl px-4 py-3 focus-within:border-ring transition-colors">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground shrink-0 mb-0.5"
          >
            <Paperclip className="w-5 h-5" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept=".pdb,.fasta,.cif,.sdf,.txt,.csv,.json"
          />

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              const el = e.target
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 200) + 'px'
            }}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.placeholder')}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
          />

          <button
            onClick={handleSend}
            disabled={!input.trim() && files.length === 0}
            className="p-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-30 disabled:cursor-not-allowed shrink-0 mb-0.5 transition-colors"
          >
            <ArrowUp className="w-5 h-5" />
          </button>
        </div>

        <p className="text-[11px] text-muted-foreground text-center mt-2">
          {t('chat.hint')}
        </p>
      </div>
    </div>
  )
}
