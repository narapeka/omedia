import type { HTMLAttributes, ReactNode } from 'react'
import { Badge as ShadcnBadge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export type BadgeTone = 'success' | 'warning' | 'danger'
export type BadgeColor = 'amber' | 'blue' | 'cyan' | 'emerald' | 'lime' | 'pink' | 'purple' | 'red' | 'sky' | 'stone' | 'violet'

const badgeColorClass: Record<BadgeColor, string> = {
  amber: 'border-amber-400/30 bg-amber-950/35 text-amber-700 dark:text-amber-200',
  blue: 'border-blue-400/30 bg-blue-950/35 text-blue-700 dark:text-blue-200',
  cyan: 'border-cyan-400/30 bg-cyan-950/35 text-cyan-700 dark:text-cyan-200',
  emerald: 'border-emerald-400/30 bg-emerald-950/35 text-emerald-700 dark:text-emerald-200',
  lime: 'border-lime-400/30 bg-lime-950/30 text-lime-700 dark:text-lime-200',
  pink: 'border-pink-400/30 bg-pink-950/35 text-pink-700 dark:text-pink-200',
  purple: 'border-purple-400/30 bg-purple-950/35 text-purple-700 dark:text-purple-200',
  red: 'border-red-400/30 bg-red-950/35 text-red-700 dark:text-red-200',
  sky: 'border-sky-400/30 bg-sky-950/35 text-sky-700 dark:text-sky-200',
  stone: 'border-stone-400/30 bg-stone-900/50 text-stone-700 dark:text-stone-200',
  violet: 'border-violet-400/30 bg-violet-950/35 text-violet-700 dark:text-violet-200',
}

export function Badge({
  color,
  tone,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { color?: BadgeColor; tone?: BadgeTone; children: ReactNode }) {
  return (
    <ShadcnBadge
      className={cn(color ? badgeColorClass[color] : undefined, className)}
      data-tone={tone}
      variant={tone === 'danger' ? 'destructive' : tone === 'success' ? 'default' : tone === 'warning' ? 'secondary' : 'outline'}
      {...props}
    >
      {children}
    </ShadcnBadge>
  )
}

export function badgeColorForTone(tone: BadgeTone | undefined): BadgeColor | undefined {
  if (tone === 'success') return 'emerald'
  if (tone === 'warning') return 'amber'
  if (tone === 'danger') return 'red'
  return undefined
}

export function badgeColorForStatus(status: string | null | undefined, tone?: BadgeTone): BadgeColor | undefined {
  const normalized = status?.toLowerCase()
  if (normalized === 'failed' || normalized === 'error') return 'red'
  if (normalized === 'succeeded' || normalized === 'success' || normalized === 'completed' || normalized === 'done') return 'emerald'
  if (normalized === 'queued' || normalized === 'started' || normalized === 'running' || normalized === 'cancelling' || normalized === 'processing') return 'sky'
  if (normalized === 'skipped' || normalized === 'cancelled' || normalized === 'warning') return 'amber'
  return badgeColorForTone(tone)
}

export function badgeColorForMediaType(mediaType: string | null | undefined): BadgeColor | undefined {
  if (mediaType === 'movie') return 'blue'
  if (mediaType === 'tv') return 'violet'
  return undefined
}
