import { ArrowUpDown, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useState, useMemo } from 'react'

interface CompareItem {
  id: string
  name: string
  length: number
  molecular_weight_kda: number
  isoelectric_point: number
  gravy: number
  identity_to_query?: number
  stability_score?: number
  mutation_count?: number
  notes?: string
}

interface BatchCompareData {
  title: string
  items: CompareItem[]
}

type SortKey = keyof CompareItem
type SortDir = 'asc' | 'desc'

function DeltaBadge({ value, unit, invert }: { value: number; unit?: string; invert?: boolean }) {
  const positive = invert ? value < 0 : value > 0
  const neutral = Math.abs(value) < 0.001
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-mono ${neutral ? 'text-muted-foreground' : positive ? 'text-emerald-400' : 'text-red-400'}`}>
      {neutral ? <Minus className="w-2.5 h-2.5" /> : positive ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
      {value > 0 ? '+' : ''}{value.toFixed(2)}{unit || ''}
    </span>
  )
}

export function BatchCompare({ data }: { data: BatchCompareData }) {
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [highlightCol, setHighlightCol] = useState<SortKey | null>(null)

  const sorted = useMemo(() => {
    const items = [...data.items]
    items.sort((a, b) => {
      const va = a[sortKey]
      const vb = b[sortKey]
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortDir === 'asc' ? va - vb : vb - va
      }
      return sortDir === 'asc'
        ? String(va || '').localeCompare(String(vb || ''))
        : String(vb || '').localeCompare(String(va || ''))
    })
    return items
  }, [data.items, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const columns: Array<{ key: SortKey; label: string; unit?: string; invert?: boolean }> = [
    { key: 'name', label: 'Name' },
    { key: 'length', label: 'Length' },
    { key: 'molecular_weight_kda', label: 'MW', unit: ' kDa' },
    { key: 'isoelectric_point', label: 'pI' },
    { key: 'gravy', label: 'GRAVY' },
    { key: 'identity_to_query', label: 'Identity' },
    { key: 'stability_score', label: 'Stability' },
    { key: 'mutation_count', label: 'Mutations' },
  ]

  if (data.items.length === 0) {
    return (
      <div className="text-center py-8 text-xs text-muted-foreground">
        No items to compare
      </div>
    )
  }

  return (
    <div className="space-y-3 text-sm">
      <h3 className="font-semibold text-sm">{data.title}</h3>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-secondary/50">
              {columns.map((col) => (
                <th key={col.key} className="text-left py-2.5 px-3 whitespace-nowrap">
                  <button
                    onClick={() => handleSort(col.key)}
                    onMouseEnter={() => setHighlightCol(col.key)}
                    onMouseLeave={() => setHighlightCol(null)}
                    className={`flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors ${
                      highlightCol === col.key ? 'text-foreground' : ''
                    }`}
                  >
                    {col.label}
                    {sortKey === col.key ? (
                      <ArrowUpDown className={`w-2.5 h-2.5 ${sortDir === 'asc' ? 'rotate-0' : 'rotate-180'}`} />
                    ) : (
                      <ArrowUpDown className="w-2.5 h-2.5 opacity-30" />
                    )}
                  </button>
                </th>
              ))}
              {data.items.some((i) => i.notes) && (
                <th className="text-left py-2.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Notes</th>
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map((item) => (
              <tr
                key={item.id}
                className="border-t border-border/30 hover:bg-secondary/20 transition-colors"
              >
                <td className="py-2 px-3">
                  <span className="font-medium">{item.name}</span>
                </td>
                <td className="py-2 px-3 font-mono text-muted-foreground">{item.length}</td>
                <td className="py-2 px-3 font-mono">{item.molecular_weight_kda.toFixed(1)}</td>
                <td className="py-2 px-3 font-mono">{item.isoelectric_point.toFixed(2)}</td>
                <td className="py-2 px-3 font-mono">{item.gravy.toFixed(3)}</td>
                <td className="py-2 px-3">
                  {item.identity_to_query !== undefined ? (
                    <div className="flex items-center gap-1.5">
                      <div className="w-12 h-1.5 bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, item.identity_to_query)}%`,
                            backgroundColor: item.identity_to_query > 80 ? '#34d399' : item.identity_to_query > 50 ? '#fbbf24' : '#f87171',
                          }}
                        />
                      </div>
                      <span className="font-mono text-[10px]">{item.identity_to_query.toFixed(1)}%</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="py-2 px-3">
                  {item.stability_score !== undefined ? (
                    <span className={`font-mono font-medium ${item.stability_score > 7 ? 'text-emerald-400' : item.stability_score > 4 ? 'text-amber-400' : 'text-red-400'}`}>
                      {item.stability_score.toFixed(1)}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="py-2 px-3 font-mono text-muted-foreground">
                  {item.mutation_count ?? '—'}
                </td>
                {data.items.some((i) => i.notes) && (
                  <td className="py-2 px-3 text-[10px] text-muted-foreground max-w-[200px] truncate">
                    {item.notes || ''}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-muted-foreground text-right">
        {data.items.length} items · click column headers to sort
      </p>
    </div>
  )
}

export function isBatchCompareResult(data: unknown): data is BatchCompareData {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return 'title' in d && 'items' in d && Array.isArray(d.items)
}

export function extractBatchCompare(
  items: Array<Record<string, unknown>>,
  title: string = 'Sequence Comparison'
): BatchCompareData | null {
  if (!items || items.length === 0) return null
  const mapped: CompareItem[] = items.map((item, i) => ({
    id: (item.id || item.name || `item-${i}`) as string,
    name: (item.name || item.accession || `Item ${i + 1}`) as string,
    length: (item.length || item.query_length || 0) as number,
    molecular_weight_kda: (item.molecular_weight_kda || 0) as number,
    isoelectric_point: (item.isoelectric_point || 0) as number,
    gravy: (item.gravy || 0) as number,
    identity_to_query: item.identity_to_query as number | undefined,
    stability_score: item.stability_score as number | undefined,
    mutation_count: item.mutation_count as number | undefined,
    notes: item.notes as string | undefined,
  }))
  return { title, items: mapped }
}
