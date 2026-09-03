import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'

interface Props {
  content: string
  streaming?: boolean
  compact?: boolean
}

const STANDALONE_SECTIONS = [
  '执行摘要',
  '摘要',
  '结论',
  '总结',
  '建议',
]

function headingLevel(marker: string) {
  return marker.includes('.') ? '###' : '##'
}

function looksLikeTitle(line: string) {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('|') || trimmed.startsWith('- ') || trimmed.startsWith('>')) {
    return false
  }
  return trimmed.length <= 40 && /(报告|分析|改造|设计|评估|总结|方案)/.test(trimmed)
}

function normalizeTableRows(text: string) {
  const repaired = text
    .replace(/\|\s+\|(?=[^|\n])/g, '|\n|')

  const lines = compactBlankLinesBetweenPipeFragments(repaired.split('\n'))
  const normalizedLines: string[] = []
  let tableBlock: string[] = []

  const flushTableBlock = () => {
    if (tableBlock.length === 0) return
    const leadingLabelIndex = findLeadingTableLabelIndex(normalizedLines)
    const leadingLabel = leadingLabelIndex >= 0 ? normalizedLines[leadingLabelIndex].trim() : undefined
    const normalized = normalizeTableBlock(tableBlock, leadingLabel)
    if (normalized.consumedLeadingLabel && leadingLabelIndex >= 0) {
      normalizedLines.splice(leadingLabelIndex)
    }
    normalizedLines.push(...normalized.lines)
    tableBlock = []
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const nextLine = lines[index + 1]
    if (isPipeLikeLine(line) && (isPipeTableLine(line) || tableBlock.length > 0 || Boolean(nextLine && isPipeLikeLine(nextLine)))) {
      tableBlock.push(line)
      continue
    }
    flushTableBlock()
    normalizedLines.push(line)
  }
  flushTableBlock()

  return normalizedLines.join('\n')
}

function compactBlankLinesBetweenPipeFragments(lines: string[]) {
  return lines.filter((line, index) => {
    if (line.trim()) return true

    const previous = findPreviousNonEmptyLine(lines, index)
    const next = findNextNonEmptyLine(lines, index)
    return !(previous && next && isPipeLikeLine(previous) && isPipeLikeLine(next))
  })
}

function findPreviousNonEmptyLine(lines: string[], beforeIndex: number) {
  for (let index = beforeIndex - 1; index >= 0; index -= 1) {
    if (lines[index].trim()) return lines[index]
  }
  return undefined
}

function findNextNonEmptyLine(lines: string[], afterIndex: number) {
  for (let index = afterIndex + 1; index < lines.length; index += 1) {
    if (lines[index].trim()) return lines[index]
  }
  return undefined
}

function isPipeLikeLine(line: string) {
  return line.trim().startsWith('|')
}

function isPipeTableLine(line: string) {
  const trimmed = line.trim()
  return trimmed.startsWith('|') && (trimmed.match(/\|/g)?.length || 0) >= 2
}

function splitPipeCells(line: string) {
  const cells = line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|+$/, '')
    .split('|')
    .map((cell) => cell.trim())

  const lastCell = cells[cells.length - 1]
  const previousCells = cells.slice(0, -1)
  if (lastCell && /^:?-{3,}:?$/.test(lastCell) && previousCells.some((cell) => !/^:?-{3,}:?$/.test(cell))) {
    return previousCells
  }
  return cells
}

function isSeparatorCells(cells: string[]) {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
}

function isLeadingTableLabel(line: string) {
  const trimmed = line.trim()
  return (
    Boolean(trimmed) &&
    trimmed.length <= 16 &&
    !trimmed.startsWith('#') &&
    !trimmed.startsWith('|') &&
    !trimmed.startsWith('- ') &&
    !trimmed.startsWith('>') &&
    !/^\d+\.\s/.test(trimmed)
  )
}

function findLeadingTableLabelIndex(lines: string[]) {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]
    if (!line.trim()) continue
    return isLeadingTableLabel(line) ? index : -1
  }
  return -1
}

function formatPipeRow(cells: string[], separator = false) {
  if (separator) {
    return `|${cells.map((cell) => cell || '---').join('|')}|`
  }
  return `| ${cells.join(' | ')} |`
}

function mergeSeparatorRows(rows: string[][]) {
  const merged: string[][] = []

  for (let index = 0; index < rows.length; index += 1) {
    const cells = rows[index]
    if (!isSeparatorCells(cells)) {
      merged.push(cells)
      continue
    }

    const separatorCells = [...cells]
    while (index + 1 < rows.length && isSeparatorCells(rows[index + 1])) {
      separatorCells.push(...rows[index + 1])
      index += 1
    }
    merged.push(separatorCells)
  }

  return merged
}

