import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, type BadgeTone } from '@/components/common/Badge'
import { cn } from '@/lib/utils'

export type OverviewStat = {
  label: string
  value: string | number
  tone?: BadgeTone
  to?: '/activity' | '/organize' | '/services' | '/transfer'
  hash?: string
  search?: Record<string, string>
  ariaLabel?: string
}

export function OverviewStats({ stats, className }: { stats: OverviewStat[]; className?: string }) {
  const { t } = useI18n()
  return (
    <div className={cn('grid grid-cols-2 gap-2 sm:grid-cols-4', className)}>
      {stats.map((stat) => {
        const content = (
          <>
            <div className="truncate text-xs text-muted-foreground">{stat.label}</div>
            <div className="mt-1">
              <Badge className="h-6 px-2.5 text-[1.1rem] font-semibold leading-none" tone={stat.tone}>{stat.value}</Badge>
            </div>
          </>
        )
        const itemClassName = stat.to
          ? 'min-w-0 rounded-md bg-muted/30 px-2.5 py-2 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
          : 'min-w-0 rounded-md bg-muted/30 px-2.5 py-2'
        return stat.to ? (
          <Link
            key={stat.label}
            aria-label={stat.ariaLabel ?? t('openLabel', { label: stat.label })}
            className={itemClassName}
            hash={stat.hash}
            search={stat.search as never}
            to={stat.to}
          >
            {content}
          </Link>
        ) : (
          <div key={stat.label} className={itemClassName}>
            {content}
          </div>
        )
      })}
    </div>
  )
}

export function NamePath({ name, path, suffix }: { name: string; path: string; suffix?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate font-medium" title={name}>{name}</span>
        {suffix}
      </div>
      <div className="truncate text-xs text-muted-foreground" title={path}>{path}</div>
    </div>
  )
}

export function OverviewDetailLine({
  label,
  title,
  value,
  className,
  valueClassName,
}: {
  label: string
  title?: string
  value: ReactNode
  className?: string
  valueClassName?: string
}) {
  return (
    <div className={cn('grid min-w-0 grid-cols-[3.5rem_minmax(0,1fr)] items-baseline gap-2 text-sm', className)}>
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('min-w-0 truncate font-medium text-muted-foreground', valueClassName)} title={title}>
        {value}
      </span>
    </div>
  )
}
