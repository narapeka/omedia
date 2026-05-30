import { useEffect, useState } from 'react'
import { Check, ChevronDown, ChevronUp, CircleX, Pencil, X } from 'lucide-react'
import type { DepotSummary, DepotDraft, TransferRule } from '@/api/types'
import { mediaTypeLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notifyError } from '@/lib/notifications'
import { useIs2xl } from '@/lib/useMediaQuery'
import { useDepotConfigActions } from '@/features/depot/api'
import { depotIsIncremental } from '@/features/depot/model'
import { CronScheduleControl } from './control'
import {
  buildTransferDrafts,
  isTransferDraftDirty,
  depotToTransferDraft,
  scheduleDisplayLabel,
  transferDraftError,
  type TransferAutomationDraft,
} from './model'

const SCHEDULED_TRANSFER_GRID =
  'md:grid-cols-[minmax(0,1.35fr)_minmax(0,0.7fr)_minmax(0,2fr)_minmax(0,2fr)_minmax(0,1.15fr)_minmax(0,1.45fr)_6rem]'

export function ScheduledTransferSection({
  open,
  depots,
  transferRules,
  onOpenChange,
}: {
  open: boolean
  depots: DepotSummary[]
  transferRules: TransferRule[]
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  const actions = useDepotConfigActions()
  const [drafts, setDrafts] = useState<Record<string, TransferAutomationDraft>>(() => buildTransferDrafts(depots))
  const [editingDepotId, setEditingDepotId] = useState<string | null>(null)

  useEffect(() => {
    setDrafts(buildTransferDrafts(depots))
    setEditingDepotId((current) => (current && depots.some((depot) => depot.id === current) ? current : null))
  }, [depots])

  const saving = actions.saveDepot.isPending
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  const updateDraft = (depotId: string, patch: Partial<TransferAutomationDraft>) => {
    setDrafts((current) => ({
      ...current,
      [depotId]: {
        ...current[depotId],
        ...patch,
      },
    }))
  }

  const editDepot = (depot: DepotSummary) => {
    setDrafts((current) => ({
      ...current,
      [depot.id]: depotToTransferDraft(depot),
    }))
    setEditingDepotId(depot.id)
  }

  const cancelEdit = (depot: DepotSummary) => {
    setDrafts((current) => ({
      ...current,
      [depot.id]: depotToTransferDraft(depot),
    }))
    setEditingDepotId(null)
  }

  const saveDraft = async (depot: DepotSummary) => {
    const draft = drafts[depot.id] ?? depotToTransferDraft(depot)
    if (transferDraftError(draft) || !isTransferDraftDirty(depot, draft)) return
    try {
      await actions.saveDepot.mutateAsync({ depotId: depot.id, data: depotPayload(depot, draft) })
      setEditingDepotId(null)
    } catch (error) {
      onActionError(error)
    }
  }

  const clearSchedule = async (depot: DepotSummary) => {
    if (!depotToTransferDraft(depot).schedule.trim()) return
    try {
      await actions.saveDepot.mutateAsync({ depotId: depot.id, data: depotPayload(depot, { schedule: '' }) })
      setEditingDepotId((current) => (current === depot.id ? null : current))
    } catch (error) {
      onActionError(error)
    }
  }

  return (
    <Card className="overflow-visible">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle>{t('scheduledTransferLower')}</CardTitle>
            <CardDescription>{t('scheduledTransferDescription')}</CardDescription>
          </div>
          <Button
            aria-expanded={open}
            aria-label={open ? t('collapseLabel', { label: t('scheduledTransferLower') }) : t('expandLabel', { label: t('scheduledTransferLower') })}
            size="icon-sm"
            variant="ghost"
            onClick={() => onOpenChange(!open)}
          >
            {open ? <ChevronUp /> : <ChevronDown />}
          </Button>
        </div>
      </CardHeader>
      {open ? (
        <CardContent className="overflow-visible">
          {depots.length === 0 ? (
            <div className="py-6 text-sm text-muted-foreground">{t('noDepotsConfigured')}</div>
          ) : (
            <>
              {!is2xl ? (
              <div className="flex flex-col gap-3">
                {depots.map((depot) => {
                  const draft = drafts[depot.id] ?? depotToTransferDraft(depot)
                  const rule = depot.policy.transfer_rule_id ? transferRules.find((item) => item.id === depot.policy.transfer_rule_id) : null
                  const isEditing = editingDepotId === depot.id
                  const savedDraft = depotToTransferDraft(depot)
                  const rowDirty = isTransferDraftDirty(depot, draft)
                  const rowValid = !transferDraftError(draft)
                  const libraryPath = depot.policy.target_library_path || '-'
                  const resolveModeLabel = depotIsIncremental(depot) ? t('resolveModeIncremental') : ''
                  return (
                    <div key={`${depot.id}:card`} className="rounded-lg border bg-muted/20 p-3">
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
                        <div className="min-w-0">
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="min-w-0 truncate font-medium" title={depot.name}>{depot.name}</span>
                            <Badge color={badgeColorForMediaType(depot.media_type)}>{mediaTypeLabel(t, depot.media_type)}</Badge>
                            {resolveModeLabel ? <Badge>{resolveModeLabel}</Badge> : null}
                          </div>
                          <div className="truncate text-xs text-muted-foreground" title={`${depot.path} -> ${libraryPath}`}>
                            {depot.path} {'->'} {libraryPath}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {isEditing ? (
                            <>
                              <Button
                                aria-label={`${t('save')} ${depot.name}`}
                                size="icon-sm"
                                variant="ghost"
                                disabled={saving || !rowDirty || !rowValid}
                                title={`${t('save')} ${depot.name}`}
                                onClick={() => void saveDraft(depot)}
                              >
                                <Check />
                              </Button>
                              <Button
                                aria-label={`${t('cancel')} ${depot.name}`}
                                size="icon-sm"
                                variant="ghost"
                                disabled={saving}
                                title={`${t('cancel')} ${depot.name}`}
                                onClick={() => cancelEdit(depot)}
                              >
                                <X />
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                aria-label={t('editLabel', { label: depot.name })}
                                size="icon-sm"
                                variant="ghost"
                                disabled={saving}
                                title={t('editLabel', { label: depot.name })}
                                onClick={() => editDepot(depot)}
                              >
                                <Pencil />
                              </Button>
                              <Button
                                aria-label={t('removeLabel', { label: depot.name })}
                                size="icon-sm"
                                variant="ghost"
                                disabled={saving || !savedDraft.schedule.trim()}
                                title={t('removeLabel', { label: depot.name })}
                                onClick={() => void clearSchedule(depot)}
                              >
                                <CircleX />
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="mt-3 grid min-w-0 grid-cols-[4rem_minmax(0,1fr)_4rem_minmax(0,1.35fr)] items-center gap-2 text-sm">
                        <span className="text-muted-foreground">{t('rule')}</span>
                        <span className="min-w-0 truncate font-medium text-muted-foreground" title={rule?.name ?? depot.policy.transfer_rule_id ?? t('none')}>
                          {rule?.name ?? depot.policy.transfer_rule_id ?? t('none')}
                        </span>
                        <span className="text-muted-foreground">{t('schedule')}</span>
                        {isEditing ? (
                          <CronScheduleControl value={draft.schedule} onChange={(schedule) => updateDraft(depot.id, { schedule })} />
                        ) : (
                          <span className="min-w-0 truncate font-medium text-muted-foreground" title={savedDraft.schedule || t('manualOnly')}>
                            {scheduleDisplayLabel(savedDraft.schedule, t)}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
              ) : null}

              {is2xl ? (
              <div className="divide-y">
                <div className={`grid min-h-10 min-w-0 items-center gap-y-3 gap-x-6 px-2 text-sm font-medium whitespace-nowrap text-foreground xl:gap-x-10 ${SCHEDULED_TRANSFER_GRID}`}>
                  <span>{t('depotName')}</span>
                  <span>{t('type')}</span>
                  <span>{t('depotPath')}</span>
                  <span>{t('libraryPath')}</span>
                  <span>{t('rule')}</span>
                  <span>{t('schedule')}</span>
                  <span>{t('actions')}</span>
                </div>
                {depots.map((depot) => {
                  const draft = drafts[depot.id] ?? depotToTransferDraft(depot)
                  const rule = depot.policy.transfer_rule_id ? transferRules.find((item) => item.id === depot.policy.transfer_rule_id) : null
                  const isEditing = editingDepotId === depot.id
                  const savedDraft = depotToTransferDraft(depot)
                  const rowDirty = isTransferDraftDirty(depot, draft)
                  const rowValid = !transferDraftError(draft)
                  const libraryPath = depot.policy.target_library_path || '-'
                  const resolveModeLabel = depotIsIncremental(depot) ? t('resolveModeIncremental') : ''
                  return (
                    <div key={depot.id} className={`grid min-w-0 gap-y-3 gap-x-6 px-2 py-3 md:items-center xl:gap-x-10 ${SCHEDULED_TRANSFER_GRID}`}>
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="min-w-0 truncate font-medium" title={depot.name}>{depot.name}</span>
                        </div>
                      </div>
                      <div className="flex min-w-0 flex-wrap items-center gap-1">
                        <Badge color={badgeColorForMediaType(depot.media_type)}>{mediaTypeLabel(t, depot.media_type)}</Badge>
                        {resolveModeLabel ? <Badge>{resolveModeLabel}</Badge> : null}
                      </div>
                      <div className="min-w-0 truncate text-sm" title={depot.path}>
                        {depot.path}
                      </div>
                      <div className="min-w-0 truncate text-sm" title={libraryPath}>
                        {libraryPath}
                      </div>
                      <div className="min-w-0 truncate text-sm" title={rule?.name ?? depot.policy.transfer_rule_id ?? t('none')}>
                        {rule?.name ?? depot.policy.transfer_rule_id ?? t('none')}
                      </div>
                      <div className="min-w-0">
                        {isEditing ? (
                          <CronScheduleControl value={draft.schedule} onChange={(schedule) => updateDraft(depot.id, { schedule })} />
                        ) : (
                          <div className="flex h-8 min-w-0 items-center text-sm text-muted-foreground" title={savedDraft.schedule || t('manualOnly')}>
                            <span className="truncate">{scheduleDisplayLabel(savedDraft.schedule, t)}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {isEditing ? (
                          <>
                            <Button
                              aria-label={`${t('save')} ${depot.name}`}
                              size="icon-sm"
                              variant="ghost"
                              disabled={saving || !rowDirty || !rowValid}
                              title={`${t('save')} ${depot.name}`}
                              onClick={() => void saveDraft(depot)}
                            >
                              <Check />
                            </Button>
                            <Button
                              aria-label={`${t('cancel')} ${depot.name}`}
                              size="icon-sm"
                              variant="ghost"
                              disabled={saving}
                              title={`${t('cancel')} ${depot.name}`}
                              onClick={() => cancelEdit(depot)}
                            >
                              <X />
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              aria-label={t('editLabel', { label: depot.name })}
                              size="icon-sm"
                              variant="ghost"
                              disabled={saving}
                              title={t('editLabel', { label: depot.name })}
                              onClick={() => editDepot(depot)}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              aria-label={t('removeLabel', { label: depot.name })}
                              size="icon-sm"
                              variant="ghost"
                              disabled={saving || !savedDraft.schedule.trim()}
                              title={t('removeLabel', { label: depot.name })}
                              onClick={() => void clearSchedule(depot)}
                            >
                              <CircleX />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
              ) : null}
            </>
          )}
        </CardContent>
      ) : null}
    </Card>
  )
}

function depotPayload(depot: DepotSummary, draft: TransferAutomationDraft): DepotDraft {
  const schedule = draft.schedule.trim()
  return {
    name: depot.name,
    path: depot.path,
    media_type: depot.media_type,
    enabled: schedule ? true : depot.enabled ?? true,
    policy: {
      ...depot.policy,
      trigger: schedule ? 'scheduled' : 'manual',
      schedule: schedule || null,
    },
  }
}
