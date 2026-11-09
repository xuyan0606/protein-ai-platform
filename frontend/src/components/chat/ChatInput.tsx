import { useState, useRef, useEffect, useImperativeHandle, type Ref, type KeyboardEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useShallow } from 'zustand/react/shallow'
import { useChatStore, type AgentState } from '@/stores/chat'
import { useChatStream, type AnalysisDepth } from '@/hooks/useChatStream'
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

export interface ChatInputHandle {
  applyTemplate: (text: string) => void
}

export function ChatInput({ templateRef }: { templateRef?: Ref<ChatInputHandle> }) {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<AttachedFile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submissionStatus, setSubmissionStatus] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [pendingTemplate, setPendingTemplate] = useState<string | null>(null)
  const [editingStrategyKey, setEditingStrategyKey] = useState<string | null>(null)
  const filesRef = useRef<AttachedFile[]>([])
  const submitLockRef = useRef(false)
  const [modelOpen, setModelOpen] = useState(false)
  const [analysisDepth, setAnalysisDepth] = useState<AnalysisDepth>('standard')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const { addMessage, streaming, conversationLoading, conversationLoadError, selectedModel, setSelectedModel, availableModels, fetchModels, agentState, clearAgentState } = useChatStore(useShallow((s) => ({
    addMessage: s.addMessage,
    streaming: s.streaming,
    conversationLoading: s.conversationLoading,
    conversationLoadError: s.conversationLoadError,
    selectedModel: s.selectedModel,
    setSelectedModel: s.setSelectedModel,
    availableModels: s.availableModels,
    fetchModels: s.fetchModels,
    agentState: s.agentState,
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

    const initialConversationId = useChatStore.getState().currentId
    const processInitialState = async () => {
      // Case: file + prompt (from PDB page "Deep Analysis in Chat")
      if (uploadFile) {
        const attachedFile: AttachedFile = { file: uploadFile, status: 'pending', progress: 0 }
        setFiles([attachedFile])
        submitLockRef.current = true
        setSubmitting(true)
        setSubmitError(null)

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
          const destination = useChatStore.getState()
          if (destination.currentId !== initialConversationId || destination.conversationLoading || destination.conversationLoadError) {
            setInput(promptText)
            updateFiles(() => [{ ...attachedFile, status: 'done', progress: 100, objectName, downloadUrl, analysisData }])
            setSubmitError('会话正在切换，内容和附件已保留，请确认当前会话后发送。')
            navigate(location.pathname, { replace: true, state: null })
            return
          }
          addMessage({
            role: 'user',
            content: promptText,
            files: [fileResult],
          })
          setInput('')
          updateFiles(() => [])
          sendMessage(promptText, useChatStore.getState().currentId ?? undefined, undefined, [fileResult], analysisDepth)
          navigate(location.pathname, { replace: true, state: null })
        } catch (error) {
          if (cancelled) return
          setInput(initialPrompt || '')
          setSubmitError(error instanceof Error ? error.message : '附件处理失败，请重试。')
          navigate(location.pathname, { replace: true, state: null })
        } finally {
          submitLockRef.current = false
          setSubmitting(false)
          setSubmissionStatus(null)
        }
        return
      }

      // Case: text prompt only (from Home page)
      if (initialPrompt) {
        if (cancelled) return
        const destination = useChatStore.getState()
        if (destination.conversationLoading || destination.conversationLoadError) {
          setInput(initialPrompt)
          navigate(location.pathname, { replace: true, state: null })
          return
        }
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
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 15000)
    setSubmissionStatus('正在解析结构，完成后生成分析策略…')
    try {
      const resp = await authFetch('/api/pdb/analyze-by-name', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Chat needs the parsed structure facts; an optional AI summary must
        // never hold up task submission or strategy confirmation.
        body: JSON.stringify({ object_name: objectName, include_summary: false }),
        signal: controller.signal,
      })
      if (!resp.ok) throw new Error('结构解析失败，请检查文件后重试。')
      return await resp.json()
    } catch (error) {
      if (controller.signal.aborted) throw new Error('结构解析等待超时，文件已保留，请重试。', { cause: error })
      throw error
    } finally {
      window.clearTimeout(timer)
      setSubmissionStatus(null)
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
    setSubmissionStatus('正在上传附件…')
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
  const busy = streaming || submitting || conversationLoading || Boolean(conversationLoadError)
  const hasLocalPlanCheckpoint = agentState?.waiting_for === 'plan_confirmation'
    && Array.isArray(agentState.plan)
    && agentState.plan.length > 0
    && Boolean(agentState.strategy_signature)
  const waitingForPlanConfirmation = hasLocalPlanCheckpoint && !busy
  const strategyEditKey = hasLocalPlanCheckpoint ? `${agentState.task_fingerprint}:${agentState.strategy_signature}` : null
  const editingStrategy = strategyEditKey !== null && editingStrategyKey === strategyEditKey

  function fillTemplate(text: string) {
    setInput(text)
    setPendingTemplate(null)
    setSubmitError(null)
    requestAnimationFrame(() => {
      const textarea = textareaRef.current
      if (!textarea) return
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
      textarea.focus()
      const start = text.indexOf('【')
      if (start >= 0) textarea.setSelectionRange(start, text.indexOf('】', start) + 1)
    })
  }

  useImperativeHandle(templateRef, () => ({
    applyTemplate(text: string) {
      if (submitLockRef.current || busy || hasLocalPlanCheckpoint) return
      if (input.trim()) setPendingTemplate(text)
      else fillTemplate(text)
    },
  }))

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

  async function sendPlanConfirmation() {
    const chat = useChatStore.getState()
    if (submitLockRef.current || chat.streaming || chat.conversationLoading || chat.conversationLoadError) return
    const visibleContent = '确认执行上述分析策略'
    let checkpoint: {
      confirmed_plan: AgentState['plan']
      strategy_signature?: string | null
      task_fingerprint?: string | null
    } | undefined

    {
      // Confirm exactly the plan this page displayed. The server rejects stale
      // identities; fetching a newer plan here would authorize unseen changes.
      const displayed = useChatStore.getState().agentState
      if (
        displayed?.waiting_for === 'plan_confirmation'
        && Array.isArray(displayed.plan)
        && displayed.plan.length > 0
        && displayed.strategy_signature
      ) {
        checkpoint = {
          confirmed_plan: displayed.plan,
          strategy_signature: displayed.strategy_signature,
          task_fingerprint: displayed.task_fingerprint,
        }
      }
    }

    if (!checkpoint) {
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
        visibleContent,
        useChatStore.getState().currentId ?? undefined,
        undefined,
        undefined,
        analysisDepth,
        'execute_confirmed',
        checkpoint
      )
    } finally {
      submitLockRef.current = false
      setSubmitting(false)
    }
  }

  function handleConfirmPlan() {
    if (busy) return
    void sendPlanConfirmation()
  }

  function handleStopExecution() {
    if (!streaming) return
    stopStreaming()
  }

  const handleSend = async () => {
    const trimmed = input.trim()
    const currentFiles = filesRef.current
    if (!trimmed && currentFiles.length === 0) return
    const chat = useChatStore.getState()
    if (submitLockRef.current || chat.streaming || chat.conversationLoading || chat.conversationLoadError) return

    const sendingConversationId = chat.currentId
    submitLockRef.current = true
    setSubmitting(true)
    try {

      if (waitingForPlanConfirmation && editingStrategy && trimmed && currentFiles.length === 0) {
        const displayed = useChatStore.getState().agentState
        addMessage({
          role: 'user',
          content: `修改分析策略：${trimmed}`,
        })
        setInput('')
        setEditingStrategyKey(null)
        if (textareaRef.current) textareaRef.current.style.height = 'auto'
        await sendMessage(
          trimmed,
          useChatStore.getState().currentId ?? undefined,
          undefined,
          undefined,
          analysisDepth,
          'revise_plan',
          displayed ? {
            confirmed_plan: displayed.plan,
            strategy_signature: displayed.strategy_signature,
            task_fingerprint: displayed.task_fingerprint,
          } : undefined
        )
        return
      }

    // Upload pending files and collect results
      interface FileResult { name: string; size: number; type: string; objectName?: string; downloadUrl?: string; analysisData?: unknown }
      setSubmitError(null)
      const fileResults: FileResult[] = currentFiles.map((f) => ({
        name: f.file.name,
        size: f.file.size,
        type: f.file.type,
        objectName: f.objectName,
        downloadUrl: f.downloadUrl,
        analysisData: f.analysisData,
      }))

      for (let i = 0; i < currentFiles.length; i++) {
        if (!fileResults[i].objectName) {
          const result = await uploadSingleFile(currentFiles[i], i)
          fileResults[i].objectName = result.objectName
          fileResults[i].downloadUrl = result.downloadUrl
        }
        const objectName = fileResults[i].objectName
        if (objectName && !fileResults[i].analysisData && await canAutoAnalyzeStructureFile(currentFiles[i].file)) {
          const analysisData = await analyzePdb(objectName)
          fileResults[i].analysisData = analysisData
          updateFiles((prev) => prev.map((f, j) => j === i ? { ...f, analysisData } : f))
        }
      }

      const destination = useChatStore.getState()
      if (destination.currentId !== sendingConversationId || destination.conversationLoading || destination.conversationLoadError) {
        setSubmitError('会话已切换，草稿和附件已保留，请确认当前会话后重新发送。')
        return
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
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '附件处理失败，请重试。')
    } finally {
      submitLockRef.current = false
      setSubmitting(false)
      setSubmissionStatus(null)
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
                <button disabled={busy} onClick={() => updateFiles((p) => p.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground disabled:opacity-50">
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {submissionStatus && <p role="status" className="mb-2 text-xs text-muted-foreground">{submissionStatus}</p>}
        {submitError && <p role="alert" className="mb-2 text-sm text-red-600">{submitError}</p>}
        {pendingTemplate && (
          <div role="alert" className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-xs">
            <span className="flex-1">输入框已有内容，是否替换为所选模板？已选附件会保留。</span>
            <button type="button" disabled={busy || hasLocalPlanCheckpoint} onClick={() => fillTemplate(pendingTemplate)} className="rounded-lg bg-primary px-3 py-1.5 text-primary-foreground disabled:opacity-50">替换输入</button>
            <button type="button" onClick={() => setPendingTemplate(null)} className="rounded-lg border border-border px-3 py-1.5">保留原文</button>
          </div>
        )}

        {conversationLoading && <p role="status" className="mb-2 text-sm text-muted-foreground">正在加载所选会话，草稿已保留，加载完成后可发送。</p>}
        {conversationLoadError && <p role="alert" className="mb-2 text-sm text-destructive">{conversationLoadError}</p>}
        {/* Input area */}
        <div className="rounded-[28px] border border-border/80 bg-card/90 p-3 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
          {waitingForPlanConfirmation && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <span>{editingStrategy ? '正在修改策略：输入修改要求并发送；也可以取消修改，继续提问。' : '策略已生成，尚未执行工具。可以继续提问；修改方案请点“修改策略”，执行请点“确认执行”。'}</span>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleConfirmPlan}
                  className="inline-flex items-center gap-1.5 rounded-full bg-amber-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-amber-700"
                >
                  <Play className="h-3.5 w-3.5" />
                  确认执行
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingStrategyKey(editingStrategy ? null : strategyEditKey)
                    textareaRef.current?.focus()
                  }}
                  className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-white px-3 py-1.5 font-medium text-amber-800 transition-colors hover:bg-amber-100 dark:border-amber-500/40 dark:bg-transparent dark:text-amber-100"
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                  {editingStrategy ? '取消修改' : '修改策略'}
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
