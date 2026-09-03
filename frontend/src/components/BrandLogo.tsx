type BrandLogoProps = {
  className?: string
  imageClassName?: string
  size?: 'sm' | 'md' | 'lg'
  subtitle?: string
  showSubtitle?: boolean
}

const sizeClass: Record<NonNullable<BrandLogoProps['size']>, string> = {
  sm: 'h-9 w-auto',
  md: 'h-12 w-auto',
  lg: 'h-16 sm:h-20 w-auto',
}

export function BrandLogo({
  className = '',
  imageClassName = '',
  size = 'md',
  subtitle,
  showSubtitle = false,
}: BrandLogoProps) {
  return (
    <div className={`flex min-w-0 items-center gap-3 ${className}`}>
      <img
        src="/brand/kwb-logo.png?v=20260827"
        alt="科为博 CRVAB"
        className={`shrink-0 object-contain ${sizeClass[size]} ${imageClassName}`}
      />
      {showSubtitle && subtitle && (
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-normal text-foreground">
            Protein AI Platform
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {subtitle}
          </div>
        </div>
      )}
    </div>
  )
}
