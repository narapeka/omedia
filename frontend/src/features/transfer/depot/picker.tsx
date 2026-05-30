import { mediaTypeLabel, type TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { MultiSelectCombobox } from '@/components/common/MultiSelectCombobox'
import { PathRoute } from '@/components/filesystem/PathRoute'
import type { DepotGroupView } from './model'
import { depotOptionIncrementalLabel } from './model'

export function TransferDepotMultiSelect({
  ariaLabel,
  className,
  emptyLabel,
  depots,
  placeholder,
  selectedDepotIds,
  onDepotSelected,
}: {
  ariaLabel: string
  className?: string
  emptyLabel: string
  depots: DepotGroupView[]
  placeholder: string
  selectedDepotIds: string[]
  onDepotSelected: (depotId: string, selected: boolean) => void
}) {
  const { t } = useI18n()
  const selectedDepots = depots.filter((depot) => selectedDepotIds.includes(depot.id))
  const selectedIds = selectedDepots.map((depot) => depot.id)
  const syncSelectedIds = (nextSelectedIds: string[]) => {
    const currentSelectedIdSet = new Set(selectedIds)
    const nextSelectedIdSet = new Set(nextSelectedIds)

    for (const depotId of selectedIds) {
      if (!nextSelectedIdSet.has(depotId)) onDepotSelected(depotId, false)
    }
    for (const depotId of nextSelectedIds) {
      if (!currentSelectedIdSet.has(depotId)) onDepotSelected(depotId, true)
    }
  }

  return (
    <MultiSelectCombobox
      ariaLabel={ariaLabel}
      emptyPlaceholder={emptyLabel}
      emptyText={t('noDepotsFound')}
      getItemDisabled={(depot) => !depot.enabled}
      getItemLabel={(depot) => depot.name}
      getItemSearchText={(depot) => [
        mediaTypeLabel(t, depot.mediaType),
        depot.name,
        depotOptionIncrementalLabel(depot, t),
        depot.id,
        depot.depotPath,
        depot.libraryPath,
      ].filter(Boolean).join(' ')}
      getItemValue={(depot) => depot.id}
      items={depots}
      placeholder={placeholder}
      className={className}
      value={selectedIds}
      onValueChange={syncSelectedIds}
      contentClassName="!w-[min(520px,calc(100vw-3rem))] !min-w-[min(520px,calc(100vw-3rem))] 2xl:!w-[min(760px,calc(100vw-3rem))] 2xl:!min-w-[min(760px,calc(100vw-3rem))]"
      itemClassName="py-1.5"
      renderItemContent={(depot) => depotOptionLabel(depot, t)}
    />
  )
}

export function depotOptionLabel(depot: DepotGroupView, t: TFunction) {
  const incrementalLabel = depotOptionIncrementalLabel(depot, t)

  return (
    <span className="grid w-[28rem] max-w-[calc(100vw-3rem)] grid-cols-[3.5rem_9rem_minmax(0,1fr)] items-center gap-2 2xl:w-[44rem] 2xl:grid-cols-[4rem_12rem_minmax(0,1fr)] 2xl:gap-3">
      <span className="min-w-0">
        <Badge color={badgeColorForMediaType(depot.mediaType)}>{mediaTypeLabel(t, depot.mediaType)}</Badge>
      </span>
      <span className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate font-medium">{depot.name}</span>
        {incrementalLabel ? <Badge>{incrementalLabel}</Badge> : null}
        {!depot.enabled ? <Badge tone="danger">{t('disabled')}</Badge> : null}
      </span>
      <PathRoute
        source={depot.depotPath}
        target={depot.libraryPath}
        truncate
        className="text-xs text-muted-foreground"
        iconClassName="size-3"
      />
    </span>
  )
}
