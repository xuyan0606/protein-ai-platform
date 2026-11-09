import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { useChatStore } from '@/stores/chat'
import { CHAT_PROMPT_TEMPLATES } from '@/lib/chat-prompt-templates'

export function ChatPromptTemplates({ onSelect }: { onSelect: (text: string) => void }) {
  const [expanded, setExpanded] = useState(true)
  const locked = useChatStore(s => s.streaming || s.agentState?.waiting_for === 'plan_confirmation')

  return (
    <section aria-label="提问模板" className="shrink-0 border-b border-border/65 bg-card/60 px-4 py-3 sm:px-6">
      <div className="mx-auto max-w-[1120px]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <FileText className="h-4 w-4 text-primary" />
            <span>不知道怎么提问？使用模板</span>
          </div>
          <button type="button" aria-expanded={expanded} aria-controls="chat-prompt-templates" aria-label={expanded ? '收起模板' : '展开模板'} onClick={() => setExpanded(value => !value)} className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-secondary">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
        {expanded && (
          <div id="chat-prompt-templates">
            <div className="mt-2 flex flex-wrap gap-2">
              {CHAT_PROMPT_TEMPLATES.map(template => (
                <button key={template.id} type="button" disabled={locked} title={template.hint} onClick={() => onSelect(template.text)} className="rounded-xl border border-border/80 bg-background/80 px-3 py-2 text-xs font-medium transition-colors hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50">
                  {template.title}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {locked ? '请先完成当前回复或处理待确认策略，再使用模板。' : '点击填入输入框，将【】改为实际信息；不清楚的写“未知”。可附序列、结构或数据，填好后发送。'}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
