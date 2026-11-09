import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader2, Maximize2, Minimize2, RotateCcw } from 'lucide-react'

type StyleMode = 'cartoon' | 'stick' | 'sphere' | 'surface' | 'ribbon'

const STYLE_OPTIONS: { mode: StyleMode; label: string }[] = [
  { mode: 'cartoon', label: 'Cartoon' },
  { mode: 'stick', label: 'Stick' },
  { mode: 'sphere', label: 'Sphere' },
  { mode: 'surface', label: 'Surface' },
  { mode: 'ribbon', label: 'Ribbon' },
]

const THREE_DMOL_SCRIPT_ID = 'protein-ai-3dmol-vendor'
const THREE_DMOL_SCRIPT_SRC = '/vendor/3Dmol.js'

let threeDmolLoadPromise: Promise<void> | null = null

function get3DmolGlobal() {
  return (globalThis as unknown as { $3Dmol?: typeof $3Dmol }).$3Dmol
}

function load3DmolScript() {
  if (get3DmolGlobal()) return Promise.resolve()
  if (threeDmolLoadPromise) return threeDmolLoadPromise

  threeDmolLoadPromise = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(THREE_DMOL_SCRIPT_ID) as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('Failed to load 3D viewer')), { once: true })
      return
    }

    const script = document.createElement('script')
    script.id = THREE_DMOL_SCRIPT_ID
    script.src = THREE_DMOL_SCRIPT_SRC
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      threeDmolLoadPromise = null
      reject(new Error('Failed to load 3D viewer'))
    }
    document.head.appendChild(script)
  })

  return threeDmolLoadPromise
}

interface Props {
  pdbData: string
  className?: string
  height?: number
  highlightResidues?: Array<{
    chainId?: string | null
    residueNumber: number
    color?: string
  }>
  highlightRanges?: Array<{
    chainId?: string | null
    startResidue: number
    endResidue: number
    color?: string
  }>
}

