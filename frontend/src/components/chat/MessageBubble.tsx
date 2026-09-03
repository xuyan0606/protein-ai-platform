import { memo } from 'react'
import type { ChatMessage } from '@/stores/chat'
import { MarkdownView } from '@/components/chat/MarkdownView'
import { ToolCallCard } from '@/components/chat/ToolCallCard'
import { PDBAnalysisCard, type PDBAnalysisData } from '@/components/analysis/PDBAnalysisCard'
import { isPDBAnalysisResult } from '@/components/analysis/resultGuards'
import { ReportBody, ReportShell } from '@/components/analysis/ReportShell'
import { PublishToolbar } from '@/components/chat/PublishToolbar'

interface Props {
  message: ChatMessage
  conversationId?: string | null
  projectId?: string | null
  isStreaming?: boolean
}

function looksLikeStructuredReport(content: string) {
  const text = content.trim()
  if (text.length < 180) return false
  return (
    /(^|\n)(执行摘要|摘要|结论|建议|总结|AI Summary|##\s|###\s)/m.test(text) ||
    /\|[^|\n]+\|[^|\n]+\|/.test(text) ||
    /(^|\s)\d+\.\s+\S+/m.test(text) ||
    /(报告|分析|改造方案|实验验证|突变优先级)/.test(text)
  )
}

function MessageBubbleBase({ message, conversationId, isStreaming = false }: Props) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isAssistant = !isUser && !isSystem

  const pdbAnalysis: PDBAnalysisData | undefined = message.files?.find((f) => isPDBAnalysisResult(f.analysisData))?.analysisData as PDBAnalysisData | undefined
  // Avoid switching the outer message container mid-stream, which causes a
  // visible relayout once long reports cross the structured-report threshold.
  const shouldUseReportShell =
    isAssistant && !isStreaming && !!message.content && looksLikeStructuredReport(message.content)

  return (
    <div className="flex">
      {/* Avatar */}
      {isSystem && (
        <div
          className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-orange-500/20 bg-orange-500/10 text-orange-500 shadow-sm"
        >
          <span className="text-xs font-bold">S</span>
        </div>
      )}

      {/* Content */}
      <div className={`min-w-0 ${isUser ? 'w-full' : 'w-full'}`}>
        {/* Message body */}
        <div
          className={`w-full text-sm ${
            isUser
              ? 'mx-auto max-w-[860px] rounded-[24px] border border-border/70 bg-secondary/30 px-4 py-3.5 text-foreground/78 shadow-[0_8px_28px_rgba(15,23,42,0.04)]'
              : isSystem
                ? 'rounded-[24px] border border-orange-500/20 bg-orange-500/5 px-5 py-4'
                : 'px-0 py-1'
          }`}
        >
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className={`mb-5 space-y-2 ${isAssistant ? 'mx-auto max-w-[860px]' : ''}`}>
              {message.toolCalls.map((tc) => (
                <ToolCallCard key={tc.id} toolCall={tc} />
              ))}
            </div>
          )}
          {pdbAnalysis && isUser && (
            <div className="mb-3">
              <PDBAnalysisCard data={pdbAnalysis} />
            </div>
          )}
          {message.content ? (
            <div className={isAssistant ? 'mx-auto max-w-[900px]' : ''}>
              {shouldUseReportShell ? (
                <ReportShell>
                  <ReportBody className="space-y-0">
                    <MarkdownView content={message.content} streaming={isStreaming} />
                  </ReportBody>
                </ReportShell>
              ) : (
                <MarkdownView content={message.content} streaming={isStreaming} compact={isUser} />
              )}
            </div>
          ) : (!message.toolCalls || message.toolCalls.length === 0) ? (
            <span className="text-muted-foreground italic text-xs">Thinking...</span>
          ) : null}
        </div>

        {/* Publish toolbar — only on assistant messages with content */}
        {!isUser && !isSystem && message.content && (
          <PublishToolbar
            content={message.content}
            conversationId={conversationId ? Number(conversationId) : undefined}
          />
        )}
      </div>
    </div>
  )
}

export const MessageBubble = memo(
  MessageBubbleBase,
  (prev, next) =>
    prev.message === next.message &&
    prev.conversationId === next.conversationId &&
    prev.projectId === next.projectId &&
    prev.isStreaming === next.isStreaming
)
