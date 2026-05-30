import { Link } from '@tanstack/react-router'
import { Badge } from '@/components/common/Badge'
import { useI18n } from '@/app/providers/I18nProvider'
import { cn } from '@/lib/utils'

export function ConfigMetric({
  badge,
  className,
  label,
  value,
  to,
  hash,
}: {
  badge?: { label: string; className?: string }
  className?: string
  label: string
  value: number
  to: '/settings' | '/services'
  hash: string
}) {
  const { t } = useI18n()
  return (
    <Link
      aria-label={t('openLabel', { label })}
      className={cn(
        'relative rounded-lg border bg-card px-2.5 py-2.5 transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-4 sm:py-3',
        badge ? 'pr-16 sm:pr-32' : '',
        className,
      )}
      hash={hash}
      to={to}
    >
      <div className="min-w-0">
        <div className="truncate text-[0.68rem] font-medium leading-4 text-muted-foreground sm:text-[0.8rem] sm:leading-5">{label}</div>
        <div className="mt-1 text-[1.3rem] font-bold leading-none sm:text-[1.5rem]">{value}</div>
      </div>
      {badge ? (
        <Badge className={`absolute top-1/2 right-2.5 h-[1.25rem] -translate-y-1/2 px-2 text-xs font-normal leading-none whitespace-nowrap sm:right-6 sm:h-[1.375rem] sm:px-2.5 sm:text-sm ${badge.className ?? ''}`}>
          {badge.label}
        </Badge>
      ) : null}
    </Link>
  )
}
