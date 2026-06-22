import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'
import { useChatStream } from '@/hooks/useChatStream'
import { ArrowUp, Paperclip, X, ChevronDown, Sparkles, Zap, Cpu } from 'lucide-react'

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
  const [files, setFiles] = useState<File[]>([])
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
      setFiles([state.uploadFile])
      window.history.replaceState({}, '', '/chat/agent')
    }
  }, [location.state]) // eslint-disable-line react-hooks/exhaustive-deps

  const currentModel = availableModels.find((m) => m.id === selectedModel)
  const modelLabel = currentModel?.name || 'DeepSeek V4 Pro'
  const Icon = MODEL_ICONS[selectedModel] || Sparkles
  const colorClass = MODEL_COLORS[selectedModel] || MODEL_COLORS.deepseek

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed && files.length === 0) return
    if (streaming) return

    addMessage({
      role: 'user',
      content: trimmed || t('chat.analyzingFiles'),
      files: files.map((f) => ({ name: f.name, size: f.size, type: f.type })),
    })
    setInput('')
    setFiles([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    sendMessage(trimmed || t('chat.analyzingFiles'), useChatStore.getState().currentId ?? undefined)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
  }

  return (
    <div className="border-t border-border px-2 sm:px-4 py-2 sm:py-3">
      <div className="max-w-3xl mx-auto">
        {/* File previews */}
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {files.map((file, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-secondary rounded-lg text-xs">
                <Paperclip className="w-3 h-3 text-muted-foreground" />
                <span className="max-w-[120px] truncate">{file.name}</span>
                <button onClick={() => setFiles((p) => p.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground">
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
