import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react'

const OUTLINE_URL = 'http://localhost:8000/'
const LOAD_DELAY = 2000 // Cover final render after OIDC redirect chain settles

export function WikiPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const loadTimer = useRef<ReturnType<typeof setTimeout>>()

  const handleLoad = () => {
    // The iframe fires onLoad for each redirect during OIDC flow.
    // Clear any existing timer and set a new one — the final onLoad
    // will be the one that sticks after the redirect chain settles.
    if (loadTimer.current) clearTimeout(loadTimer.current)
    loadTimer.current = setTimeout(() => setLoading(false), LOAD_DELAY)
  }

  const handleRetry = () => {
    setError(false)
    setLoading(true)
    if (iframeRef.current) {
      iframeRef.current.src = OUTLINE_URL
    }
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Toolbar */}
      <header className="h-12 border-b border-border flex items-center px-3 gap-3 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground"
          aria-label="Go back"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="font-semibold text-sm">Knowledge Base</span>
        <div className="flex-1" />
        {loading && (
          <span className="text-xs text-muted-foreground animate-pulse">
            Loading...
          </span>
        )}
        {error && (
          <button
            onClick={handleRetry}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-amber-500 hover:bg-secondary"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
        <a
          href={OUTLINE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-muted-foreground hover:bg-secondary"
        >
          <ExternalLink className="w-3 h-3" />
          Open in new tab
        </a>
      </header>

      {/* Iframe */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <span className="text-sm text-muted-foreground">
                Loading knowledge base...
              </span>
            </div>
          </div>
        )}
        <iframe
          ref={iframeRef}
          src={OUTLINE_URL}
          className="w-full h-full border-0"
          title="Knowledge Base"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
          onLoad={handleLoad}
          onError={() => { setLoading(false); setError(true) }}
        />
      </div>
    </div>
  )
}