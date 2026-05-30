import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type SelectOption = { value: string; label: ReactNode; disabled?: boolean; textValue?: string }
const emptySelectValue = '__omedia_empty__'

export function SelectControl({
  contentAlign = 'start',
  contentPosition = 'popper',
  id,
  'aria-label': ariaLabel,
  value,
  onValueChange,
  options,
  placeholder,
  className,
  triggerClassName,
  triggerAriaLabel,
  triggerLabel,
  ...props
}: Omit<ComponentProps<typeof Select>, 'value' | 'onValueChange'> & {
  value?: string | null
  onValueChange: (value: string) => void
  options: SelectOption[]
  contentAlign?: ComponentProps<typeof SelectContent>['align']
  contentPosition?: ComponentProps<typeof SelectContent>['position']
  id?: string
  'aria-label'?: string
  placeholder?: string
  className?: string
  triggerClassName?: string
  triggerAriaLabel?: string
  triggerLabel?: ReactNode
}) {
  const hasEmptyOption = options.some((option) => option.value === '')
  const currentValue = value === '' || value === null || value === undefined ? (hasEmptyOption ? emptySelectValue : '') : value
  return (
    <Select value={currentValue} onValueChange={(nextValue) => onValueChange(nextValue === emptySelectValue ? '' : nextValue)} {...props}>
      <SelectTrigger id={id} aria-label={triggerAriaLabel ?? ariaLabel} className={cn('w-full', triggerClassName)}>
        <SelectValue placeholder={placeholder}>{triggerLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent className={className} position={contentPosition} align={contentAlign}>
        <SelectGroup>
          {options.map((option) => (
            <SelectItem
              key={option.value || emptySelectValue}
              value={option.value || emptySelectValue}
              disabled={option.disabled}
              textValue={option.textValue}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
