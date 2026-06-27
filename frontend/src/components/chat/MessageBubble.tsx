import { useTranslation } from 'react-i18next'
import type { ChatMessage } from '@/stores/chat'
import { MarkdownView } from '@/components/chat/MarkdownView'
import { ToolCallCard } from '@/components/chat/ToolCallCard'
import { PDBAnalysisCard, isPDBAnalysisResult, type PDBAnalysisData } from '@/components/analysis/PDBAnalysisCard'
import { Dna, User } from 'lucide-react'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const { t } = useTranslation()
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  const roleLabel = isUser
    ? t('common.you')
    : isSystem
      ? t('common.system')
      : t('common.proteinAI')

  const pdbAnalysis: PDBAnalysisData | undefined = message.files?.find((f) => isPDBAnalysisResult(f.analysisData))?.analysisData as PDBAnalysisData | undefined

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : isSystem
              ? 'bg-orange-500/10 text-orange-500'
              : 'bg-primary/10 text-primary'
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4" />
        ) : isSystem ? (
          <span className="text-xs font-bold">S</span>
        ) : (
          <Dna className="w-4 h-4" />
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : ''}`}>
        {/* Role label */}
        <div
          className={`text-xs text-muted-foreground mb-1 ${
            isUser ? 'text-right' : ''
          }`}
        >
          {roleLabel}
        </div>

        {/* Message body */}
        <div
          className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-primary text-primary-foreground max-w-[85%]'
              : isSystem
                ? 'bg-orange-500/5 border border-orange-500/20'
                : 'bg-card border border-border'
          }`}
        >
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="space-y-2 mb-3">
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
            <MarkdownView content={message.content} />
          ) : (!message.toolCalls || message.toolCalls.length === 0) ? (
            <span className="text-muted-foreground italic text-xs">Thinking...</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}
