import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { getAccessToken, getRefreshToken } from '@/lib/api'
import { BrandLogo } from '@/components/BrandLogo'
import {
  ArrowRight,
  Database,
  Eye,
  EyeOff,
  FlaskConical,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  User,
} from 'lucide-react'

/** Default post-login destination when no ?next= param is present */
const DEFAULT_REDIRECT = '/home'

/**
 * Safely resolve the post-login redirect target.
 * - Only relative paths (starting with "/" but not "//") are allowed.
 * - Absolute URLs, protocol-relative URLs, and javascript: URIs are rejected
 *   to prevent Open Redirect attacks.
 */
function safeNextUrl(param: string | null): string {
  if (!param) return DEFAULT_REDIRECT
  const normalized = param.trim()
  if (!normalized) return DEFAULT_REDIRECT
  // Reject absolute URLs, protocol-relative URLs, and anything suspicious
  if (
    normalized.startsWith('//') ||
    normalized.includes('://') ||
    normalized.toLowerCase().startsWith('javascript:')
  ) {
    return DEFAULT_REDIRECT
  }
  if (normalized.startsWith('/')) return normalized
  return DEFAULT_REDIRECT
}

export function AuthPage() {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const { login, isLoading, error, clearError, token, user } =
    useAuthStore()

  const nextUrl = safeNextUrl(searchParams.get('next'))

  useEffect(() => {
    const authState = useAuthStore.getState()
    const hasLocalCredentials =
      Boolean(authState.token || authState.refreshToken || getAccessToken() || getRefreshToken())
    const shouldRestoreForOidc = nextUrl.startsWith('/api/')

    if (!authState.initialized && !authState.isLoading && (hasLocalCredentials || shouldRestoreForOidc)) {
      void authState.checkAuth()
    }
  }, [nextUrl])

  useEffect(() => {
    if (!(token && user)) return
    if (!nextUrl.startsWith('/api/')) return
    window.location.assign(nextUrl)
  }, [nextUrl, token, user])

  // Already authenticated — redirect to the target page
  if (token && user) {
    // OIDC authorize endpoint (/api/...) requires a full page navigation.
    if (nextUrl.startsWith('/api/')) return null
    return <Navigate to={nextUrl} replace />
  }

  const validate = (): boolean => {
    if (!email.trim()) {
      setValidationError('Username is required')
      return false
    }
    if (!password) {
      setValidationError('Password is required')
      return false
    }
    setValidationError(null)
    return true
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()
    if (!validate()) return

    try {
      await login(email, password)
      // Navigate handled by the redirect guard above once state updates
    } catch {
      // Error is set in the store, displayed below
    }
  }

  const displayError = validationError || error

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto grid min-h-screen w-full max-w-6xl grid-cols-1 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative flex min-h-[34vh] flex-col overflow-hidden border-b border-border px-6 py-8 sm:px-10 lg:min-h-screen lg:border-b-0 lg:px-12 lg:py-12">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-rose-500/5" />
          <div className="relative flex flex-1 flex-col justify-start pt-10 pb-6 lg:pt-14 lg:pb-8">
            <BrandLogo
              size="md"
              showSubtitle
              subtitle="Enzyme engineering workspace"
            />

            <div className="mt-16 max-w-xl lg:mt-20">
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs font-medium text-foreground shadow-sm">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                Production research environment
              </div>
              <h1 className="max-w-lg text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
                Secure access for structure-aware enzyme design.
              </h1>
              <p className="mt-6 max-w-xl text-sm leading-6 text-muted-foreground">
                Continue protein sequence analysis, uploaded structure review,
                molecular dynamics tasks, and evidence-backed mutation workflows.
              </p>

              <div className="mt-12 grid max-w-xl grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-3 text-blue-500 transition-colors">
                  <Database className="mb-3 h-4 w-4" />
                  <div className="text-sm font-semibold text-foreground">Data</div>
                  <div className="mt-1 text-xs text-muted-foreground">Live assets</div>
                </div>
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-emerald-500 transition-colors">
                  <FlaskConical className="mb-3 h-4 w-4" />
                  <div className="text-sm font-semibold text-foreground">Design</div>
                  <div className="mt-1 text-xs text-muted-foreground">Wet-lab gates</div>
                </div>
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/10 p-3 text-purple-500 transition-colors">
                  <LockKeyhole className="mb-3 h-4 w-4" />
                  <div className="text-sm font-semibold text-foreground">Access</div>
                  <div className="mt-1 text-xs text-muted-foreground">Project ACL</div>
                </div>
              </div>
            </div>
          </div>

          <div className="relative hidden pt-8 text-xs text-muted-foreground lg:block">
            Verified workflows for files, structures, tasks, and research records.
          </div>
        </section>

        <section className="flex items-center justify-center bg-background px-5 py-8 sm:px-8 lg:border-l lg:border-border">
          <div className="w-full max-w-md">
            <div className="mb-6">
              <div className="text-xs font-semibold uppercase tracking-normal text-primary">
                Welcome back
              </div>
              <h2 className="mt-2 text-2xl font-bold tracking-tight">
                Sign in to continue
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Use your platform username and password.
              </p>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6 shadow-lg shadow-primary/10">
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email */}
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-foreground">
                    Username
                  </label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                      type="text"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter username"
                      className="w-full rounded-xl border border-border bg-background px-10 py-2.5 text-sm transition-colors focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/15"
                      autoComplete="username"
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-foreground">
                    Password
                  </label>
                  <div className="relative">
                    <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter password"
                      className="w-full rounded-xl border border-border bg-background py-2.5 pl-10 pr-10 text-sm transition-colors focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/15"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      tabIndex={-1}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Error Message */}
                {displayError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-500 dark:border-red-800 dark:bg-red-950/30">
                    {displayError}
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                  Sign In
                  {!isLoading && <ArrowRight className="h-4 w-4" />}
                </button>
              </form>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
