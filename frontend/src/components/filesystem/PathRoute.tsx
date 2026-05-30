import type { HTMLAttributes } from 'react'
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export function PathArrow({ className }: { className?: string }) {
  return <ArrowRight aria-hidden="true" className={cn('size-3.5 shrink-0 text-muted-foreground', className)} />
}

export function PathRoute({
  source,
  target,
  className,
  iconClassName,
  pathClassName,
  truncate = false,
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  source: string
  target: string
  iconClassName?: string
  pathClassName?: string
  truncate?: boolean
}) {
  return (
    <span
      className={cn(
        'inline-flex min-w-0 max-w-full items-center gap-x-2 gap-y-1',
        truncate ? 'flex-nowrap' : 'flex-wrap',
        className,
      )}
      title={`${source} -> ${target}`}
      {...props}
    >
      <span className={cn(truncate ? 'min-w-0 truncate' : 'min-w-0 break-all', pathClassName)}>{source}</span>
      <PathArrow className={iconClassName} />
      <span className={cn(truncate ? 'min-w-0 truncate' : 'min-w-0 break-all', pathClassName)}>{target}</span>
    </span>
  )
}
