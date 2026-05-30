import { ChevronDown, ChevronRight, Pencil } from 'lucide-react'
import { mediaTypeLabel, type TFunction } from '@/app/i18n/labels'
import type { DepotSummary, OriginSummary } from '@/api/types'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { PathRoute } from '@/components/filesystem/PathRoute'
import { depotIsIncremental, depotResolveMode } from '@/features/depot/model'
import { cn } from '@/lib/utils'
import { useIs2xl } from '@/lib/useMediaQuery'
import { DepotRemoveButton, depotResolveModeLabel, highConfidenceBadgeClass } from './depot'
import type { OriginDraft } from './draft'
import { OriginChildTable } from './origin'
import { ruleName } from './validate'

export function DepotFolderSection({
  depot,
  sourceOrigins,
  users,
  expanded,
  activeOriginDraft,
  organizeRules,
  transferRules,
  savingOrigin,
  onToggle,
  onEditDepot,
  onRemoveDepot,
  onAddOrigin,
  onEditOrigin,
  onOriginDraftChange,
  onSaveOrigin,
  onCancelOrigin,
  onRemoveOrigin,
  t,
}: {
  depot: DepotSummary
  sourceOrigins: OriginSummary[]
  users: OriginSummary[]
  expanded: boolean
  activeOriginDraft: OriginDraft | null
  organizeRules: { id: string; name?: string | null }[]
  transferRules: { id: string; name?: string | null }[]
  savingOrigin: boolean
  onToggle: () => void
  onEditDepot: () => void
  onRemoveDepot: () => void
  onAddOrigin: () => void
  onEditOrigin: (origin: OriginSummary) => void
  onOriginDraftChange: (draft: OriginDraft | null) => void
  onSaveOrigin: () => void
  onCancelOrigin: () => void
  onRemoveOrigin: (origin: OriginSummary) => void
  t: TFunction
}) {
  const is2xl = useIs2xl()

  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      <div className="grid gap-y-3 border-b bg-muted/30 p-3 2xl:min-h-[72px] 2xl:grid-cols-[minmax(12rem,22%)_minmax(18rem,1fr)_minmax(10rem,24%)_156px] 2xl:items-center">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={expanded ? t('collapseLabel', { label: depot.name }) : t('expandLabel', { label: depot.name })}
              aria-expanded={expanded}
              onClick={onToggle}
            >
              {expanded ? <ChevronDown /> : <ChevronRight />}
            </Button>
            <Badge className="text-sm" color={badgeColorForMediaType(depot.media_type)}>{mediaTypeLabel(t, depot.media_type)}</Badge>
            <span className="min-w-0 truncate text-base font-semibold" title={depot.name}>
              {depot.name}
            </span>
            {depotIsIncremental(depot) ? (
              <Badge className={highConfidenceBadgeClass()}>{depotResolveModeLabel(t, depotResolveMode(depot))}</Badge>
            ) : null}
          </div>
          {!is2xl ? (
            <DepotFolderActions
              depot={depot}
              users={users}
              onEditDepot={onEditDepot}
              onRemoveDepot={onRemoveDepot}
              t={t}
              className="shrink-0"
            />
          ) : null}
        </div>
        <div className="grid min-w-0 grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center 2xl:contents">
          <div className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-2 text-foreground sm:flex sm:flex-[1_1_26rem] sm:items-center 2xl:flex-none 2xl:px-3">
            <span className="shrink-0 text-muted-foreground">{t('path')}</span>
            <PathRoute
              className="omedia-settings-folder-route flex-1"
              pathClassName="omedia-settings-folder-route-path"
              source={depot.path}
              target={depot.policy.target_library_path}
              truncate
            />
          </div>
          <div className="flex min-w-0 items-center justify-between gap-2 text-foreground sm:gap-10 2xl:flex-none 2xl:gap-3 2xl:px-3" title={ruleName(transferRules, depot.policy.transfer_rule_id, t)}>
            <div className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-2 sm:flex sm:items-center">
              <span className="shrink-0 text-muted-foreground">{t('rule')}</span>
              <span className="truncate">{ruleName(transferRules, depot.policy.transfer_rule_id, t)}</span>
            </div>
            <Badge className="shrink-0 text-muted-foreground 2xl:mr-24">{t('origins')} {sourceOrigins.length}</Badge>
          </div>
        </div>
        {is2xl ? (
          <DepotFolderActions
            depot={depot}
            users={users}
            onEditDepot={onEditDepot}
            onRemoveDepot={onRemoveDepot}
            t={t}
            className="px-2"
          />
        ) : null}
      </div>
      {expanded ? (
        <div className="bg-background p-3">
          <OriginChildTable
            origins={sourceOrigins}
            organizeRules={organizeRules}
            activeDraft={activeOriginDraft}
            saving={savingOrigin}
            onAdd={onAddOrigin}
            onEdit={onEditOrigin}
            onDraftChange={onOriginDraftChange}
            onSave={onSaveOrigin}
            onCancel={onCancelOrigin}
            onRemove={onRemoveOrigin}
          />
        </div>
      ) : null}
    </section>
  )
}

function DepotFolderActions({
  depot,
  users,
  onEditDepot,
  onRemoveDepot,
  t,
  className,
}: {
  depot: DepotSummary
  users: OriginSummary[]
  onEditDepot: () => void
  onRemoveDepot: () => void
  t: TFunction
  className?: string
}) {
  return (
    <div className={cn('flex flex-nowrap justify-end gap-2', className)}>
      <Button className="whitespace-nowrap" size="sm" variant="outline" aria-label={t('editLabel', { label: depot.name })} onClick={onEditDepot}>
        <Pencil data-icon="inline-start" />
        {t('edit')}
      </Button>
      <DepotRemoveButton depot={depot} users={users} mode="button" onRemove={onRemoveDepot} />
    </div>
  )
}