export function ProteinViewer({ pdbData, className = '', height = 350, highlightResidues = [], highlightRanges = [] }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<$3Dmol.GLViewer | null>(null)
  const viewerModuleReadyRef = useRef(false)
  const resizeFrameRef = useRef<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<StyleMode>('cartoon')
  const [isFullscreen, setIsFullscreen] = useState(false)

  const hasRenderableSize = useCallback((el: HTMLDivElement | null) => {
    if (!el) return false
    if (!el.isConnected || document.visibilityState === 'hidden') return false
    const rect = el.getBoundingClientRect()
    const style = window.getComputedStyle(el)
    return (
      rect.width >= 24 &&
      rect.height >= 24 &&
      el.getClientRects().length > 0 &&
      style.display !== 'none' &&
      style.visibility !== 'hidden'
    )
  }, [])

  const safeRender = useCallback((viewer: $3Dmol.GLViewer) => {
    const el = containerRef.current
    if (!hasRenderableSize(el)) return false
    try {
      viewer.resize()
      viewer.render()
      return true
    } catch {
      return false
    }
  }, [hasRenderableSize])

  const destroyViewer = useCallback(() => {
    if (viewerRef.current) {
      try { viewerRef.current.clear() } catch { /* ignore */ }
      viewerRef.current = null
    }
  }, [])

  const applyHighlights = useCallback((v: $3Dmol.GLViewer) => {
    const viewerWithAddStyle = v as $3Dmol.GLViewer & {
      addStyle: (selection: Record<string, string | number>, style: Record<string, unknown>) => void
    }

    for (const highlight of highlightRanges) {
      const selection: Record<string, string | number> = {
        resi: `${highlight.startResidue}-${highlight.endResidue}`,
      }
      if (highlight.chainId) {
        selection.chain = highlight.chainId
      }

      viewerWithAddStyle.addStyle(selection, {
        cartoon: {
          color: highlight.color || '#0ea5e9',
          opacity: 0.95,
        },
      })
    }

    for (const highlight of highlightResidues) {
      const selection: Record<string, string | number> = { resi: highlight.residueNumber }
      if (highlight.chainId) {
        selection.chain = highlight.chainId
      }

      viewerWithAddStyle.addStyle(selection, {
        stick: {
          color: highlight.color || '#ef4444',
          radius: 0.28,
        },
        sphere: {
          color: highlight.color || '#ef4444',
          scale: 0.38,
        },
      })
    }
  }, [highlightRanges, highlightResidues])

  const applyStyle = useCallback((v: $3Dmol.GLViewer, styleMode: StyleMode) => {
    v.clear()
    v.addModel(pdbData, 'pdb')

    switch (styleMode) {
      case 'cartoon':
        v.setStyle({}, { cartoon: { color: 'spectrum' } })
        break
      case 'stick':
        v.setStyle({}, { stick: { color: 'spectrum', radius: 0.15 } })
        break
      case 'sphere':
        v.setStyle({}, { sphere: { color: 'spectrum', scale: 0.3 } })
        break
      case 'surface':
        v.setStyle({}, { cartoon: { color: 'spectrum', opacity: 0.5 } })
        v.addSurface($3Dmol.SurfaceType.VDW, { color: 'spectrum', opacity: 0.7 })
        break
      case 'ribbon':
        v.setStyle({}, { cartoon: { style: 'ribbon', color: 'spectrum' } })
        break
    }
    applyHighlights(v)
    v.zoomTo()
  }, [applyHighlights, pdbData])

  const initializeViewer = useCallback((styleMode: StyleMode) => {
    const el = containerRef.current
    if (!viewerModuleReadyRef.current || !hasRenderableSize(el) || !el) {
      return false
    }

    try {
      destroyViewer()
      const viewer = $3Dmol.createViewer(el, {
        backgroundColor: '0xf8fafc',
        antialias: true,
      })
      viewerRef.current = viewer
      applyStyle(viewer, styleMode)
      if (!safeRender(viewer)) {
        destroyViewer()
        return false
      }
      setLoading(false)
      setError(null)
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to render structure')
      setLoading(false)
      return false
    }
  }, [applyStyle, destroyViewer, hasRenderableSize, safeRender])

  useEffect(() => {
    if (!containerRef.current || !pdbData) return

    let disposed = false
    setLoading(true)
    setError(null)
    destroyViewer()

    load3DmolScript().then(() => {
      if (disposed) return
      viewerModuleReadyRef.current = true
      initializeViewer(mode)
    }).catch(() => {
      if (!disposed) {
        setError('Failed to load 3D viewer')
        setLoading(false)
      }
    })

    return () => {
      disposed = true
      destroyViewer()
    }
  }, [destroyViewer, initializeViewer, mode, pdbData])

  // Handle style mode changes
  useEffect(() => {
    if (viewerRef.current && !loading) {
      applyStyle(viewerRef.current, mode)
      if (!safeRender(viewerRef.current)) {
        destroyViewer()
        setLoading(true)
      }
      return
    }

    if (viewerModuleReadyRef.current && !viewerRef.current) {
      initializeViewer(mode)
    }
  }, [applyStyle, destroyViewer, initializeViewer, loading, mode, safeRender])

  // Handle resize
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      if (resizeFrameRef.current !== null) {
        cancelAnimationFrame(resizeFrameRef.current)
      }
      resizeFrameRef.current = requestAnimationFrame(() => {
        resizeFrameRef.current = null
        if (!hasRenderableSize(el)) {
          destroyViewer()
          setLoading(true)
          return
        }
        if (viewerRef.current) {
          if (!safeRender(viewerRef.current)) {
            destroyViewer()
            setLoading(true)
          }
          return
        }
        if (viewerModuleReadyRef.current && pdbData) {
          initializeViewer(mode)
        }
      })
    })
    ro.observe(el)
    return () => {
      ro.disconnect()
      if (resizeFrameRef.current !== null) {
        cancelAnimationFrame(resizeFrameRef.current)
        resizeFrameRef.current = null
      }
    }
  }, [destroyViewer, hasRenderableSize, initializeViewer, mode, pdbData, safeRender])

  const handleReset = () => {
    if (viewerRef.current) {
      applyStyle(viewerRef.current, mode)
    }
  }

  const syncFullscreenState = useCallback(() => {
    const fullscreenElement = document.fullscreenElement
    setIsFullscreen(Boolean(rootRef.current && fullscreenElement === rootRef.current))
  }, [])

  useEffect(() => {
    const handleFullscreenChange = () => {
      syncFullscreenState()
      requestAnimationFrame(() => {
        if (viewerRef.current) {
          safeRender(viewerRef.current)
        } else if (viewerModuleReadyRef.current && pdbData) {
          initializeViewer(mode)
        }
      })
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [initializeViewer, mode, pdbData, safeRender, syncFullscreenState])

  const toggleFullscreen = useCallback(async () => {
    const root = rootRef.current
    if (!root) return

    try {
      if (document.fullscreenElement === root) {
        await document.exitFullscreen()
        return
      }

      if (!document.fullscreenElement) {
        await root.requestFullscreen()
      }
    } catch {
      setError('Failed to toggle fullscreen view')
    }
  }, [])

  if (error) {
    return (
      <div className={`bg-red-500/5 border border-red-500/20 rounded-lg p-6 text-center ${className}`}>
        <p className="text-sm text-red-400">{error}</p>
      </div>
    )
  }

  return (
    <div
      ref={rootRef}
      className={`border border-border rounded-xl overflow-hidden bg-card ${isFullscreen ? 'h-screen w-screen rounded-none border-0' : ''} ${className}`}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 bg-secondary/50 border-b border-border">
        <div className="flex items-center gap-0.5">
          {STYLE_OPTIONS.map((opt) => (
            <button
              key={opt.mode}
              onClick={() => setMode(opt.mode)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                mode === opt.mode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <button
          onClick={handleReset}
          className="p-1 rounded hover:bg-secondary text-muted-foreground"
          title="Reset view"
        >
          <RotateCcw className="w-3 h-3" />
        </button>
        <button
          onClick={() => { void toggleFullscreen() }}
          className="p-1 rounded hover:bg-secondary text-muted-foreground"
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          {isFullscreen ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
        </button>
      </div>

      {/* Canvas */}
      <div className="relative" style={{ height: isFullscreen ? 'calc(100vh - 45px)' : height }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}
        <div
          ref={containerRef}
          className="w-full h-full relative"
          style={{ minHeight: height }}
        />
      </div>
    </div>
  )
}
