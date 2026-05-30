import { ChevronDown, ChevronLast, ChevronRight, Plus, Trash2, X } from 'lucide-react'
import { useRef, useState } from 'react'
import type { RuleReferences } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { InfoTooltip } from '@/components/common/InfoTooltip'
import { SelectControl } from '@/components/common/SelectControl'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { ConditionValueEditor } from './condition'
import type { CategoryDraft, RuleKind } from './draft'
import { bucketHelpText, bucketVariableOptions, conditionWithField, conditionWithOperator, emptyCondition, fallbackBucketHelpText, fieldOptions, operatorOptions, updateCondition } from './draft'

export function AddCategoryControl({ onClick }: { onClick: () => void }) {
  const { t } = useI18n()
  return (
    <button
      type="button"
      aria-label={t('addCategory')}
      className="flex min-h-20 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/10 p-4 text-center text-sm font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:bg-muted/20 hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      onClick={onClick}
    >
      <Plus className="size-6" aria-hidden="true" />
      <span>{t('addCategory')}</span>
    </button>
  )
}

export function TransferAddCategoryPrompt({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}) {
  const { t } = useI18n()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('transferAddCategoryPromptTitle')}</DialogTitle>
          <DialogDescription>{t('transferAddCategoryPromptDescription')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
          <Button onClick={onConfirm}>
            <Plus data-icon="inline-start" />
            {t('continueAddCategory')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function BucketInput({
  className,
  value,
  placeholder,
  onChange,
  'aria-label': ariaLabel,
}: {
  className?: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
  'aria-label': string
}) {
  const { t } = useI18n()
  const inputRef = useRef<HTMLInputElement>(null)
  const anchorRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)

  const insertVariable = (variable: string) => {
    const input = inputRef.current
    onChange(variable)
    setOpen(false)
    window.requestAnimationFrame(() => {
      if (document.activeElement === input) input?.setSelectionRange(variable.length, variable.length)
    })
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div ref={anchorRef} className={cn('relative', className)}>
          <Input
            ref={inputRef}
            aria-expanded={open}
            aria-haspopup="listbox"
            aria-label={ariaLabel}
            autoComplete="off"
            className="h-full"
            value={value}
            placeholder={placeholder}
            onChange={(event) => onChange(event.target.value)}
            onClick={() => setOpen(true)}
            onFocus={() => setOpen(true)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setOpen(false)
            }}
          />
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        className="w-[min(400px,calc(100vw-2rem))] p-1"
        onCloseAutoFocus={(event) => event.preventDefault()}
        onInteractOutside={(event) => {
          const target = event.target
          if (target instanceof Node && anchorRef.current?.contains(target)) event.preventDefault()
        }}
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <div role="listbox" aria-label={t('bucketVariableHelp')} className="flex flex-col gap-1">
          {bucketVariableOptions.map((variable) => (
            <button
              key={variable}
              type="button"
              role="option"
              aria-selected="false"
              className="rounded-md px-2 py-1.5 text-left font-mono text-sm text-foreground outline-none hover:bg-muted focus-visible:bg-muted"
              onClick={() => insertVariable(variable)}
              onMouseDown={(event) => event.preventDefault()}
            >
              {variable}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export function CategoryEditor({
  kind,
  ruleReferences,
  category,
  categoryIndex,
  expanded,
  onToggleExpanded,
  onChange,
  onRemove,
}: {
  kind: RuleKind
  ruleReferences: RuleReferences
  category: CategoryDraft
  categoryIndex: number
  expanded: boolean
  onToggleExpanded: () => void
  onChange: (category: CategoryDraft) => void
  onRemove: () => void
}) {
  const { t, locale } = useI18n()
  const categoryLabel = `${t('bucket')} ${categoryIndex + 1}`
  const addCondition = () => onChange({ ...category, conditions: [...category.conditions, emptyCondition()] })
  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      <div className={cn('flex flex-wrap items-start justify-between gap-3 bg-muted/20 p-3 sm:items-center', expanded ? 'border-b' : null)}>
        <div className="grid min-w-0 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 sm:flex sm:flex-wrap">
          <Button
            aria-label={expanded ? t('collapseLabel', { label: categoryLabel }) : t('expandLabel', { label: categoryLabel })}
            aria-expanded={expanded}
            size="icon-sm"
            variant="ghost"
            onClick={onToggleExpanded}
          >
            {expanded ? <ChevronDown /> : <ChevronRight />}
          </Button>
          <span className="min-w-0 truncate font-medium sm:w-16 sm:shrink-0 sm:whitespace-nowrap">{categoryLabel}</span>
          <InfoTooltip label={bucketHelpText(t)} />
          <BucketInput
            aria-label={t('bucket')}
            className="col-span-3 h-9 min-w-0 sm:col-span-auto sm:ml-1 sm:w-[400px] sm:max-w-[400px]"
            value={category.bucket}
            placeholder={t('bucketPlaceholder')}
            onChange={(bucket) => onChange({ ...category, bucket })}
          />
        </div>
        <Button size="icon-sm" variant="ghost" aria-label={t('removeCategory', { name: category.bucket || t('unnamedCategory') })} onClick={onRemove}>
          <X />
        </Button>
      </div>
      {expanded ? (
        <div className="p-3">
          <div className="overflow-hidden rounded-lg border bg-muted/10">
            <Table className="block sm:table sm:min-w-[640px] sm:table-fixed">
              <colgroup>
                <col style={{ width: '24%' }} />
                <col style={{ width: '19%' }} />
                <col />
                <col style={{ width: '48px' }} />
              </colgroup>
              <TableHeader className="block sm:table-header-group">
                <TableRow className="flex items-center justify-between hover:bg-transparent sm:table-row">
                  <TableHead className="block h-auto px-3 py-2 text-muted-foreground sm:table-cell sm:h-10 sm:py-0">
                    <div className="flex items-center gap-1.5">
                      {t('conditionField')}
                    </div>
                  </TableHead>
                  <TableHead className="hidden px-3 text-muted-foreground sm:table-cell">
                    <div className="flex items-center gap-1.5">
                      {t('operator')}
                    </div>
                  </TableHead>
                  <TableHead className="hidden px-3 text-muted-foreground sm:table-cell">
                    <div className="flex items-center gap-1.5">
                      {t('value')}
                      <InfoTooltip label={t('conditionValueHelpText')} />
                    </div>
                  </TableHead>
                  <TableHead className="block h-auto px-2 py-2 sm:table-cell sm:h-10 sm:py-0">
                    <div className="flex justify-end">
                      <Button size="icon-sm" variant="secondary" aria-label={t('addCondition')} onClick={addCondition}>
                        <Plus />
                      </Button>
                    </div>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="block sm:table-row-group">
                {category.conditions.length ? (
                  category.conditions.map((condition, conditionIndex) => (
                    <TableRow key={conditionIndex} className="grid gap-2 p-3 hover:bg-muted/20 sm:table-row sm:p-0">
                      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
                        <div className="grid gap-1">
                          <span className="text-xs text-muted-foreground sm:hidden">{t('conditionField')}</span>
                          <SelectControl
                            value={condition.field}
                            onValueChange={(field) => onChange(updateCondition(category, conditionIndex, conditionWithField(kind, condition, field)))}
                            options={fieldOptions(kind, t)}
                            placeholder={t('choosePlaceholder')}
                            triggerAriaLabel={t('conditionField')}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
                        <div className="grid gap-1">
                          <span className="text-xs text-muted-foreground sm:hidden">{t('operator')}</span>
                          <SelectControl
                            value={condition.op}
                            onValueChange={(op) => onChange(updateCondition(category, conditionIndex, conditionWithOperator(condition, op)))}
                            options={operatorOptions(kind, condition.field, t)}
                            placeholder={t('choosePlaceholder')}
                            triggerAriaLabel={t('operator')}
                            disabled={!condition.field}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
                        <div className="grid gap-1">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground sm:hidden">
                            {t('value')}
                            <InfoTooltip label={t('conditionValueHelpText')} />
                          </div>
                          <ConditionValueEditor
                            condition={condition}
                            locale={locale}
                            ruleReferences={ruleReferences}
                            disabled={!condition.field || !condition.op}
                            onChange={(value) => onChange(updateCondition(category, conditionIndex, { ...condition, value }))}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="block p-0 sm:table-cell sm:px-2 sm:py-2">
                        <div className="flex justify-end">
                          <Button
                            size="icon-sm"
                            variant="danger"
                            aria-label={t('removeCondition')}
                            disabled={category.conditions.length <= 1}
                            onClick={() => onChange({ ...category, conditions: category.conditions.filter((_item, index) => index !== conditionIndex) })}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow className="block hover:bg-transparent sm:table-row">
                    <TableCell colSpan={4} className="block px-3 py-6 text-center text-muted-foreground sm:table-cell">
                      {t('noConditions')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : null}
    </section>
  )
}

export function FallbackBucketEditor({
  bucket,
  onChange,
}: {
  bucket: string
  onChange: (bucket: string) => void
}) {
  const { t } = useI18n()
  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      <div className="flex flex-wrap items-center gap-3 bg-muted/20 p-3">
        <div className="grid min-w-0 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 sm:flex sm:flex-wrap">
          <Button
            aria-label={t('expandLabel', { label: t('fallbackBucket') })}
            aria-expanded={false}
            disabled
            size="icon-sm"
            variant="ghost"
          >
            <ChevronLast />
          </Button>
          <span className="min-w-0 truncate font-medium sm:w-16 sm:shrink-0 sm:whitespace-nowrap">{t('fallbackBucket')}</span>
          <InfoTooltip label={fallbackBucketHelpText(t)} />
          <BucketInput
            aria-label={t('fallbackBucket')}
            className="col-span-3 h-9 min-w-0 sm:col-span-auto sm:ml-1 sm:w-[400px] sm:max-w-[400px]"
            value={bucket}
            placeholder={t('bucketPlaceholder')}
            onChange={onChange}
          />
        </div>
      </div>
    </section>
  )
}
