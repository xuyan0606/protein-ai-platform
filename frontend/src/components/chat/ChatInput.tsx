import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useShallow } from 'zustand/react/shallow'
import { useChatStore, type AgentState, type StepResult } from '@/stores/chat'
import { useChatStream, type AgentControl, type AnalysisDepth } from '@/hooks/useChatStream'
import { api, authFetch, uploadFormWithProgress } from '@/lib/api'
import { ArrowUp, Paperclip, X, ChevronDown, Sparkles, Loader2, CheckCircle, AlertCircle, Gauge, Microscope, Play, SlidersHorizontal, Square } from 'lucide-react'

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
  gpt55: Sparkles,
  gpt56: Sparkles,
  'gpt56-sol': Sparkles,
  'gpt6-sol': Sparkles,
}

const MODEL_COLORS: Record<string, string> = {
  gpt55: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
  gpt56: 'text-orange-500 bg-orange-500/10 border-orange-500/20',
  'gpt56-sol': 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20',
  'gpt6-sol': 'text-emerald-600 bg-emerald-500/10 border-emerald-500/20',
}

const STRUCTURE_FILE_EXTENSIONS = new Set(['pdb', 'ent', 'cif'])
const PDB_TEXT_PREFIXES = ['HEADER', 'ATOM', 'MODEL', 'CRYST1', 'TITLE', 'REMARK', 'SEQRES', 'data_']
const ANALYSIS_DEPTH_OPTIONS: Array<{ value: AnalysisDepth; label: string; title: string }> = [
  { value: 'fast', label: '快', title: 'Fast analysis' },
  { value: 'standard', label: '标准', title: 'Standard analysis' },
  { value: 'deep', label: '深度', title: 'Deep analysis with slow tools allowed' },
]

async function canAutoAnalyzeStructureFile(file: File): Promise<boolean> {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !STRUCTURE_FILE_EXTENSIONS.has(ext)) return false

  try {
    const preview = await file.slice(0, 4096).text()
    const trimmed = preview.trimStart()
    return PDB_TEXT_PREFIXES.some((prefix) => trimmed.startsWith(prefix))
  } catch {
    return false
  }
}

function normalizeStepResults(raw: Array<Record<string, unknown>> | undefined): StepResult[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => ({
    step: Number(item.step || 0),
    tool: String(item.tool || ''),
    status: String(item.status || ''),
    result_preview: typeof item.result_preview === 'string' ? item.result_preview : undefined,
    error: typeof item.error === 'string' ? item.error : undefined,
    duration: typeof item.duration === 'number' ? item.duration : undefined,
  }))
}