function inferTableColumnCount(rows: string[][], separatorIndex: number) {
  let maxColumns = Math.max(...rows.map((cells) => cells.length))

  for (let index = separatorIndex + 1; index < rows.length - 1; index += 1) {
    const current = rows[index]
    const next = rows[index + 1]
    if (current.length === 1 && !isSeparatorCells(next)) {
      maxColumns = Math.max(maxColumns, current.length + next.length)
    }
  }

  return maxColumns
}

const EC_PREDICTION_HEADERS = ['序号', 'EC编号', '类别', '置信度', '名称']

function isEcNumberCell(cell: string) {
  return /^(?:EC\s*)?\d+(?:\.(?:\d+|-)){3}$/i.test(cell.trim())
}

function hasEcPredictionHeaderShape(header: string[]) {
  const normalizedHeader = header.map((cell) => cell.replace(/\s/g, ''))
  return (
    normalizedHeader.includes('EC编号') &&
    normalizedHeader.some((cell) => cell === '级别' || cell === '类别') &&
    normalizedHeader.some((cell) => cell === '信心' || cell === '置信度') &&
    normalizedHeader.includes('名称')
  )
}

function hasIndexedEcPredictionRows(rows: string[][], separatorIndex: number) {
  return rows.slice(separatorIndex + 1).some((cells) => (
    cells.length >= EC_PREDICTION_HEADERS.length &&
    /^\d+$/.test(cells[0]?.trim() || '') &&
    isEcNumberCell(cells[1] || '')
  ))
}

function repairKnownHeaderShape(rows: string[][], separatorIndex: number, maxColumns: number) {
  if (
    maxColumns === EC_PREDICTION_HEADERS.length &&
    hasEcPredictionHeaderShape(rows[0]) &&
    rows[0].length < maxColumns &&
    hasIndexedEcPredictionRows(rows, separatorIndex)
  ) {
    rows[0] = [...EC_PREDICTION_HEADERS]
  }
}

function normalizeTableBlock(lines: string[], leadingLabel?: string) {
  const rows = mergeSeparatorRows(lines.map((line) => splitPipeCells(line)))
  const separatorIndex = rows.findIndex((cells) => isSeparatorCells(cells))
  if (separatorIndex <= 0) {
    return {
      consumedLeadingLabel: false,
      lines: lines.map((line) => {
        const cells = splitPipeCells(line)
        return cells.length >= 2 ? formatPipeRow(cells) : line
      }),
    }
  }

  let consumedLeadingLabel = false
  const maxColumns = inferTableColumnCount(rows, separatorIndex)
  repairKnownHeaderShape(rows, separatorIndex, maxColumns)
  if (leadingLabel && rows[0].length + 1 === maxColumns) {
    rows[0] = [leadingLabel, ...rows[0]]
    consumedLeadingLabel = true
  }

  const normalizedRows: string[][] = []
  for (let index = 0; index < rows.length; index += 1) {
    const cells = rows[index]
    if (index <= separatorIndex) {
      normalizedRows.push(cells)
      continue
    }

    const next = rows[index + 1]
    if (cells.length === 1 && next && !isSeparatorCells(next) && cells.length + next.length === maxColumns) {
      normalizedRows.push([...cells, ...next])
      index += 1
      continue
    }
    normalizedRows.push(cells)
  }

  return {
    consumedLeadingLabel,
    lines: normalizedRows.map((cells, index) => {
      if (index === separatorIndex) {
        return formatPipeRow(Array.from({ length: maxColumns }, () => '---'), true)
      }

      const padded = [...cells]
      while (padded.length < maxColumns) {
        padded.push(index < separatorIndex ? `列 ${padded.length + 1}` : '')
      }
      return formatPipeRow(padded)
    }),
  }
}

function containsLikelyTable(text: string) {
  const normalized = normalizeTableRows(text)
  const lines = normalized.split('\n')
  return lines.some((line, index) => {
    if (!isPipeTableLine(line)) return false
    const next = lines[index + 1]
    if (!next || !isPipeTableLine(next)) return false
    return isSeparatorCells(splitPipeCells(next))
  })
}

function normalizeInlineNumberedList(text: string) {
  return text
    .replace(/([：:])\s*(\d+\.\s)/g, '$1\n$2')
    .replace(/\s(?=\d+\.\s)/g, '\n')
}

