import type { InputHTMLAttributes, ReactNode } from 'react'
import { useId } from 'react'
import { InfoTooltip } from '@/components/common/InfoTooltip'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

export const fieldCaptionClassName = 'items-center gap-1.5 text-xs font-normal text-muted-foreground'

export function FieldLabelWithInfo({
  children,
  help,
  htmlFor,
}: {
  children: ReactNode
  help?: ReactNode
  htmlFor?: string
}) {
  return (
    <FieldLabel htmlFor={htmlFor} className={fieldCaptionClassName}>
      <span>{children}</span>
      {help ? (
        <InfoTooltip label={`${children} info`}>{help}</InfoTooltip>
      ) : null}
    </FieldLabel>
  )
}

type TextFieldProps = {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  disabled?: boolean
  min?: InputHTMLAttributes<HTMLInputElement>['min']
  max?: InputHTMLAttributes<HTMLInputElement>['max']
  step?: InputHTMLAttributes<HTMLInputElement>['step']
  inputMode?: InputHTMLAttributes<HTMLInputElement>['inputMode']
}

export function TextField({
  label,
  value,
  onChange,
  type = 'text',
  disabled = false,
  min,
  max,
  step,
  inputMode,
}: TextFieldProps) {
  const id = useId()
  return (
    <Field>
      <Input id={id} type={type} min={min} max={max} step={step} inputMode={inputMode} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} />
      <FieldLabel htmlFor={id} className={fieldCaptionClassName}>{label}</FieldLabel>
    </Field>
  )
}
