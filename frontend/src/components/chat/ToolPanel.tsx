import { useState, useEffect, useMemo } from 'react'
import { Search, Play, Loader2, CheckCircle2, XCircle, ChevronRight, Wrench, Beaker, Zap, Box } from 'lucide-react'
import { api } from '@/lib/api'

interface ToolSchema {
  name: string
  description: string
  category: string
  is_async: boolean
  requires?: string[]
  provides?: string[]
  evidence_level?: string
  runtime_mode?: string
  license_status?: string
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
    const props = selectedTool.parameters.properties || {}
    const required = selectedTool.parameters.required || []
    const missing = required.filter((key) => {
      const raw = formValues[key]
      const schema = props[key]
      return (raw === undefined || raw.trim() === '') && schema?.default === undefined
    })
    if (missing.length > 0) {
      setError(`Missing required parameter: ${missing.map(label).join(', ')}`)
      setResult(null)
      return
    }

    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const params: Record<string, unknown> = {}
      for (const [key, schema] of Object.entries(props)) {
        const raw = formValues[key]
        if (raw === undefined || raw === '') {
          if (schema.default !== undefined) {
            params[key] = schema.default
          }
          continue
        }
        if (schema.type === 'integer' || schema.type === 'number') {
          const parsed = Number(raw)
          if (!Number.isFinite(parsed)) {
            throw new Error(`${label(key)} must be a valid number`)
          }
          params[key] = parsed
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
      const hasValue = (keys: string[]) => keys.some((key) => {
        const value = params[key]
        return value !== undefined && value !== null && value !== ''
      })
      const preflight = await api.preflightTool(selectedTool.name, {
        has_sequence: hasValue(['sequence', 'protein_sequence', 'seq']),
        has_pdb: hasValue(['pdb_data', 'pdb_structure', 'pdb_path', 'pdb_object_name']),
        has_ligand_3d: hasValue(['ligand_3d', 'ligand_3d_path', 'ligand_3d_object_name', 'ligand_pdbqt_path', 'ligand_pdbqt_object_name']),
        has_topology: hasValue(['topology', 'topology_path', 'topology_object_name']),
      })
      if (!preflight.allowed) {
        const details = preflight.violations.map((item) => item.dependency || item.code).join(', ')
        throw new Error(`Preflight blocked: ${details}`)
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
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search tools..."
          className="w-full rounded-2xl border border-border/80 bg-background/80 py-2.5 pl-9 pr-3 text-xs shadow-sm outline-none transition focus:border-primary/30 focus:ring-2 focus:ring-primary/10"
        />
      </div>

      {/* Category filter */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <button
          onClick={() => { setActiveCat('all'); setSelectedTool(null) }}
          className={`rounded-full px-4 py-2 text-sm font-medium leading-none transition-colors ${
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
              className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium leading-none transition-colors ${
                activeCat === cat ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground hover:bg-secondary/70'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {cat} ({count})
            </button>
          )
        })}
      </div>

      {/* Tool list or detail */}
      {!selectedTool ? (
        <div className="space-y-2 overflow-y-auto flex-1 pr-1">
          {filteredTools.map((tool) => (
            <button
              key={tool.name}
              onClick={() => selectTool(tool)}
              className="group w-full rounded-[22px] border border-border/70 bg-card/80 px-3.5 py-3 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/20 hover:bg-primary/5"
            >
              <div className="flex items-center justify-between">
                <span className="truncate text-sm font-medium">{tool.name}</span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground line-clamp-2">
                {tool.description}
              </p>
              <div className="mt-2 flex flex-wrap gap-1 text-[9px] text-muted-foreground">
                <span className="rounded-md bg-secondary px-1.5 py-0.5">{tool.evidence_level || 'unverified'}</span>
                <span className="rounded-md bg-secondary px-1.5 py-0.5">{tool.runtime_mode || (tool.is_async ? 'async_worker' : 'inline_sync')}</span>
              </div>
            </button>
          ))}
          {filteredTools.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6">
              {searchQuery ? 'No tools match your search' : 'No tools in this category'}
            </p>
          )}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col rounded-[24px] border border-border/70 bg-card/70 p-4 shadow-sm">
          {/* Back + tool name */}
          <button
            onClick={() => setSelectedTool(null)}
            className="mb-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            ← Back to list
          </button>
          <h4 className="mb-1 text-base font-semibold">{selectedTool.name}</h4>
          <p className="mb-4 text-[11px] leading-5 text-muted-foreground">{selectedTool.description}</p>

          <div className="mb-4 grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded-lg border border-border/70 bg-background/50 p-2">
              <div className="text-muted-foreground">Requires</div>
              <div className="mt-1 font-mono">{selectedTool.requires?.join(', ') || 'none'}</div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/50 p-2">
              <div className="text-muted-foreground">Provides</div>
              <div className="mt-1 font-mono">{selectedTool.provides?.join(', ') || 'none'}</div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/50 p-2">
              <div className="text-muted-foreground">Evidence</div>
              <div className="mt-1">{selectedTool.evidence_level || 'unverified'}</div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/50 p-2">
              <div className="text-muted-foreground">Runtime / license</div>
              <div className="mt-1">{selectedTool.runtime_mode || (selectedTool.is_async ? 'async_worker' : 'inline_sync')} / {selectedTool.license_status || 'review_required'}</div>
            </div>
          </div>

          {/* Parameter form */}
          <div className="mb-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {Object.entries(selectedTool.parameters.properties || {}).map(([key, schema]) => {
              const isRequired = selectedTool.parameters.required?.includes(key)
              return (
                <div key={key} className="space-y-1">
                  <label className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
                    {label(key)}
                    {isRequired && <span className="text-red-400">*</span>}
                    <span className="text-[9px] opacity-50">({schema.type})</span>
                  </label>
                  {schema.type === 'boolean' ? (
                    <select
                      value={formValues[key] || ''}
                      onChange={(e) => setFormValues((p) => ({ ...p, [key]: e.target.value }))}
                      className="w-full rounded-xl border border-border/80 bg-background/80 px-3 py-2 text-xs outline-none transition focus:border-primary/30 focus:ring-2 focus:ring-primary/10"
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
                      className="w-full rounded-xl border border-border/80 bg-background/80 px-3 py-2 text-xs font-mono outline-none transition focus:border-primary/30 focus:ring-2 focus:ring-primary/10"
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
            className="flex w-full shrink-0 items-center justify-center gap-1.5 rounded-2xl bg-primary py-2.5 text-xs font-medium text-primary-foreground shadow-[0_14px_34px_rgba(37,99,235,0.22)] transition-colors hover:bg-primary/90 disabled:opacity-40"
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
