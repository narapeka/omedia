import { useEffect, useMemo, useState } from 'react'
import { Check, CircleX, Pencil, X } from 'lucide-react'
import type {
  OrganizeRule,
  Origin,
  OriginSummary,
  DepotSummary,
  WatchSettingsChild,
} from '@/api/types'
import { mediaTypeLabel, statusLabel as translatedStatusLabel, type TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { SelectControl } from '@/components/common/SelectControl'
import { notifyError } from '@/lib/notifications'
import { useIs2xl } from '@/lib/useMediaQuery'
import { useOriginActions } from '@/features/origin/api'

type WatchOriginDraft = {
  mediaType: Origin['media_type'] | ''
  organizeRuleId: string
  targetDepotId: string
}

const EMPTY_RULE_OPTIONS = [{ value: '', label: '-' }]

const WATCH_CHILD_GRID =
  'md:grid-cols-[minmax(0,3fr)_minmax(0,0.7fr)_minmax(0,2.05fr)_minmax(0,1.55fr)_minmax(1rem,0.55fr)_minmax(0,0.9fr)_6rem]'

export function WatchChildTable({
  children,
  origins,
  depots,
  organizeRules,
  watchRunning,
}: {
  children: WatchSettingsChild[]
  origins: OriginSummary[]
  depots: DepotSummary[]
  organizeRules: OrganizeRule[]
  watchRunning: boolean
}) {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  const actions = useOriginActions()
  const mediaTypeOptions = useMemo(
    () => [
      { value: '', label: '-' },
      { value: 'movie', label: t('mediaMovie') },
      { value: 'tv', label: t('mediaTv') },
    ],
    [t],
  )
  const originsById = useMemo(() => new Map(origins.map((origin) => [origin.id, origin])), [origins])
  const ruleOptions = useMemo(
    () => [{ value: '', label: t('none') }, ...organizeRules.map((rule) => ({ value: rule.id, label: rule.name }))],
    [organizeRules, t],
  )
  const initialDrafts = useMemo(
    () =>
      Object.fromEntries(
        children.map((child) => {
          const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
          return [child.path, draftFromOrigin(origin)]
        }),
      ),
    [children, originsById, depots],
  )
  const [drafts, setDrafts] = useState<Record<string, WatchOriginDraft>>(() => initialDrafts)
  const [editingPath, setEditingPath] = useState<string | null>(null)

  useEffect(() => {
    setDrafts(initialDrafts)
  }, [initialDrafts])

  const saving = actions.createOrigin.isPending || actions.saveOrigin.isPending || actions.deleteOrigin.isPending
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  if (children.length === 0) {
    return <div className="px-4 py-6 text-sm text-muted-foreground">{t('noDirectChildren')}</div>
  }

  const updateDraft = (child: WatchSettingsChild, patch: Partial<WatchOriginDraft>) => {
    setDrafts((current) => {
      const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
      return {
        ...current,
        [child.path]: {
          ...(current[child.path] ?? draftFromOrigin(origin)),
          ...patch,
        },
      }
    })
  }

  const editChild = (child: WatchSettingsChild) => {
    const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
    setDrafts((current) => ({
      ...current,
      [child.path]: draftFromOrigin(origin),
    }))
    setEditingPath(child.path)
  }

  const cancelEdit = (child: WatchSettingsChild) => {
    setDrafts((current) => ({
      ...current,
      [child.path]: initialDrafts[child.path],
    }))
    setEditingPath(null)
  }

  const saveDraft = async (child: WatchSettingsChild) => {
    const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
    const draft = drafts[child.path] ?? draftFromOrigin(origin)
    if (watchDraftError(draft) || !isWatchDraftDirty(initialDrafts[child.path], draft)) return
    try {
      const payload = originPayload(child, origin, draft)
      if (origin) await actions.saveOrigin.mutateAsync({ originId: origin.id, data: payload })
      else await actions.createOrigin.mutateAsync(payload)
      setEditingPath(null)
    } catch (error) {
      onActionError(error)
    }
  }

  const deleteDraft = async (child: WatchSettingsChild) => {
    const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
    if (!origin) return
    try {
      await actions.deleteOrigin.mutateAsync(origin.id)
      setEditingPath((current) => (current === child.path ? null : current))
    } catch (error) {
      onActionError(error)
    }
  }

  return (
    <>
      <div className="px-4">
        {!is2xl ? (
        <div className="flex flex-col gap-3">
          {children.map((child) => {
            const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
            const draft = drafts[child.path] ?? draftFromOrigin(origin)
            const isEditing = editingPath === child.path
            const displayDraft = isEditing ? draft : initialDrafts[child.path]
            const depotOptions = depotOptionsForType(depots, draft.mediaType)
            const isMissing = child.status === 'missing'
            const rowLabel = origin?.name ?? child.name
            const rowDirty = isWatchDraftDirty(initialDrafts[child.path], draft)
            const rowValid = !watchDraftError(draft)
            const targetDepotDisabled = !isEditing || isMissing || saving || !draft.mediaType || depotOptions.length <= 1
            const ruleDisabled = !isEditing || isMissing || saving || !draft.mediaType
            const targetDepot = depots.find((depot) => depot.id === displayDraft.targetDepotId)
            const organizeRule = organizeRules.find((rule) => rule.id === displayDraft.organizeRuleId)
            return (
              <div key={`${child.status}-${child.path}:card`} className="rounded-lg border bg-muted/20 p-3">
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium" title={origin?.name ?? child.name}>{origin?.name ?? child.name}</div>
                    <div className="truncate text-xs text-muted-foreground" title={child.path}>{child.path}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {isEditing ? (
                      <>
                        <Button
                          aria-label={`${t('save')} ${rowLabel}`}
                          size="icon-sm"
                          variant="ghost"
                          disabled={saving || !rowDirty || !rowValid}
                          title={`${t('save')} ${rowLabel}`}
                          onClick={() => void saveDraft(child)}
                        >
                          <Check />
                        </Button>
                        <Button
                          aria-label={`${t('cancel')} ${rowLabel}`}
                          size="icon-sm"
                          variant="ghost"
                          disabled={saving}
                          title={`${t('cancel')} ${rowLabel}`}
                          onClick={() => cancelEdit(child)}
                        >
                          <X />
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          aria-label={t('editLabel', { label: rowLabel })}
                          size="icon-sm"
                          variant="ghost"
                          disabled={saving}
                          title={t('editLabel', { label: rowLabel })}
                          onClick={() => editChild(child)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          aria-label={t('removeLabel', { label: rowLabel })}
                          size="icon-sm"
                          variant="ghost"
                          disabled={saving || !origin}
                          title={t('removeLabel', { label: rowLabel })}
                          onClick={() => void deleteDraft(child)}
                        >
                          <CircleX />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                <div className="mt-3 grid gap-2 text-sm">
                  <div className="grid min-w-0 grid-cols-[5rem_6rem_minmax(0,1fr)] items-center gap-2 sm:grid-cols-[5rem_8.5rem_minmax(0,1fr)]">
                    <span className="text-muted-foreground">{t('targetDepotColumn')}</span>
                    {isEditing ? (
                      <>
                        <SelectControl
                          aria-label={`${child.name} ${t('mediaType')}`}
                          value={displayDraft.mediaType}
                          options={mediaTypeOptions}
                          triggerClassName="w-24 sm:w-full"
                          disabled={!isEditing || isMissing || saving}
                          onValueChange={(mediaType) => {
                            const nextMediaType = mediaType as WatchOriginDraft['mediaType']
                            const currentDepot = draft.targetDepotId ? depots.find((depot) => depot.id === draft.targetDepotId) : undefined
                            const nextTargetDepotId = currentDepot?.media_type === nextMediaType ? draft.targetDepotId : ''
                            updateDraft(child, { mediaType: nextMediaType, targetDepotId: nextTargetDepotId, organizeRuleId: nextMediaType ? draft.organizeRuleId : '' })
                          }}
                        />
                        <div className="min-w-0">
                          <SelectControl
                            aria-label={`${child.name} ${t('targetDepot')}`}
                            value={displayDraft.targetDepotId}
                            options={depotOptions}
                            disabled={targetDepotDisabled}
                            onValueChange={(targetDepotId) => updateDraft(child, { targetDepotId })}
                          />
                        </div>
                      </>
                    ) : (
                      <>
                        {displayDraft.mediaType ? <Badge color={badgeColorForMediaType(displayDraft.mediaType)}>{mediaTypeLabel(t, displayDraft.mediaType)}</Badge> : <span className="text-muted-foreground">-</span>}
                        <span className="min-w-0 truncate font-medium text-muted-foreground" title={targetDepot?.name ?? '-'}>
                          {targetDepot?.name ?? '-'}
                        </span>
                      </>
                    )}
                  </div>
                  <div className="grid min-w-0 grid-cols-[5rem_minmax(0,1fr)_auto] items-center gap-2">
                    <span className="text-muted-foreground">{t('rule')}</span>
                    {isEditing ? (
                      <div className="min-w-0">
                        <SelectControl
                          aria-label={`${child.name} ${t('organizeRule')}`}
                          value={displayDraft.organizeRuleId}
                          options={displayDraft.mediaType ? ruleOptions : EMPTY_RULE_OPTIONS}
                          disabled={ruleDisabled}
                          onValueChange={(organizeRuleId) => updateDraft(child, { organizeRuleId })}
                        />
                      </div>
                    ) : (
                      <span className="min-w-0 truncate font-medium text-muted-foreground" title={organizeRule?.name ?? t('none')}>
                        {organizeRule?.name ?? t('none')}
                      </span>
                    )}
                    <Badge tone={statusTone(child.status)}>{watchStatusLabel(child.status, t, watchRunning)}</Badge>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        ) : null}

        {is2xl ? (
        <div className="overflow-auto">
          <div className="divide-y">
          <div className={`grid min-h-10 items-center gap-y-3 gap-x-6 px-2 text-sm font-medium whitespace-nowrap text-foreground xl:gap-x-10 ${WATCH_CHILD_GRID}`}>
            <span>{t('folderColumn')}</span>
            <span>{t('type')}</span>
            <span>{t('targetDepotColumn')}</span>
            <span>{t('rule')}</span>
            <span aria-hidden="true" />
            <span>{t('status')}</span>
            <span>{t('actions')}</span>
          </div>
          {children.map((child) => {
            const origin = child.origin_id ? originsById.get(child.origin_id) : undefined
            const draft = drafts[child.path] ?? draftFromOrigin(origin)
            const isEditing = editingPath === child.path
            const displayDraft = isEditing ? draft : initialDrafts[child.path]
            const depotOptions = depotOptionsForType(depots, draft.mediaType)
            const isMissing = child.status === 'missing'
            const rowLabel = origin?.name ?? child.name
            const rowDirty = isWatchDraftDirty(initialDrafts[child.path], draft)
            const rowValid = !watchDraftError(draft)
            const targetDepotDisabled = !isEditing || isMissing || saving || !draft.mediaType || depotOptions.length <= 1
            const ruleDisabled = !isEditing || isMissing || saving || !draft.mediaType
            return (
              <div key={`${child.status}-${child.path}`} className={`grid gap-y-3 gap-x-6 px-2 py-3 md:items-center xl:gap-x-10 ${WATCH_CHILD_GRID}`}>
                <div className="min-w-0">
                  <div className="truncate font-medium" title={origin?.name ?? child.name}>{origin?.name ?? child.name}</div>
                  <div className="truncate text-xs text-muted-foreground" title={child.path}>{child.path}</div>
                </div>
                <div>
                  <SelectControl
                    aria-label={`${child.name} ${t('mediaType')}`}
                    value={displayDraft.mediaType}
                    options={mediaTypeOptions}
                    disabled={!isEditing || isMissing || saving}
                    onValueChange={(mediaType) => {
                      const nextMediaType = mediaType as WatchOriginDraft['mediaType']
                      const currentDepot = draft.targetDepotId ? depots.find((depot) => depot.id === draft.targetDepotId) : undefined
                      const nextTargetDepotId = currentDepot?.media_type === nextMediaType ? draft.targetDepotId : ''
                      updateDraft(child, { mediaType: nextMediaType, targetDepotId: nextTargetDepotId, organizeRuleId: nextMediaType ? draft.organizeRuleId : '' })
                    }}
                  />
                </div>
                <div className="min-w-0">
                  <SelectControl
                    aria-label={`${child.name} ${t('targetDepot')}`}
                    value={displayDraft.targetDepotId}
                    options={depotOptions}
                    disabled={targetDepotDisabled}
                    onValueChange={(targetDepotId) => updateDraft(child, { targetDepotId })}
                  />
                </div>
                <div>
                  <SelectControl
                    aria-label={`${child.name} ${t('organizeRule')}`}
                    value={displayDraft.organizeRuleId}
                    options={displayDraft.mediaType ? ruleOptions : EMPTY_RULE_OPTIONS}
                    disabled={ruleDisabled}
                    onValueChange={(organizeRuleId) => updateDraft(child, { organizeRuleId })}
                  />
                </div>
                <div aria-hidden="true" />
                <div>
                  <Badge tone={statusTone(child.status)}>{watchStatusLabel(child.status, t, watchRunning)}</Badge>
                </div>
                <div className="flex items-center gap-1.5">
                  {isEditing ? (
                    <>
                      <Button
                        aria-label={`${t('save')} ${rowLabel}`}
                        size="icon-sm"
                        variant="ghost"
                        disabled={saving || !rowDirty || !rowValid}
                        title={`${t('save')} ${rowLabel}`}
                        onClick={() => void saveDraft(child)}
                      >
                        <Check />
                      </Button>
                      <Button
                        aria-label={`${t('cancel')} ${rowLabel}`}
                        size="icon-sm"
                        variant="ghost"
                        disabled={saving}
                        title={`${t('cancel')} ${rowLabel}`}
                        onClick={() => cancelEdit(child)}
                      >
                        <X />
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        aria-label={t('editLabel', { label: rowLabel })}
                        size="icon-sm"
                        variant="ghost"
                        disabled={saving}
                        title={t('editLabel', { label: rowLabel })}
                        onClick={() => editChild(child)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        aria-label={t('removeLabel', { label: rowLabel })}
                        size="icon-sm"
                        variant="ghost"
                        disabled={saving || !origin}
                        title={t('removeLabel', { label: rowLabel })}
                        onClick={() => void deleteDraft(child)}
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
        </div>
        ) : null}
      </div>
      {depots.length === 0 ? <div className="border-t px-4 py-3 text-sm text-muted-foreground">{t('createDepotBeforeAutoOrganize')}</div> : null}
    </>
  )
}

function draftFromOrigin(origin: OriginSummary | undefined): WatchOriginDraft {
  if (!origin) {
    return {
      mediaType: '',
      organizeRuleId: '',
      targetDepotId: '',
    }
  }

  const mediaType = origin.media_type
  return {
    mediaType,
    organizeRuleId: origin.policy.organize_rule_id ?? '',
    targetDepotId: origin.policy.target_depot_id ?? '',
  }
}

function isWatchDraftDirty(initial: WatchOriginDraft | undefined, draft: WatchOriginDraft | undefined) {
  if (!initial || !draft) return false
  return (
    initial.mediaType !== draft.mediaType ||
    initial.organizeRuleId !== draft.organizeRuleId ||
    initial.targetDepotId !== draft.targetDepotId
  )
}

function watchDraftError(draft: WatchOriginDraft | undefined) {
  return !draft?.mediaType || !draft.targetDepotId
}

function depotOptionsForType(depots: DepotSummary[], mediaType: WatchOriginDraft['mediaType']) {
  return [
    { value: '', label: '-', textValue: '-' },
    ...depots
      .filter((depot) => depot.media_type === mediaType)
      .map((depot) => ({
        value: depot.id,
        label: depot.name,
        textValue: `${depot.name} ${depot.path} ${depot.media_type}`,
      })),
  ]
}

function originPayload(
  child: WatchSettingsChild,
  origin: OriginSummary | undefined,
  values: WatchOriginDraft,
): Omit<Origin, 'id'> {
  return {
    name: origin?.name ?? child.name,
    path: origin?.path ?? child.path,
    media_type: values.mediaType as Origin['media_type'],
    trigger: 'watch',
    enabled: true,
    policy: {
      target_depot_id: values.targetDepotId,
      organize_rule_id: values.organizeRuleId || null,
    },
  }
}

function watchStatusLabel(status: string, t: TFunction, watchRunning: boolean) {
  if (status === 'configured' && !watchRunning) return t('configured')
  return translatedStatusLabel(t, status) || status
}

function statusTone(status: string) {
  if (status === 'configured') return 'success'
  if (status === 'missing') return 'danger'
  if (status === 'disabled') return 'warning'
  return undefined
}
