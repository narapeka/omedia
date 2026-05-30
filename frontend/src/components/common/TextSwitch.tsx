import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type TextSwitchProps = {
  checked: boolean
  checkedLabel: ReactNode
  uncheckedLabel: ReactNode
  ariaChecked?: boolean | 'mixed'
  ariaLabel: string
  className?: string
  disabled?: boolean
  title?: string
  widthRem?: number
  onCheckedChange?: (checked: boolean) => void
}

export function TextSwitch({
  checked,
  checkedLabel,
  uncheckedLabel,
  ariaChecked,
  ariaLabel,
  className,
  disabled,
  title,
  widthRem = 6.5,
  onCheckedChange,
}: TextSwitchProps) {
  const knobTranslateRem = widthRem - 1.75

  return (
    <button
      type="button"
      role="switch"
      aria-checked={ariaChecked ?? checked}
      aria-label={ariaLabel}
      className={cn(
        'relative inline-flex h-7 shrink-0 items-center overflow-hidden rounded-full border text-[13px] font-medium leading-none transition-colors focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50',
        checked ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-muted text-muted-foreground',
        className,
      )}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      style={{ width: `${widthRem}rem` }}
      title={title}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-y-0 left-3 flex items-center whitespace-nowrap transition-opacity',
          checked ? 'opacity-100' : 'opacity-0',
        )}
      >
        {checkedLabel}
      </span>
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-y-0 right-3 flex items-center whitespace-nowrap transition-opacity',
          checked ? 'opacity-0' : 'opacity-100',
        )}
      >
        {uncheckedLabel}
      </span>
      <span
        className="absolute left-1 top-1/2 size-5 rounded-full bg-background shadow-sm transition-transform"
        style={{ transform: checked ? `translate(${knobTranslateRem}rem, -50%)` : 'translate(0, -50%)' }}
      />
    </button>
  )
}