function normalizeMarkdown(raw: string, compact = false) {
  let text = raw
    .replace(/\r\n/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .trim()

  if (!text) return text

  text = normalizeInlineNumberedList(text)

  for (const section of STANDALONE_SECTIONS) {
    const escaped = section.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    text = text
      .replace(new RegExp(`([^\\n])\\s+(${escaped})(?=\\s)`, 'g'), '$1\n\n## $2\n')
      .replace(new RegExp(`^(${escaped})(?=\\s)`, 'm'), '## $1\n')
  }

  text = text
    .replace(/^\s*---\s*$/gm, '\n---\n')
    .replace(/(^|\n)(\d+(?:\.\d+)*)\s+([^\n|]{2,50})\s+(?=\|)/g, (_, prefix, marker, title) => {
      const level = headingLevel(marker)
      return `${prefix}${level} ${marker} ${title.trim()}\n\n`
    })
    .replace(/([。；：!?])\s*((?:\d+(?:\.\d+)*)\s+[^\n|]{2,40})(?=\s*\|)/g, (_, punctuation, title) => {
      const match = title.match(/^(\d+(?:\.\d+)*)/)
      const level = headingLevel(match?.[1] || '')
      return `${punctuation}\n\n${level} ${title.trim()}\n`
    })
    .replace(/([。；：!?])((?:\d+(?:\.\d+)*)\s+[^\n]{2,36})/g, (_, punctuation, title) => {
      const match = title.match(/^(\d+(?:\.\d+)*)/)
      const level = headingLevel(match?.[1] || '')
      return `${punctuation}\n\n${level} ${title.trim()}\n`
    })
    .replace(/([^\n])\s+(#{1,6}\s)/g, '$1\n\n$2')
    // Split an inline table only when the line does not already start as a
    // table row. Otherwise a valid row is split at its second cell.
    .replace(/^(?!\s*\|)([^\n]*?)(\|(?:[^|\n]+\|){2,})$/gm, '$1\n\n$2')
    .replace(/([。；：!?])(-\s)/g, '$1\n\n$2')
    .replace(/([。；：!?])(\|[-| :]+\|)/g, '$1\n\n$2')
    .replace(/\n{3,}/g, '\n\n')

  text = normalizeTableRows(text)

  const lines = text.split('\n')
  const normalizedLines = lines.map((line) => {
    const trimmed = line.trim()
    if (!trimmed) return ''

    if (!compact && looksLikeTitle(trimmed)) {
      return `# ${trimmed}`
    }

    const sectionMatch = trimmed.match(/^(\d+(?:\.\d+)*)\s+(.{2,40})$/)
    if (
      sectionMatch &&
      !trimmed.includes('|') &&
      !trimmed.startsWith('>') &&
      !trimmed.startsWith('- ') &&
      !/^\d+\.\s/.test(trimmed)
    ) {
      return compact ? trimmed : `${headingLevel(sectionMatch[1])} ${trimmed}`
    }

    return line
  })

  return normalizedLines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

function normalizeMarkdownStreaming(raw: string) {
  const text = raw
    .replace(/\r\n/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    // Keep streaming normalization intentionally light to avoid reflow-heavy
    // structure rewrites while tokens are still arriving.
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return containsLikelyTable(text) ? normalizeTableRows(text) : text
}

export const MarkdownView = memo(function MarkdownView({ content, streaming = false, compact = false }: Props) {
  const renderedContent = useMemo(
    () => (streaming ? normalizeMarkdownStreaming(content) : normalizeMarkdown(content, compact)),
    [content, streaming, compact]
  )

  if (streaming && !containsLikelyTable(renderedContent)) {
    return (
      <div className={`report-markdown max-w-none whitespace-pre-wrap break-words text-[rgb(31,35,41)] ${compact ? 'text-[14px] leading-relaxed' : 'text-[15px] leading-relaxed'}`}>
        {renderedContent}
      </div>
    )
  }

  return (
    <div className={`report-markdown max-w-none break-words text-[rgb(31,35,41)] ${compact ? 'text-[14px] leading-relaxed' : 'text-[15px] leading-relaxed'}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          // Open links in new tab
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary underline decoration-primary/35 underline-offset-4 transition-opacity hover:opacity-80"
              {...props}
            >
              {children}
            </a>
          ),
          h1: ({ children, ...props }) => (
            <h1
              className={compact
                ? 'mb-2 mt-3 text-[14px] font-semibold leading-relaxed text-[rgb(31,35,41)] first:mt-0'
                : 'mb-3 mt-8 text-[1.5rem] font-semibold leading-tight tracking-tight text-[rgb(31,35,41)] first:mt-0'}
              {...props}
            >
              {children}
            </h1>
          ),
          h2: ({ children, ...props }) => (
            <h2
              className={compact
                ? 'mb-2 mt-3 text-[14px] font-semibold leading-relaxed text-[rgb(31,35,41)] first:mt-0'
                : 'mb-2.5 mt-7 text-[1.22rem] font-semibold leading-snug tracking-tight text-[rgb(31,35,41)] first:mt-0'}
              {...props}
            >
              {children}
            </h2>
          ),
          h3: ({ children, ...props }) => (
            <h3
              className={compact
                ? 'mb-2 mt-3 text-[14px] font-semibold leading-relaxed text-[rgb(31,35,41)] first:mt-0'
                : 'mb-2 mt-5 text-[1.05rem] font-semibold leading-snug text-[rgb(31,35,41)] first:mt-0'}
              {...props}
            >
              {children}
            </h3>
          ),
          h4: ({ children, ...props }) => (
            <h4 className={compact ? 'mb-2 mt-3 text-[14px] font-semibold leading-relaxed text-[rgb(31,35,41)] first:mt-0' : 'mb-2 mt-4 text-[0.98rem] font-semibold text-[rgb(31,35,41)] first:mt-0'} {...props}>
              {children}
            </h4>
          ),
          p: ({ children, ...props }) => (
            <p className={compact ? 'my-2 text-[14px] leading-relaxed text-[rgb(31,35,41)] first:mt-0 last:mb-0' : 'my-3 text-[15px] leading-relaxed text-[rgb(31,35,41)] first:mt-0 last:mb-0'} {...props}>
              {children}
            </p>
          ),
          ul: ({ children, ...props }) => (
            <ul className={compact ? 'my-2 list-disc space-y-1.5 pl-5 marker:text-primary' : 'my-2 list-disc space-y-1.5 pl-6 marker:text-primary'} {...props}>
              {children}
            </ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className={compact ? 'my-2 list-decimal space-y-1.5 pl-5 marker:font-semibold marker:text-primary' : 'my-2 list-decimal space-y-1.5 pl-12 marker:font-semibold marker:text-primary'} {...props}>
              {children}
            </ol>
          ),
          li: ({ children, ...props }) => (
            <li className={compact ? 'my-0.5 pl-1 text-[14px] leading-relaxed text-[rgb(31,35,41)]' : 'my-0.5 pl-1 text-[15px] leading-relaxed text-[rgb(31,35,41)]'} {...props}>
              {children}
            </li>
          ),
          blockquote: ({ children, ...props }) => (
            <blockquote
              className="my-4 rounded-r-lg border-l-4 border-l-[#bbbfc4] bg-[#bbbfc4]/10 px-4 py-2 text-[14px] leading-relaxed text-[#646a73] not-italic"
              {...props}
            >
              {children}
            </blockquote>
          ),
          hr: (props) => (
            <hr className="my-6 border-0 border-t border-[rgba(31,35,41,0.15)]" {...props} />
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-[rgb(31,35,41)]" {...props}>
              {children}
            </strong>
          ),
          // Style code blocks
          pre: ({ children, ...props }) => (
            <pre
              className="my-4 overflow-x-auto rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 text-[12px] leading-relaxed text-slate-800"
              {...props}
            >
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-sm font-normal text-primary" {...props}>
                  {children}
                </code>
              )
            }
            return <code className={className} {...props}>{children}</code>
          },
          // Style tables for GFM
          table: ({ children, ...props }) => (
            <div className="my-4 max-w-full overflow-x-auto rounded-md border border-border bg-white">
              <table className="w-max min-w-full table-auto border-collapse text-sm" {...props}>
                {children}
              </table>
            </div>
          ),
          th: ({ children, ...props }) => (
            <th
              className="min-w-[8rem] max-w-[22rem] whitespace-normal break-words border border-slate-200 bg-slate-50 px-3 py-2 text-left text-[13px] font-semibold text-slate-700 [overflow-wrap:anywhere]"
              {...props}
            >
              {children}
            </th>
          ),
          td: ({ children, ...props }) => (
            <td className="min-w-[8rem] max-w-[22rem] whitespace-normal break-words border border-slate-200 px-3 py-2 align-top text-[13px] leading-relaxed text-[rgb(31,35,41)] [overflow-wrap:anywhere]" {...props}>
              {children}
            </td>
          ),
        }}
      >
        {renderedContent}
      </ReactMarkdown>
    </div>
  )
})
