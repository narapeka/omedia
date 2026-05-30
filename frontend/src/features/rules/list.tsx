import { useState } from 'react'
import { Plus } from 'lucide-react'
import { categoryCountLabel as formatCategoryCount } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { OrganizeRule, TransferRule } from '@/api/types'
import type { RuleKind, RuleRow, RuleSelection } from './draft'

export function RuleListTable({
  rows,
  selected,
  onSelect,
}: {
  rows: RuleRow[]
  selected: RuleSelection
  onSelect: (selection: RuleSelection) => void
}) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border/70 bg-transparent p-1">
      {rows.length ? (
        rows.map((row) => {
          const active = selected.kind === row.kind && selected.id === row.rule.id
          return (
            <button
              key={`${row.kind}:${row.rule.id}`}
              type="button"
              aria-current={active ? 'true' : undefined}
              className={cn(
                'flex min-h-11 w-full items-center gap-3 rounded-md border border-transparent px-3 py-2 text-left text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50',
                active
                  ? 'border-transparent bg-muted/70 text-foreground'
                  : 'border-transparent bg-transparent text-muted-foreground hover:bg-muted/20',
              )}
              onClick={() => onSelect({ kind: row.kind, id: row.rule.id })}
            >
              <RuleKindBadge kind={row.kind} />
              <span className={cn('min-w-0 flex-1 truncate font-medium', active ? 'text-foreground' : 'text-muted-foreground')}>
                {row.rule.name}
              </span>
              <span className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
                {formatCategoryCount(t, (row.rule.categories ?? []).length)}
                <span
                  aria-hidden="true"
                  className={cn('size-1.5 rounded-full transition-colors', active ? 'bg-muted-foreground' : 'bg-transparent')}
                />
              </span>
            </button>
          )
        })
      ) : (
        <div className="px-3 py-8 text-center text-sm text-muted-foreground">{t('noRulesYet')}</div>
      )}
    </div>
  )
}

export function RuleCreateMenu({ onCreate }: { onCreate: (kind: RuleKind) => void }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const createOptions: Array<{ kind: RuleKind; label: string }> = [
    { kind: 'organize', label: t('createOrganizeRule') },
    { kind: 'transfer', label: t('createTransferRule') },
  ]

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button aria-label={t('addRule')} className="w-full" variant="secondary">
          <Plus />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-1">
        <div className="flex flex-col gap-1">
          {createOptions.map((option) => (
            <button
              key={option.kind}
              type="button"
              className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm outline-none transition-colors hover:bg-muted focus-visible:bg-muted"
              onClick={() => {
                onCreate(option.kind)
                setOpen(false)
              }}
            >
              <RuleKindBadge kind={option.kind} />
              <span className="min-w-0 flex-1 truncate">{option.label}</span>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export function RuleKindBadge({ kind }: { kind: RuleKind }) {
  const { t } = useI18n()
  return (
    <Badge
      className={cn(
        'h-6 rounded-md px-2.5 text-[13px]',
        kind === 'organize'
          ? 'border-sky-400/30 bg-sky-500/10 text-sky-100'
          : 'border-emerald-400/30 bg-emerald-500/10 text-emerald-100',
      )}
    >
      {kind === 'organize' ? t('organize') : t('transfer')}
    </Badge>
  )
}

export function buildRuleRows(organizeRules: OrganizeRule[], transferRules: TransferRule[]): RuleRow[] {
  return [
    ...organizeRules.map((rule) => ({ kind: 'organize' as const, rule })),
    ...transferRules.map((rule) => ({ kind: 'transfer' as const, rule })),
  ].sort(compareRuleRows)
}

function compareRuleRows(left: RuleRow, right: RuleRow) {
  const kindOrder = ruleKindOrder(left.kind) - ruleKindOrder(right.kind)
  if (kindOrder !== 0) return kindOrder
  return left.rule.name.localeCompare(right.rule.name, undefined, { numeric: true, sensitivity: 'base' })
}

function ruleKindOrder(kind: RuleKind) {
  return kind === 'organize' ? 0 : 1
}

export function firstSelectionFromRows(rows: RuleRow[], preferredKind?: RuleKind): RuleSelection {
  const row = (preferredKind ? rows.find((item) => item.kind === preferredKind) : undefined) ?? rows[0]
  return { kind: row?.kind ?? preferredKind ?? 'organize', id: row?.rule.id ?? '' }
}
