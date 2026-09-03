import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react'

const PLATFORM_WIKI_ROUTE = '/wiki'
const AGENT_WORKSPACE_ROUTE = '/chat/agent'
const EMBEDDED_WIKI_ROUTE = '/'
const OUTLINE_OIDC_ENTRY_ROUTE = '/auth/oidc'

function normalizeOutlineUrl(url?: string) {
  if (!url) return EMBEDDED_WIKI_ROUTE

  const trimmed = url.trim()
  if (!trimmed) return EMBEDDED_WIKI_ROUTE

  const [pathWithQuery = '', hash = ''] = trimmed.split('#', 2)
  const [path = '', query = ''] = pathWithQuery.split('?', 2)
  const normalizedPath =
    path === PLATFORM_WIKI_ROUTE ? EMBEDDED_WIKI_ROUTE : path

  return `${normalizedPath}${query ? `?${query}` : ''}${hash ? `#${hash}` : ''}`
}

function resolveInitialOutlineUrl(url?: string) {
  const normalized = normalizeOutlineUrl(url)

  // Always re-enter OIDC when the configured entrypoint is the wiki root.
  // This refreshes stale Outline sessions that can otherwise leave the iframe
  // stuck in a broken authenticated-but-expired state.
  if (
    normalized === EMBEDDED_WIKI_ROUTE ||
    normalized === PLATFORM_WIKI_ROUTE
  ) {
    return OUTLINE_OIDC_ENTRY_ROUTE
  }

  return normalized
}

const OUTLINE_URL = resolveInitialOutlineUrl(import.meta.env.VITE_OUTLINE_URL)
const OUTLINE_FALLBACK_URL = OUTLINE_OIDC_ENTRY_ROUTE
const LOAD_DELAY = 2000 // Cover final render after OIDC redirect chain settles
const NOT_FOUND_POLL_INTERVAL = 1000
const OIDC_TRANSIENT_PREFIXES = [
  '/auth/oidc',
  '/wiki/auth/oidc',
  '/api/oidc/authorize',
  '/wiki/auth/oidc.callback',
]
const STABLE_WIKI_PREFIXES = [
  PLATFORM_WIKI_ROUTE,
  '/collection/',
  '/doc/',
  '/search',
  '/home',
]

function hasPrefix(pathname: string, prefixes: string[]) {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(prefix))
}

function hasNotFoundContent(text: string) {
  const normalized = text.trim().toLowerCase()
  if (!normalized) return false
  return normalized.includes('not found') || normalized.includes('document not found')
}

export function WikiPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const loadTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const notFoundPollTimer = useRef<ReturnType<typeof setInterval>>(undefined)
  const consecutiveNotFoundLoads = useRef(0)
  const didSearchFallback = useRef(false)

  const resolveFallbackUrl = useCallback(async () => {
    try {
      const response = await fetch('/api/documents.list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ limit: 1 }),
      })
      if (!response.ok) return OUTLINE_FALLBACK_URL
      const payload = await response.json()
      const docUrl = payload?.data?.[0]?.url
      if (typeof docUrl === 'string' && docUrl.startsWith('/doc/')) {
        return docUrl
      }
    } catch {
      // Fall back to the wiki root when Outline API cookies are not ready yet.
    }
    return OUTLINE_FALLBACK_URL
  }, [])

  const redirectToFallback = useCallback(async () => {
    const iframe = iframeRef.current
    if (!iframe || didSearchFallback.current) return
    didSearchFallback.current = true
    consecutiveNotFoundLoads.current = 0
    iframe.src = await resolveFallbackUrl()
  }, [resolveFallbackUrl])

  useEffect(() => {
    notFoundPollTimer.current = setInterval(() => {
      const iframe = iframeRef.current
      if (!iframe || didSearchFallback.current) return

      try {
        const framePath = iframe.contentWindow?.location.pathname
        const frameText = iframe.contentDocument?.body?.textContent ?? ''
        if (
          framePath &&
          framePath !== OUTLINE_FALLBACK_URL &&
          !hasPrefix(framePath, OIDC_TRANSIENT_PREFIXES) &&
          hasNotFoundContent(frameText)
        ) {
          void redirectToFallback()
        }
      } catch {
        // Ignore cross-document inspection failures during redirect hops.
      }
    }, NOT_FOUND_POLL_INTERVAL)

    return () => {
      if (loadTimer.current) clearTimeout(loadTimer.current)
      if (notFoundPollTimer.current) clearInterval(notFoundPollTimer.current)
    }
  }, [redirectToFallback])

  const showWikiError = () => {
    if (loadTimer.current) clearTimeout(loadTimer.current)
    setError(true)
    setLoading(false)
  }

  const handleLoad = () => {
    const iframe = iframeRef.current

    if (iframe) {
      try {
        const framePath = iframe.contentWindow?.location.pathname
        const frameText = iframe.contentDocument?.body?.textContent ?? ''
        const isNotFound = hasNotFoundContent(frameText)

        // Exact `/wiki` belongs to the platform SPA, not embedded Outline.
        // If the iframe ever lands there, correct it immediately to avoid
        // recursively loading the same page inside itself.
        if (framePath === PLATFORM_WIKI_ROUTE) {
          iframe.src = OUTLINE_URL
          return
        }

        if (framePath && hasPrefix(framePath, OIDC_TRANSIENT_PREFIXES)) {
          consecutiveNotFoundLoads.current = 0
          return
        }

        if (framePath && hasPrefix(framePath, STABLE_WIKI_PREFIXES) && !isNotFound) {
          consecutiveNotFoundLoads.current = 0
        }

        if (isNotFound) {
          consecutiveNotFoundLoads.current += 1
        }

        if (
          isNotFound &&
          framePath &&
          framePath !== OUTLINE_FALLBACK_URL &&
          !hasPrefix(framePath, OIDC_TRANSIENT_PREFIXES) &&
          !didSearchFallback.current
        ) {
          void redirectToFallback()
          return
        }

        if (
          isNotFound &&
          framePath &&
          !hasPrefix(framePath, OIDC_TRANSIENT_PREFIXES) &&
          consecutiveNotFoundLoads.current >= 2
        ) {
          setError(true)
          setLoading(false)
          return
        }
      } catch {
        // Ignore cross-document inspection failures during redirect hops.
      }
    }

    // The iframe fires onLoad for each redirect during OIDC flow.
    // Clear any existing timer and set a new one — the final onLoad
    // will be the one that sticks after the redirect chain settles.
    if (loadTimer.current) clearTimeout(loadTimer.current)
    loadTimer.current = setTimeout(() => setLoading(false), LOAD_DELAY)
  }

  const handleRetry = () => {
    setError(false)
    setLoading(true)
    consecutiveNotFoundLoads.current = 0
    didSearchFallback.current = false
    void redirectToFallback()
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
        <button
          onClick={() => navigate(AGENT_WORKSPACE_ROUTE)}
          className="px-2 py-1 rounded-md text-xs text-muted-foreground hover:bg-secondary"
        >
          Back to Agent
        </button>
        <div className="flex-1" />
        {loading && (
          <span className="text-xs text-muted-foreground animate-pulse">
            Loading...
          </span>
        )}
        {error && (
          <>
            <button
              onClick={handleRetry}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-amber-500 hover:bg-secondary"
            >
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
            <button
              onClick={() => navigate('/home')}
              className="px-2 py-1 rounded-md text-xs text-muted-foreground hover:bg-secondary"
            >
              Back to Home
            </button>
          </>
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
          onLoad={handleLoad}
          onError={showWikiError}
        />
      </div>
    </div>
  )
}
