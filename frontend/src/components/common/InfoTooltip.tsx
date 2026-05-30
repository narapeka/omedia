import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export function InfoTooltip({
  label,
  children,
  contentClassName,
}: {
  label: string
  children?: ReactNode
  contentClassName?: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          aria-label={label}
          className="inline-flex cursor-help items-center text-muted-foreground"
          role="img"
          tabIndex={0}
        >
          <Info className="size-3.5" />
        </span>
      </TooltipTrigger>
      <TooltipContent className={cn('w-80 max-w-80 whitespace-normal text-left text-xs leading-normal', contentClassName)}>
        {children ?? label}
      </TooltipContent>
    </Tooltip>
  )
}
