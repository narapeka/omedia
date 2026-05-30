import type { ComponentProps } from 'react'
import { Button as ShadcnButton } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export function IconButton({
  label,
  className,
  ...props
}: Omit<ComponentProps<typeof ShadcnButton>, 'className' | 'size' | 'variant'> & { label: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <ShadcnButton aria-label={label} className={className} size="icon" variant="outline" {...props} />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
