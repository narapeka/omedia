import type { ComponentProps } from 'react'
import { Button as ShadcnButton } from '@/components/ui/button'

type AppButtonVariant = 'primary' | 'danger' | 'default' | 'outline' | 'secondary' | 'ghost' | 'link' | 'destructive'

export function Button({
  variant,
  className,
  ...props
}: Omit<ComponentProps<typeof ShadcnButton>, 'variant' | 'className'> & {
  variant?: AppButtonVariant
  className?: string
}) {
  return (
    <ShadcnButton
      className={className}
      variant={variant === 'danger' ? 'destructive' : variant === 'primary' ? 'default' : variant ?? 'outline'}
      {...props}
    />
  )
}
