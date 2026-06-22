import { ChevronDown, ChevronRight, Brain, CheckCircle2, XCircle, Loader2, Clock, FlaskConical, ScrollText, Microscope, FileText } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/stores/chat'

interface Props {
  steps: string[]
}

const stageIcons: Record<string, React.ReactNode> = {
  router: <Brain className="w-4 h-4" />,
  research: <FlaskConical className="w-4 h-4" />,
  plan: <ScrollText className="w-4 h-4" />,
  execute: <Microscope className="w-4 h-4" />,
  synthesize: <FileText className="w-4 h-4" />,
  done: <CheckCircle2 className="w-4 h-4 text-green-500" />,
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3 h-3 text-muted-foreground" />,
  running: <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="w-3 h-3 text-green-500" />,
  failed: <XCircle className="w-3 h-3 text-red-500" />,
}

const stageOrder = ['router', 'research', 'plan', 'execute', 'synthesize'] as const

export function ThinkingChain({ steps }: Props) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(true)
  const agentState = useChatStore((s) => s.agentState)

  const getStageLabel = (s: string): string => {
    const map: Record<string, string> = {
      router: t('agent.analyzing'),
      research: t('agent.gathering'),
      plan: t('agent.planning'),
      execute: t('agent.executing'),
      synthesizing: t('agent.synthesizing'),
      synthesize: t('agent.synthesizing'),
      done: t('agent.complete'),
    }
    return map[s] || s
  }

  const getStageShortLabel = (s: string): string => {
    const map: Record<string, string> = {
      router: t('agent.route'),
      research: t('agent.research'),
      plan: t('agent.plan'),
      execute: t('agent.execute'),
      synthesize: t('agent.synthesize'),
    }
    return map[s] || s
  }

  // Legacy mode: show simple thinking steps
  if (!agentState && steps.length > 0) {
    return <LegacyThinkingChain steps={steps} />
  }

  // No agent state yet
  if (!agentState) return null

  const { stage, plan, step_results, waiting_for } = agentState
  const totalSteps = plan.length

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:bg-secondary transition-colors"
      >
        <Brain className="w-3.5 h-3.5" />
        <span>{t('agent.pipeline')}</span>
        {stage !== 'done' && (
          <span className="text-blue-500 animate-pulse ml-1">
            {getStageLabel(stage)}
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          {stage === 'done' && <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border">
          {/* Stage progress bar */}
          <div className="px-3 py-2">
            <div className="flex items-center gap-1">
              {stageOrder.map((s, i) => {
                const fullOrder = [...stageOrder, 'done']
                const stageIndex = fullOrder.indexOf(stage)
                const isComplete = i < stageIndex
                const isCurrent = s === stage
                return (
                  <div key={s} className="flex items-center gap-1 flex-1">
                    <div
                      className={`w-full h-1 rounded ${
                        isComplete ? 'bg-green-500' : isCurrent ? 'bg-blue-500 animate-pulse' : 'bg-muted'
                      }`}
                    />
                    {i < 4 && <div className="w-2" />}
                  </div>
                )
              })}
            </div>
            <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
              {stageOrder.map((s) => (
                <span
                  key={s}
                  className={stage === s ? 'text-foreground font-medium' : ''}
                >
                  {getStageShortLabel(s)}
                </span>
              ))}
            </div>
          </div>

          {/* Plan steps */}
          {plan.length > 0 && (
            <div className="border-t border-border px-3 py-2">
              <div className="text-[11px] font-medium text-muted-foreground mb-1.5">
                {t('agent.executionPlan', { count: totalSteps })}
              </div>
              <div className="space-y-1">
                {plan.map((step) => (
                  <div
                    key={step.id}
                    className={`flex items-start gap-2 text-xs py-1 px-2 rounded ${
                      step.status === 'running' ? 'bg-blue-500/10' :
                      step.status === 'failed' ? 'bg-red-500/10' : ''
                    }`}
                  >
                    <span className="shrink-0 mt-0.5">
                      {statusIcons[step.status] || statusIcons.pending}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span className="font-mono text-[11px] text-blue-600 dark:text-blue-400">
                        {step.tool_name}
                      </span>
                      <span className="text-muted-foreground ml-1.5">{step.description}</span>
                    </div>
                    {step.status === 'running' && (
                      <span className="text-[10px] text-blue-500 animate-pulse shrink-0">{t('agent.running')}</span>
                    )}
                    {step.status === 'completed' && (
                      <span className="text-[10px] text-green-600 shrink-0">{t('agent.done')}</span>
                    )}
                    {step.status === 'failed' && (
                      <span className="text-[10px] text-red-500 shrink-0">{t('agent.failed')}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Step results */}
          {step_results.length > 0 && (
            <div className="border-t border-border px-3 py-2">
              <div className="text-[11px] font-medium text-muted-foreground mb-1.5">
                {t('agent.results')}
              </div>
              <div className="space-y-1">
                {step_results.map((r, i) => (
                  <div key={i} className="text-[11px] flex items-start gap-1.5">
                    {statusIcons[r.status]}
                    <span className="font-mono">{r.tool}</span>
                    {r.duration && (
                      <span className="text-muted-foreground">({r.duration}s)</span>
                    )}
                    {r.error && (
                      <span className="text-red-500 truncate">{r.error}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Waiting indicator */}
          {waiting_for && (
            <div className="border-t border-border px-3 py-2 bg-amber-500/10">
              <div className="text-[11px] text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                <Clock className="w-3 h-3" />
                {t('agent.waitingFor')} {waiting_for.replace(/_/g, ' ')}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LegacyThinkingChain({ steps }: { steps: string[] }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:bg-secondary transition-colors"
      >
        <Brain className="w-3.5 h-3.5" />
        <span>{t('agent.reasoning', { count: steps.length })}</span>
        <span className="ml-auto">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border px-3 py-2 space-y-1.5">
          {steps.map((step, i) => (
            <div key={i} className="flex gap-2 text-xs">
              <span className="text-muted-foreground font-mono shrink-0">
                {i + 1}.
              </span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
