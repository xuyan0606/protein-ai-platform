import { memo } from 'react'

interface Props {
  content: string
}

export const MarkdownView = memo(function MarkdownView({ content }: Props) {
  // Simple markdown rendering without heavy dependencies for now
  // Full react-markdown + rehype-katex + Shiki will be added in a follow-up
  const rendered = renderSimpleMarkdown(content)

  return (
    <div
      className="prose prose-sm dark:prose-invert max-w-none break-words"
      dangerouslySetInnerHTML={{ __html: rendered }}
    />
  )
})

function renderSimpleMarkdown(text: string): string {
  let html = text
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_: string, lang: string, code: string) => {
      return `<pre class="bg-secondary rounded-lg p-4 overflow-x-auto my-3 text-xs"><code class="language-${lang}">${code.trim()}</code></pre>`
    })
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-secondary px-1.5 py-0.5 rounded text-xs font-mono">$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold mt-5 mb-3">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold mt-6 mb-4">$1</h1>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p class="my-2">')
    // Single newline → <br>
    .replace(/\n/g, '<br/>')

  return `<p class="my-2">${html}</p>`
}
