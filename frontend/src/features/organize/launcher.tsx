import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { MultiSelectCombobox } from '@/components/common/MultiSelectCombobox'
import { PathRoute } from '@/components/filesystem/PathRoute'
import { mediaTypeLabel, type TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { DepotSummary, OriginSummary } from '@/api/types'
import { depotIsIncremental } from '@/features/depot/model'
import { cn } from '@/lib/utils'

export function LauncherModeButton({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        'h-7 shrink-0 rounded-md px-2.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
        active
          ? 'bg-background text-foreground shadow-sm ring-1 ring-border'
          : 'text-muted-foreground hover:bg-background/40 hover:text-foreground',
      )}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

export function ManualOriginPicker({
  ariaLabel,
  className,
  origins,
  selectedOriginIds,
  depotById,
  onValueChange,
}: {
  ariaLabel: string
  className?: string
  origins: OriginSummary[]
  selectedOriginIds: string[]
  depotById: Map<string, DepotSummary>
  onValueChange: (originIds: string[]) => void
}) {
  const { t } = useI18n()

  return (
    <MultiSelectCombobox
      ariaLabel={ariaLabel}
      emptyPlaceholder={t('noOriginsFound')}
      emptyText={t('noOriginsFound')}
      getItemDisabled={(origin) => !origin.enabled}
      getItemLabel={(origin) => origin.name}
      getItemSearchText={(origin) => {
        const targetDepot = depotById.get(origin.policy.target_depot_id)
        return [
          mediaTypeLabel(t, origin.media_type),
          origin.name,
          origin.path,
          targetDepot?.name,
          targetDepot?.path,
          targetDepot ? depotOptionIncrementalLabel(targetDepot, t) : '',
        ].filter(Boolean).join(' ')
      }}
      getItemValue={(origin) => origin.id}
      items={origins}
      placeholder={t('scanSelectedOrigins')}
      className={className}
      value={selectedOriginIds}
      onValueChange={onValueChange}
      contentClassName="!w-[min(560px,calc(100vw-3rem))] !min-w-[min(560px,calc(100vw-3rem))] 2xl:!w-[min(880px,calc(100vw-3rem))] 2xl:!min-w-[min(880px,calc(100vw-3rem))]"
      itemClassName="py-1.5"
      renderItemContent={(origin) => originOptionLabel(origin, depotById, t)}
    />
  )
}

function originOptionLabel(origin: OriginSummary, depotById: Map<string, DepotSummary>, t: TFunction) {
  const targetDepot = depotById.get(origin.policy.target_depot_id)
  const incrementalLabel = targetDepot ? depotOptionIncrementalLabel(targetDepot, t) : ''
  const targetName = targetDepot?.name ?? origin.policy.target_depot_id
  const targetPath = targetDepot?.path ?? targetName

  return (
    <span className="grid w-[32rem] max-w-[calc(100vw-3rem)] grid-cols-[3.5rem_8rem_8rem_minmax(0,1fr)] items-center gap-2 2xl:w-[52rem] 2xl:grid-cols-[4rem_10rem_12rem_minmax(0,1fr)] 2xl:gap-3">
      <span className="min-w-0">
        <Badge color={badgeColorForMediaType(origin.media_type)}>{mediaTypeLabel(t, origin.media_type)}</Badge>
      </span>
      <span className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate font-medium">{origin.name}</span>
        {!origin.enabled ? <Badge tone="danger">{t('disabled')}</Badge> : null}
      </span>
      <span className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate font-medium">{targetName}</span>
        {incrementalLabel ? <Badge>{incrementalLabel}</Badge> : null}
      </span>
      <PathRoute
        source={origin.path}
        target={targetPath}
        truncate
        className="text-xs text-muted-foreground"
        iconClassName="size-3"
      />
    </span>
  )
}

export function depotOptionLabel(depot: DepotSummary, t: TFunction) {
  const incrementalLabel = depotOptionIncrementalLabel(depot, t)

  return (
    <span className="grid w-[24rem] max-w-[calc(100vw-3rem)] grid-cols-[3.5rem_8rem_minmax(0,1fr)] items-center gap-2 2xl:w-[32rem] 2xl:grid-cols-[4rem_10rem_minmax(0,1fr)] 2xl:gap-3">
      <span className="min-w-0">
        <Badge color={badgeColorForMediaType(depot.media_type)}>{mediaTypeLabel(t, depot.media_type)}</Badge>
      </span>
      <span className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate font-medium">{depot.name}</span>
        {incrementalLabel ? <Badge>{incrementalLabel}</Badge> : null}
      </span>
      <span className="min-w-0 truncate text-xs text-muted-foreground" title={depot.path}>
        {depot.path}
      </span>
    </span>
  )
}

export function depotTriggerLabel(depot: DepotSummary, t: TFunction) {
  const incrementalLabel = depotOptionIncrementalLabel(depot, t)

  return (
    <span className="flex min-w-0 items-center gap-3">
      <Badge color={badgeColorForMediaType(depot.media_type)}>{mediaTypeLabel(t, depot.media_type)}</Badge>
      <span className="min-w-0 truncate font-medium">{depot.name}</span>
      {incrementalLabel ? <Badge>{incrementalLabel}</Badge> : null}
    </span>
  )
}

export function depotOptionIncrementalLabel(depot: DepotSummary, t: TFunction) {
  return depotIsIncremental(depot) ? t('resolveModeIncremental') : ''
}
