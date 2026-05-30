import type { ReactNode } from 'react'
import { useMemo } from 'react'
import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
  ComboboxValue,
  useComboboxAnchor,
} from '@/components/ui/combobox'
import { cn } from '@/lib/utils'

export type MultiSelectComboboxProps<TItem> = {
  ariaLabel: string
  emptyPlaceholder: string
  emptyText: string
  getItemDisabled?: (item: TItem) => boolean
  getItemLabel: (item: TItem) => string
  getItemSearchText?: (item: TItem) => string
  getItemValue: (item: TItem) => string
  items: TItem[]
  onValueChange: (value: string[]) => void
  placeholder: string
  renderItemContent?: (item: TItem) => ReactNode
  renderItemLabelAddon?: (item: TItem) => ReactNode
  renderItemMeta?: (item: TItem) => ReactNode
  value: string[]
  chipClassName?: string
  className?: string
  contentClassName?: string
  disabled?: boolean
  itemClassName?: string
}

export function MultiSelectCombobox<TItem>({
  ariaLabel,
  chipClassName,
  className,
  contentClassName,
  disabled,
  emptyPlaceholder,
  emptyText,
  getItemDisabled,
  getItemLabel,
  getItemSearchText,
  getItemValue,
  itemClassName,
  items,
  onValueChange,
  placeholder,
  renderItemContent,
  renderItemLabelAddon,
  renderItemMeta,
  value,
}: MultiSelectComboboxProps<TItem>) {
  const anchor = useComboboxAnchor()
  const itemByValue = useMemo(() => new Map(items.map((item) => [getItemValue(item), item])), [getItemValue, items])
  const itemValues = useMemo(() => items.map((item) => getItemValue(item)), [getItemValue, items])
  const selectedValues = value.filter((itemValue) => itemByValue.has(itemValue))
  const isDisabled = disabled || items.length === 0

  const getValueLabel = (itemValue: string) => {
    const item = itemByValue.get(itemValue)
    return item ? getItemLabel(item) : itemValue
  }

  const getValueSearchText = (itemValue: string) => {
    const item = itemByValue.get(itemValue)
    if (!item) return itemValue
    return getItemSearchText?.(item) ?? getItemLabel(item)
  }

  return (
    <Combobox
      multiple
      autoHighlight
      disabled={isDisabled}
      items={itemValues}
      itemToStringLabel={getValueSearchText}
      itemToStringValue={(itemValue) => itemValue}
      value={selectedValues}
      onValueChange={onValueChange}
    >
      <ComboboxChips ref={anchor} className={cn('w-full', className)}>
        <ComboboxValue>
          {(values: string[]) => (
            <>
              {values.map((itemValue) => (
                <ComboboxChip key={itemValue} className={cn('max-w-[min(18rem,100%)]', chipClassName)}>
                  <span className="truncate">{getValueLabel(itemValue)}</span>
                </ComboboxChip>
              ))}
              <ComboboxChipsInput
                aria-label={ariaLabel}
                className="min-w-0"
                disabled={isDisabled}
                placeholder={values.length === 0 ? (isDisabled ? emptyPlaceholder : placeholder) : undefined}
              />
              <ComboboxTrigger
                aria-label={ariaLabel}
                disabled={isDisabled}
                className="ml-auto inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground data-disabled:pointer-events-none data-disabled:opacity-50"
              />
            </>
          )}
        </ComboboxValue>
      </ComboboxChips>
      <ComboboxContent anchor={anchor} className={cn('w-[min(680px,calc(100vw-3rem))]', contentClassName)}>
        <ComboboxEmpty>{emptyText}</ComboboxEmpty>
        <ComboboxList>
          {(itemValue: string) => {
            const item = itemByValue.get(itemValue)
            if (!item) return null

            return (
              <ComboboxItem
                key={itemValue}
                value={itemValue}
                disabled={getItemDisabled?.(item)}
                className={cn('items-center py-1', itemClassName)}
              >
                {renderItemContent ? (
                  renderItemContent(item)
                ) : (
                  <div className="grid min-w-0 flex-1 grid-cols-[minmax(8rem,1fr)_minmax(12rem,1.5fr)] items-center gap-6">
                    <div className="flex min-w-0 items-center gap-2 font-medium">
                      <span className="truncate">{getItemLabel(item)}</span>
                      {renderItemLabelAddon?.(item)}
                    </div>
                    {renderItemMeta ? (
                      <div className="truncate text-right text-xs text-muted-foreground">{renderItemMeta(item)}</div>
                    ) : null}
                  </div>
                )}
              </ComboboxItem>
            )
          }}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}
