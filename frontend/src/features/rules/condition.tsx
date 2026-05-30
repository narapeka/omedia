import { Check, Pipette } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { RuleReferences } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { ConditionDraft } from './draft'
import { filterReferenceOptions, formatReferenceValue, referenceOptionsForCondition, selectedReferenceValues, toggleValue } from './draft'
import type { RuleReferenceOption } from './references'

export function ConditionValueEditor({
  condition,
  locale,
  ruleReferences,
  disabled,
  onChange,
}: {
  condition: ConditionDraft
  locale: string
  ruleReferences: RuleReferences
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const { t } = useI18n()
  const helperOptions = referenceOptionsForCondition(condition, ruleReferences, locale)
  const selectedValues = selectedReferenceValues(condition)

  if (!helperOptions.length) {
    return (
      <Input
        aria-label={t('value')}
        className={conditionValueInputClassName(disabled)}
        value={condition.value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  return (
    <div className="flex h-8 min-w-0 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
      <Input
        aria-label={t('value')}
        className={cn(
          'h-full min-w-0 flex-1 rounded-none border-0 bg-transparent px-3 focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent',
          disabled ? 'dark:bg-transparent' : null,
        )}
        value={condition.value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
      <ReferenceValuePicker
        condition={condition}
        options={helperOptions}
        selectedValues={selectedValues}
        disabled={disabled}
        onChange={onChange}
      />
    </div>
  )
}

function conditionValueInputClassName(disabled?: boolean) {
  return disabled ? 'disabled:bg-transparent dark:disabled:bg-input/30' : undefined
}

function ReferenceValuePicker({
  condition,
  options,
  selectedValues,
  disabled,
  onChange,
}: {
  condition: ConditionDraft
  options: RuleReferenceOption[]
  selectedValues: string[]
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selectedSet = useMemo(() => new Set(selectedValues), [selectedValues])
  const multiple = condition.op === 'in'
  const twoColumnLayout = condition.field === 'tmdb.genre_ids' || condition.field === 'tmdb.origin_country'
  const filteredOptions = useMemo(() => filterReferenceOptions(options, query).slice(0, 80), [options, query])

  const updateSelection = (value: string) => {
    const nextValues = multiple ? toggleValue(selectedValues, value) : [value]
    onChange(formatReferenceValue(condition.field, condition.op, nextValues))
    if (!multiple) setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="h-full w-20 rounded-none border-y-0 border-l border-r-0 border-input bg-transparent px-3 hover:bg-muted/70 focus-visible:ring-0"
          disabled={disabled}
        >
          <Pipette data-icon="inline-start" />
          {t('chooseValue')}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="flex max-h-[28rem] w-[min(28rem,calc(100vw-2rem))] flex-col gap-2 p-3">
        <Input value={query} placeholder={t('valueSearchPlaceholder')} onChange={(event) => setQuery(event.target.value)} />
        <div className="max-h-80 overflow-y-auto pr-1">
          {filteredOptions.length ? (
            <div className="flex flex-col gap-1">
              {filteredOptions.map((option) => {
                const checked = selectedSet.has(option.value)
                return (
                  <div
                    key={option.value}
                    role="option"
                    aria-selected={checked}
                    tabIndex={0}
                    className={cn('flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm outline-none hover:bg-muted focus-visible:bg-muted', checked ? 'bg-muted text-foreground' : 'text-foreground')}
                    onClick={() => updateSelection(option.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        updateSelection(option.value)
                      }
                    }}
                  >
                    {multiple ? (
                      <Checkbox
                        checked={checked}
                        aria-label={option.label}
                        onClick={(event) => event.stopPropagation()}
                        onCheckedChange={() => updateSelection(option.value)}
                      />
                    ) : (
                      <span className="flex size-4 shrink-0 items-center justify-center">
                        {checked ? <Check /> : null}
                      </span>
                    )}
                    <span
                      className={cn(
                        'min-w-0 flex-1',
                        twoColumnLayout ? 'grid grid-cols-[minmax(6rem,0.9fr)_minmax(8rem,1.1fr)] items-center gap-4' : null,
                      )}
                    >
                      <span className="block truncate font-medium">{option.label}</span>
                      {option.description ? (
                        <span className={cn('block truncate text-muted-foreground', twoColumnLayout ? 'text-sm' : 'text-xs')}>
                          {option.description}
                        </span>
                      ) : null}
                    </span>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="py-6 text-center text-sm text-muted-foreground">{t('noValueMatches')}</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

