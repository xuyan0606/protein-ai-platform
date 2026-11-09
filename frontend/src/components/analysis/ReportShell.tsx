import type { ComponentType, ReactNode } from 'react'

type IconType = ComponentType<{ className?: string }>

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

const TONE_STYLES = {
  neutral: 'border-border/70 bg-secondary/25 text-foreground',
  info: 'border-blue-500/15 bg-blue-500/6 text-foreground',
  success: 'border-emerald-500/15 bg-emerald-500/6 text-foreground',
  warning: 'border-amber-500/20 bg-amber-500/7 text-foreground',
  danger: 'border-red-500/15 bg-red-500/6 text-foreground',
}

const BADGE_TONE_STYLES = {
  neutral: 'border-border/70 bg-secondary/55 text-muted-foreground',
  info: 'border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  warning: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  danger: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
}

export function ReportShell({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={cx(
        'overflow-hidden rounded-[28px] border border-border/70 bg-card/95 shadow-[0_20px_60px_rgba(15,23,42,0.06)]',
        className
      )}
    >
      {children}
    </section>
  )
}

export function ReportHeader({
  icon: Icon,
  title,
  subtitle,
  actions,
  badge,
}: {
  icon?: IconType
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  badge?: ReactNode
}) {
  return (
    <div className="border-b border-border/70 bg-[linear-gradient(180deg,rgba(37,99,235,0.05),transparent)] px-5 py-4 sm:px-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {Icon ? (
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary">
                <Icon className="h-4 w-4" />
              </span>
            ) : null}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="truncate text-[1rem] font-semibold tracking-[0.01em] text-foreground">
                  {title}
                </h3>
                {badge}
              </div>
              {subtitle ? (
                <p className="mt-1 text-[12px] leading-6 text-muted-foreground">{subtitle}</p>
              ) : null}
            </div>
          </div>
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
    </div>
  )
}

export function ReportBody({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cx('space-y-5 px-5 py-5 sm:px-6', className)}>{children}</div>
}

export function ReportSection({
  title,
  icon: Icon,
  action,
  children,
  className,
}: {
  title: ReactNode
  icon?: IconType
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cx('space-y-3', className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {Icon ? <Icon className="h-3.5 w-3.5 text-primary" /> : null}
          <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {title}
          </h4>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function ReportMetricGrid({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cx('grid grid-cols-2 gap-3 sm:grid-cols-4', className)}>{children}</div>
}

export function ReportMetricCard({
  label,
  value,
  meta,
  tone = 'neutral',
  mono = false,
  className,
}: {
  label: ReactNode
  value: ReactNode
  meta?: ReactNode
  tone?: keyof typeof TONE_STYLES
  mono?: boolean
  className?: string
}) {
  return (
    <div className={cx('rounded-2xl border px-3.5 py-3', TONE_STYLES[tone], className)}>
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className={cx('mt-2 text-[1rem] font-semibold leading-none text-foreground', mono && 'font-mono')}>
        {value}
      </div>
      {meta ? <div className="mt-2 text-[11px] leading-5 text-muted-foreground">{meta}</div> : null}
    </div>
  )
}

export function ReportPanel({
  children,
  className,
  tone = 'neutral',
}: {
  children: ReactNode
  className?: string
  tone?: keyof typeof TONE_STYLES
}) {
  return (
    <div className={cx('rounded-2xl border px-4 py-3.5', TONE_STYLES[tone], className)}>
      {children}
    </div>
  )
}

export function ReportBadge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode
  tone?: keyof typeof TONE_STYLES
  className?: string
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-medium',
        BADGE_TONE_STYLES[tone],
        className
      )}
    >
      {children}
    </span>
  )
}

export function ReportDataTable({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cx('overflow-x-auto rounded-2xl border border-border/70 bg-secondary/15', className)}>
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  )
}