export function ChatInput() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<AttachedFile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const filesRef = useRef<AttachedFile[]>([])
  const submitLockRef = useRef(false)
  const [modelOpen, setModelOpen] = useState(false)
  const [analysisDepth, setAnalysisDepth] = useState<AnalysisDepth>('standard')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const { addMessage, streaming, selectedModel, setSelectedModel, availableModels, fetchModels, agentState, messages, clearAgentState } = useChatStore(useShallow((s) => ({
    addMessage: s.addMessage,
    streaming: s.streaming,
    selectedModel: s.selectedModel,
    setSelectedModel: s.setSelectedModel,
    availableModels: s.availableModels,
    fetchModels: s.fetchModels,
    agentState: s.agentState,
    messages: s.messages,
    clearAgentState: s.clearAgentState,
  })))
  const { sendMessage, stopStreaming } = useChatStream()
  const initialSent = useRef(false)

  useEffect(() => {
    filesRef.current = files
  }, [files])

  useEffect(() => {
    if (availableModels.length === 0) {
      void fetchModels()
    }
  }, [availableModels.length, fetchModels])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (modelRef.current && !modelRef.current.contains(e.target as Node)) setModelOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Handle initial prompt from Home page / PDB page navigation
  useEffect(() => {
    if (initialSent.current) return
    const state = location.state as { initialPrompt?: string; uploadFile?: File } | null
    if (!state?.initialPrompt && !state?.uploadFile) return

    initialSent.current = true
    const initialPrompt = state.initialPrompt
    const uploadFile = state.uploadFile
    let cancelled = false

    const processInitialState = async () => {
      // Case: file + prompt (from PDB page "Deep Analysis in Chat")
      if (uploadFile) {
        const attachedFile: AttachedFile = { file: uploadFile, status: 'pending', progress: 0 }
        setFiles([attachedFile])

        try {
          // Upload the file first
          const { objectName, downloadUrl } = await uploadSingleFile(attachedFile, 0)
          if (cancelled) return

          let analysisData: unknown = null
          if (objectName && await canAutoAnalyzeStructureFile(uploadFile)) {
            analysisData = await analyzePdb(objectName)
            if (cancelled) return
          }

          const fileResult = {
            name: uploadFile.name,
            size: uploadFile.size,
            type: uploadFile.type,
            objectName,
            downloadUrl,
            analysisData,
          }

          const promptText = initialPrompt || t('chat.analyzingFiles')

          addMessage({
            role: 'user',
            content: promptText,
            files: [fileResult],
          })
          setInput('')
          updateFiles(() => [])
          sendMessage(promptText, useChatStore.getState().currentId ?? undefined, undefined, [fileResult], analysisDepth)
          navigate(location.pathname, { replace: true, state: null })
        } catch {
          if (cancelled) return
          // Upload failed — fall back to text-only
          const promptText = initialPrompt || t('chat.analyzingFiles')
          addMessage({
            role: 'user',
            content: promptText,
          })
          setInput('')
          updateFiles(() => [])
          sendMessage(promptText, useChatStore.getState().currentId ?? undefined, undefined, undefined, analysisDepth)
          navigate(location.pathname, { replace: true, state: null })
        }
        return
      }

      // Case: text prompt only (from Home page)
      if (initialPrompt) {
        if (cancelled) return
        addMessage({
          role: 'user',
          content: initialPrompt,
        })
        setInput('')
        sendMessage(initialPrompt, useChatStore.getState().currentId ?? undefined, undefined, undefined, analysisDepth)
        navigate(location.pathname, { replace: true, state: null })
      }
    }

    void processInitialState()

    return () => {
      cancelled = true
    }
  }, [location.pathname, location.state, analysisDepth]) // eslint-disable-line react-hooks/exhaustive-deps

  async function analyzePdb(objectName: string): Promise<unknown> {
    try {
      const selectedModel = useChatStore.getState().selectedModel
      const resp = await authFetch('/api/pdb/analyze-by-name', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ object_name: objectName, model: selectedModel }),
      })
      if (!resp.ok) return null
      return resp.json()
    } catch {
      return null
    }
  }

  // Helper: update both state and ref atomically
  function updateFiles(updater: (prev: AttachedFile[]) => AttachedFile[]) {
    setFiles((prev) => {
      const next = updater(prev)
      filesRef.current = next
      return next
    })
  }

  async function uploadSingleFile(attached: AttachedFile, idx: number): Promise<{ objectName: string; downloadUrl: string }> {
    const formData = new FormData()
    formData.append('file', attached.file)
    try {
      const data = await uploadFormWithProgress<{
        id: string
        object_name?: string
        download_url?: string
      }>('/files/upload', formData, {
        onProgress: (progress) => {
          updateFiles((prev) =>
            prev.map((f, j) => (j === idx ? { ...f, progress, status: 'uploading' } : f))
          )
        },
      })
      const objectName = data.object_name || data.id
      const downloadUrl = data.download_url || ''
      updateFiles((prev) =>
        prev.map((f, j) =>
          j === idx ? { ...f, status: 'done', progress: 100, objectName, downloadUrl } : f
        )
      )
      return { objectName, downloadUrl }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed'
      updateFiles((prev) =>
        prev.map((f, j) => (j === idx ? { ...f, status: 'error', error: message } : f))
      )
      throw error
    }
  }

  const currentModel = availableModels.find((m) => m.id === selectedModel)
  const modelLabel = currentModel?.name || 'GPT-6-sol'
  const Icon = MODEL_ICONS[selectedModel] || Sparkles
  const colorClass = MODEL_COLORS[selectedModel] || MODEL_COLORS.gpt55
  const busy = streaming || submitting
  const hasLocalPlanCheckpoint = agentState?.waiting_for === 'plan_confirmation'
    && Array.isArray(agentState.plan)
    && agentState.plan.length > 0
    && Boolean(agentState.strategy_signature)
  const waitingForPlanConfirmation = hasLocalPlanCheckpoint && !busy

  useEffect(() => {
    if (!hasLocalPlanCheckpoint) return
    if (streaming) return
    const conversationId = useChatStore.getState().currentId
    if (!conversationId) {
      clearAgentState()
      return
    }
    let cancelled = false
    const verifyActiveCheckpoint = async () => {
      try {
        const active = await api.getActiveStrategyCheckpoint(conversationId)
        if (cancelled || useChatStore.getState().currentId !== conversationId) return
        const activePlan = active.agent_state?.plan
        if (
          active.agent_state?.waiting_for !== 'plan_confirmation'
          || !Array.isArray(activePlan)
          || activePlan.length === 0
        ) {
          clearAgentState()
        }
      } catch {
        if (!cancelled && useChatStore.getState().currentId === conversationId) {
          clearAgentState()
        }
      }
    }
    const timer = window.setTimeout(() => {
      void verifyActiveCheckpoint()
    }, 750)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [hasLocalPlanCheckpoint, agentState?.strategy_signature, streaming, clearAgentState])

  function getPlannedTaskContext() {
    let baseIndex = -1
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i]
      if (
        message.role === 'user' &&
        !message.content.startsWith('确认执行') &&
        !message.content.startsWith('修改分析策略')
      ) {
        baseIndex = i
        break
      }
    }
    if (baseIndex < 0) return null

    const base = messages[baseIndex]
    const modifications = messages
      .slice(baseIndex + 1)
      .filter((message) => message.role === 'user' && message.content.startsWith('修改分析策略'))
      .map((message) => message.content.replace(/^修改分析策略[:：]?/, '').trim())
      .filter(Boolean)
    const content = modifications.length > 0
      ? `${base.content}\n\n[用户修改策略要求]\n${modifications.join('\n')}`
      : base.content

    return { base, content }
  }

  async function sendPlannedControl(control: AgentControl, note?: string) {
    if (submitLockRef.current || useChatStore.getState().streaming) return
    const plannedTask = getPlannedTaskContext()
    if (!plannedTask) return
    const fileResults = plannedTask.base.files?.map((f) => ({
      name: f.name,
      objectName: f.objectName,
      downloadUrl: f.downloadUrl,
      analysisData: f.analysisData,
    }))
    const visibleContent = control === 'execute_confirmed'
      ? '确认执行上述分析策略'
      : `修改分析策略：${note || ''}`.trim()
    const taskContent = control === 'execute_confirmed'
      ? visibleContent
      : `${plannedTask.content}\n\n[用户修改策略要求]\n${note || ''}`
    let checkpoint: {
      confirmed_plan: AgentState['plan']
      strategy_signature?: string | null
      task_fingerprint?: string | null
    } | undefined

    if (control === 'execute_confirmed') {
      const currentConversationId = useChatStore.getState().currentId
      if (currentConversationId) {
        try {
          const active = await api.getActiveStrategyCheckpoint(currentConversationId)
          const activePlan = active.agent_state?.plan
          if (active.agent_state?.waiting_for === 'plan_confirmation' && Array.isArray(activePlan) && activePlan.length > 0) {
            useChatStore.getState().setAgentState({
              stage: active.agent_state.stage || 'plan',
              plan: activePlan,
              current_step: active.agent_state.current_step || 0,
              step_results: normalizeStepResults(active.agent_state.step_results),
              research_notes: active.agent_state.research_notes || '',
              waiting_for: active.agent_state.waiting_for || null,
              strategy_signature: active.agent_state.strategy_signature || null,
              task_fingerprint: active.agent_state.task_fingerprint || null,
              next_action: active.agent_state.next_action || null,
              artifacts: active.agent_state.artifacts || {},
            })
            checkpoint = {
              confirmed_plan: activePlan,
              strategy_signature: active.agent_state.strategy_signature,
              task_fingerprint: active.agent_state.task_fingerprint,
            }
          }
        } catch {
          // Fall through to the explicit user-facing error below.
        }
      }
    }

    if (control === 'execute_confirmed' && !checkpoint) {
      clearAgentState()
      return
    }

    submitLockRef.current = true
    setSubmitting(true)
    try {
      addMessage({
        role: 'user',
        content: visibleContent,
      })
      await sendMessage(
        taskContent,
        useChatStore.getState().currentId ?? undefined,
        undefined,
        fileResults,
        analysisDepth,
        control,
        checkpoint
      )
    } finally {
      submitLockRef.current = false
      setSubmitting(false)
    }
  }

  function handleConfirmPlan() {
    if (busy) return
    void sendPlannedControl('execute_confirmed')
  }

  function handleStopExecution() {
    if (!streaming) return
    stopStreaming()
  }

  const handleSend = async () => {
    const trimmed = input.trim()
    const currentFiles = filesRef.current
    if (!trimmed && currentFiles.length === 0) return
    if (submitLockRef.current || useChatStore.getState().streaming) return

    submitLockRef.current = true
    setSubmitting(true)
    try {

      if (waitingForPlanConfirmation && trimmed) {
        const plannedTask = getPlannedTaskContext()
        const fileResults = plannedTask?.base.files?.map((f) => ({
          name: f.name,
          objectName: f.objectName,
          downloadUrl: f.downloadUrl,
          analysisData: f.analysisData,
        }))
        const taskContent = plannedTask
          ? `${plannedTask.content}\n\n[用户修改策略要求]\n${trimmed}`
          : trimmed
        addMessage({
          role: 'user',
          content: `修改分析策略：${trimmed}`,
        })
        setInput('')
        if (textareaRef.current) textareaRef.current.style.height = 'auto'
        await sendMessage(
          taskContent,
          useChatStore.getState().currentId ?? undefined,
          undefined,
          fileResults,
          analysisDepth,
          'revise_plan'
        )
        return
      }

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

      for (let i = 0; i < currentFiles.length; i++) {
        if (currentFiles[i].status === 'pending') {
          const result = await uploadSingleFile(currentFiles[i], i)
          fileResults[i].objectName = result.objectName
          fileResults[i].downloadUrl = result.downloadUrl
          if (result.objectName && await canAutoAnalyzeStructureFile(currentFiles[i].file)) {
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
      await sendMessage(trimmed || t('chat.analyzingFiles'), useChatStore.getState().currentId ?? undefined, undefined, fileResults, analysisDepth)
    } finally {
      submitLockRef.current = false
      setSubmitting(false)
    }
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
    <div className="border-t border-border/70 bg-background/65 px-3 py-3 backdrop-blur sm:px-4 sm:py-4">
      <div className="mx-auto max-w-4xl">
        {/* File previews */}
        {files.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {files.map((file, i) => (
              <div key={i} className="flex items-center gap-2 rounded-2xl border border-border/80 bg-card/90 px-3 py-2 text-xs shadow-sm">
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

        {/* Input area */}
        <div className="rounded-[28px] border border-border/80 bg-card/90 p-3 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
          {waitingForPlanConfirmation && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <span>策略已生成，尚未执行工具。确认后才会开始调用工具；输入修改要求可重新出策略。</span>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={handleConfirmPlan}
                  className="inline-flex items-center gap-1.5 rounded-full bg-amber-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-amber-700"
                >
                  <Play className="h-3.5 w-3.5" />
                  确认执行
                </button>
                <button
                  type="button"
                  onClick={() => textareaRef.current?.focus()}
                  className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-white px-3 py-1.5 font-medium text-amber-800 transition-colors hover:bg-amber-100 dark:border-amber-500/40 dark:bg-transparent dark:text-amber-100"
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                  修改策略
                </button>
              </div>
            </div>
          )}
          {streaming && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-red-300/70 bg-red-50 px-3 py-2 text-xs text-red-900 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-100">
              <span>{agentState?.stage === 'execute' ? '正在执行分析策略，可随时停止当前执行流。' : '正在生成或传输结果，可随时停止当前执行流。'}</span>
              <button
                type="button"
                onClick={handleStopExecution}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-red-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-red-700"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                停止执行
              </button>
            </div>
          )}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <div ref={modelRef} className="relative z-20">
                <button
                  onClick={() => setModelOpen(!modelOpen)}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-all hover:opacity-80 active:scale-[0.97] ${colorClass}`}
                >
                  <Icon className="w-3 h-3" />
                  <span>{modelLabel}</span>
                  <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${modelOpen ? 'rotate-180' : ''}`} />
                </button>
                {modelOpen && (
                  <div className="absolute bottom-full left-0 z-[120] mb-2 w-72 overflow-hidden rounded-2xl border border-border bg-popover py-1.5 text-popover-foreground shadow-2xl ring-1 ring-black/5 backdrop-blur-sm">
                    <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
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
                          className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-xs transition-colors
                            ${m.id === selectedModel ? 'bg-secondary font-medium' : 'hover:bg-secondary/70'}
                            ${!m.available ? 'cursor-not-allowed opacity-40' : ''}`}
                        >
                          <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border ${MC}`}>
                            <MI className="w-3 h-3" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate">{m.name}</span>
                            <span className="block truncate text-[10px] text-muted-foreground">{m.description}</span>
                          </span>
                          {m.id === selectedModel && (
                            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1 rounded-full border border-border/80 bg-background/75 p-1">
                {analysisDepth === 'deep' ? (
                  <Microscope className="ml-1 h-3.5 w-3.5 text-primary" />
                ) : (
                  <Gauge className="ml-1 h-3.5 w-3.5 text-muted-foreground" />
                )}
                {ANALYSIS_DEPTH_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    title={option.title}
                    aria-pressed={analysisDepth === option.value}
                    onClick={() => setAnalysisDepth(option.value)}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                      analysisDepth === option.value
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-full border border-border/80 bg-background/80 px-3 py-1 text-[11px] text-muted-foreground">
              {streaming ? 'Streaming response...' : t('chat.hint')}
            </div>
          </div>

          <div className="flex items-end gap-3 rounded-[24px] border border-border/80 bg-background/80 px-4 py-3 transition-colors focus-within:border-ring">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mb-0.5 shrink-0 rounded-2xl border border-border/80 bg-card p-2 text-muted-foreground transition-colors hover:bg-secondary"
            >
              <Paperclip className="w-4 h-4" />
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
              placeholder={waitingForPlanConfirmation ? '输入策略修改要求，例如：先不要跑 ESMFold，只做性质预测和关键突变位点排序' : t('chat.placeholder')}
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm leading-7 placeholder:text-muted-foreground focus:outline-none"
            />

            <button
              onClick={handleSend}
              disabled={busy || (!input.trim() && files.length === 0)}
              className="mb-0.5 shrink-0 rounded-2xl bg-primary p-2.5 text-primary-foreground shadow-[0_12px_28px_rgba(37,99,235,0.26)] transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
