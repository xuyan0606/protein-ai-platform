import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader2, Maximize2, RotateCcw } from 'lucide-react'

type StyleMode = 'cartoon' | 'stick' | 'sphere' | 'surface' | 'ribbon'

const STYLE_OPTIONS: { mode: StyleMode; label: string }[] = [
  { mode: 'cartoon', label: 'Cartoon' },
  { mode: 'stick', label: 'Stick' },
  { mode: 'sphere', label: 'Sphere' },
  { mode: 'surface', label: 'Surface' },
  { mode: 'ribbon', label: 'Ribbon' },
]

interface Props {
  pdbData: string
  className?: string
  height?: number
}

export function ProteinViewer({ pdbData, className = '', height = 350 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<$3Dmol.GLViewer | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<StyleMode>('cartoon')

  const applyStyle = useCallback((v: $3Dmol.GLViewer, styleMode: StyleMode) => {
    v.removeAllModels()
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
    v.zoomTo()
    v.render()
  }, [pdbData])

  useEffect(() => {
    if (!containerRef.current || !pdbData) return

    let disposed = false
    setLoading(true)
    setError(null)

    // Load 3Dmol dynamically
    import('3dmol/build/3Dmol.js').then(() => {
      if (disposed || !containerRef.current) return

      try {
        // Destroy previous viewer
        if (viewerRef.current) {
          try { viewerRef.current.clear() } catch { /* ignore */ }
        }

        const viewer = $3Dmol.createViewer(containerRef.current!, {
          backgroundColor: '0xf8fafc',
          antialias: true,
        })
        viewerRef.current = viewer

        applyStyle(viewer, mode)
        setLoading(false)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to render structure')
        setLoading(false)
      }
    }).catch(() => {
      if (!disposed) {
        setError('Failed to load 3D viewer')
        setLoading(false)
      }
    })

    return () => {
      disposed = true
      if (viewerRef.current) {
        try { viewerRef.current.clear() } catch { /* ignore */ }
        viewerRef.current = null
      }
    }
  }, [pdbData]) // eslint-disable-line react-hooks/exhaustive-deps

  // Handle style mode changes
  useEffect(() => {
    if (viewerRef.current && !loading) {
      applyStyle(viewerRef.current, mode)
    }
  }, [mode, loading]) // eslint-disable-line react-hooks/exhaustive-deps

  // Handle resize
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      if (viewerRef.current) {
        viewerRef.current.resize()
        viewerRef.current.render()
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const handleReset = () => {
    if (viewerRef.current) {
      applyStyle(viewerRef.current, mode)
    }
  }

  if (error) {
    return (
      <div className={`bg-red-500/5 border border-red-500/20 rounded-lg p-6 text-center ${className}`}>
        <p className="text-sm text-red-400">{error}</p>
      </div>
    )
  }

  return (
    <div className={`border border-border rounded-xl overflow-hidden bg-card ${className}`}>
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
          onClick={() => {
            if (viewerRef.current) {
              viewerRef.current.zoomTo()
              viewerRef.current.render()
            }
          }}
          className="p-1 rounded hover:bg-secondary text-muted-foreground"
          title="Fit to view"
        >
          <Maximize2 className="w-3 h-3" />
        </button>
      </div>

      {/* Canvas */}
      <div className="relative" style={{ height }}>
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
