import { useState, useEffect, useMemo } from 'react'
import { Search, Play, Loader2, CheckCircle2, XCircle, ChevronRight, Wrench, Beaker, Zap, Box } from 'lucide-react'
import { api } from '@/lib/api'

interface ToolSchema {
  name: string
  description: string
  category: string
  is_async: boolean
  parameters: {
    type: string
    properties: Record<string, { type: string; description?: string; default?: unknown; items?: { type: string } }>
    required?: string[]
  }
}

interface ToolResult {
  status: string
  result: Record<string, unknown>
}

const CATEGORY_ICONS: Record<string, typeof Beaker> = {
  design: Box,
  prediction: Zap,
  simulation: Beaker,
  search: Search,
  structure: Box,
  engineering: Wrench,
  docking: Box,
  analysis: Zap,
}

export function ToolPanel() {
  const [tools, setTools] = useState<ToolSchema[]>([])
  const [categories, setCategories] = useState<Record<string, string[]>>({})
  const [activeCat, setActiveCat] = useState<string>('all')
  const [selectedTool, setSelectedTool] = useState<ToolSchema | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ToolResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    api.getTools().then((data) => {
      const list: ToolSchema[] = data.tools || []
      setTools(list)
      setCategories(data.categories || {})
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const filteredTools = useMemo(() => {
    let result = tools
    // Category filter
    if (activeCat !== 'all') {
      const catToolNames = categories[activeCat] || []
      result = result.filter((t) => catToolNames.includes(t.name))
    }
    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
      )
    }
    return result
  }, [tools, activeCat, categories, searchQuery])

  const selectTool = (tool: ToolSchema) => {
    setSelectedTool(tool)
    setFormValues({})
    setResult(null)
    setError(null)
  }

  const handleRun = async () => {
    if (!selectedTool) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const params: Record<string, unknown> = {}
      const props = selectedTool.parameters.properties || {}
      for (const [key, schema] of Object.entries(props)) {
        const raw = formValues[key]
        if (raw === undefined || raw === '') {
          if (schema.default !== undefined) {
            params[key] = schema.default
          }
          continue
        }
        if (schema.type === 'integer' || schema.type === 'number') {
          params[key] = Number(raw)
        } else if (schema.type === 'boolean') {
          params[key] = raw === 'true'
        } else if (schema.type === 'array' && schema.items) {
          try {
            params[key] = JSON.parse(raw)
          } catch {
            params[key] = raw.split(',').map((s) => s.trim())
          }
        } else {
          params[key] = raw
        }
      }
      const res = await api.callTool(selectedTool.name, params)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Tool execution failed')
    } finally {
      setRunning(false)
    }
  }

  const label = (key: string) => key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  const placeholder = (schema: { type: string; default?: unknown; description?: string }) => {
    if (schema.default !== undefined) return String(schema.default)
    if (schema.description) return schema.description.substring(0, 60)
    if (schema.type === 'array') return '["val1","val2"] or val1,val2'
    return ''
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const categoryNames = Object.keys(categories)

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="relative mb-2">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search tools..."
          className="w-full pl-6.5 pr-2 py-1 rounded-md border border-border bg-transparent text-xs focus:outline-none focus:border-ring"
        />
      </div>

      {/* Category filter */}
      <div className="flex items-center gap-1 mb-3 flex-wrap">
        <button
          onClick={() => { setActiveCat('all'); setSelectedTool(null) }}
          className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
            activeCat === 'all' ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
          }`}
        >
          All ({tools.length})
        </button>
        {categoryNames.map((cat) => {
          const Icon = CATEGORY_ICONS[cat] || Beaker
          const count = (categories[cat] || []).length
          return (
            <button
              key={cat}
              onClick={() => { setActiveCat(cat); setSelectedTool(null) }}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                activeCat === cat ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground hover:bg-secondary/70'
              }`}
            >
              <Icon className="w-2.5 h-2.5" />
              {cat} ({count})
            </button>
          )
        })}
      </div>

      {/* Tool list or detail */}
      {!selectedTool ? (
        <div className="space-y-1 overflow-y-auto flex-1">
          {filteredTools.map((tool) => (
            <button
              key={tool.name}
              onClick={() => selectTool(tool)}
              className="w-full text-left px-2.5 py-2 rounded-md hover:bg-secondary/50 transition-colors group"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium truncate">{tool.name}</span>
                <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
              </div>
              <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">
                {tool.description}
              </p>
            </button>
          ))}
          {filteredTools.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6">
              {searchQuery ? 'No tools match your search' : 'No tools in this category'}
            </p>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Back + tool name */}
          <button
            onClick={() => setSelectedTool(null)}
            className="text-xs text-muted-foreground hover:text-foreground mb-2 flex items-center gap-1"
          >
            ← Back to list
          </button>
          <h4 className="text-sm font-medium mb-1">{selectedTool.name}</h4>
          <p className="text-[11px] text-muted-foreground mb-3">{selectedTool.description}</p>

          {/* Parameter form */}
          <div className="space-y-2 flex-1 overflow-y-auto mb-3">
            {Object.entries(selectedTool.parameters.properties || {}).map(([key, schema]) => {
              const isRequired = selectedTool.parameters.required?.includes(key)
              return (
                <div key={key} className="space-y-0.5">
                  <label className="text-[10px] font-medium text-muted-foreground flex items-center gap-1">
                    {label(key)}
                    {isRequired && <span className="text-red-400">*</span>}
                    <span className="text-[9px] opacity-50">({schema.type})</span>
                  </label>
                  {schema.type === 'boolean' ? (
                    <select
                      value={formValues[key] || ''}
                      onChange={(e) => setFormValues((p) => ({ ...p, [key]: e.target.value }))}
                      className="w-full px-2 py-1 rounded-md border border-border bg-transparent text-xs focus:outline-none focus:border-ring"
                    >
                      <option value="">—</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={formValues[key] || ''}
                      onChange={(e) => setFormValues((p) => ({ ...p, [key]: e.target.value }))}
                      placeholder={placeholder(schema)}
                      className="w-full px-2 py-1 rounded-md border border-border bg-transparent text-xs font-mono focus:outline-none focus:border-ring"
                    />
                  )}
                  {schema.description && (
                    <p className="text-[9px] text-muted-foreground/70">{schema.description}</p>
                  )}
                </div>
              )
            })}
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-40 transition-colors shrink-0"
          >
            {running ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            {running ? 'Running...' : 'Run Tool'}
          </button>

          {/* Result */}
          {result && (
            <div className="mt-3 p-2.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 shrink-0">
              <div className="flex items-center gap-1.5 mb-1.5">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span className="text-[10px] font-medium text-emerald-400">Result</span>
              </div>
              <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap break-all font-mono max-h-40 overflow-y-auto">
                {JSON.stringify(result.result || result, null, 2)}
              </pre>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-2 p-2.5 rounded-md bg-red-500/10 border border-red-500/20 shrink-0">
              <div className="flex items-center gap-1.5">
                <XCircle className="w-3 h-3 text-red-400" />
                <span className="text-[10px] text-red-400">{error}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
