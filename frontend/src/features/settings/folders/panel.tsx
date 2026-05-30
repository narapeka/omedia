import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { DepotDraft as ApiDepotDraft, DepotSummary, OriginDraft as ApiOriginDraft, OriginSummary } from '@/api/types'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { ConfirmDialog, type ConfirmDialogState } from '@/components/common/ConfirmDialog'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useDepots, useDepotConfigActions } from '@/features/depot/api'
import { useOrganizeSessions } from '@/features/organize/api'
import { useOrigins, useOriginActions } from '@/features/origin/api'
import { isManualOrigin } from '@/features/origin/model'
import { useOrganizeRules, useTransferRules } from '@/features/rules/api'
import { useTransferJobs } from '@/features/transfer/api'
import { notifyError } from '@/lib/notifications'
import { DepotDialog } from './depot'
import { emptyDepotDraft, emptyOriginDraftForDepot, depotToDraft, originToDraftForDepot, type DepotDraft, type MediaType, type OriginDraft } from './draft'
import { DepotFolderSection } from './section'
import { assessDepotRemoval, assessOriginRemoval, sortDepotsForCards, validateDepotDraft, validateOriginDraft } from './validate'

export function FoldersPanel() {
  const { t } = useI18n()
  const origins = useOrigins()
  const depots = useDepots()
  const organizeRules = useOrganizeRules()
  const organizeSessions = useOrganizeSessions()
  const transferJobs = useTransferJobs()
  const transferRules = useTransferRules()
  const originActions = useOriginActions()
  const depotActions = useDepotConfigActions()
  const actions = { ...originActions, ...depotActions }
  const [originDraft, setOriginDraft] = useState<OriginDraft | null>(null)
  const [depotDraft, setDepotDraft] = useState<DepotDraft | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmDialogState | null>(null)
  const [message, setMessage] = useState('')
  const [expandedDepotIds, setExpandedDepotIds] = useState<Set<string>>(() => new Set())
  const manualOrigins = useMemo(() => (origins.data ?? []).filter(isManualOrigin), [origins.data])
  const originsByDepotId = useMemo(() => {
    const grouped = new Map<string, OriginSummary[]>()
    for (const origin of manualOrigins) {
      const list = grouped.get(origin.policy.target_depot_id) ?? []
      list.push(origin)
      grouped.set(origin.policy.target_depot_id, list)
    }
    return grouped
  }, [manualOrigins])
  const originUsersByDepotId = useMemo(() => {
    const grouped = new Map<string, OriginSummary[]>()
    for (const origin of origins.data ?? []) {
      const list = grouped.get(origin.policy.target_depot_id) ?? []
      list.push(origin)
      grouped.set(origin.policy.target_depot_id, list)
    }
    return grouped
  }, [origins.data])
  const sortedDepots = useMemo(() => sortDepotsForCards(depots.data ?? []), [depots.data])
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  useEffect(() => {
    setExpandedDepotIds((current) => {
      const knownIds = new Set(sortedDepots.map((depot) => depot.id))
      const next = new Set<string>()
      for (const depot of sortedDepots) {
        if (current.has(depot.id)) next.add(depot.id)
      }
      for (const id of current) {
        if (knownIds.has(id)) next.add(id)
      }
      return next
    })
  }, [sortedDepots])

  const openOriginDraft = (nextDraft: OriginDraft) => {
    setMessage('')
    setOriginDraft(nextDraft)
  }

  const openDepotDraft = (nextDraft: DepotDraft) => {
    setMessage('')
    setDepotDraft(nextDraft)
  }

  const saveOriginDraft = async (draft: OriginDraft | null, onSaved: () => void) => {
    if (!draft) return
    const error = validateOriginDraft(draft, t)
    if (error) {
      setMessage(error)
      return
    }
    const payload: ApiOriginDraft = {
      name: draft.name.trim(),
      path: draft.path,
      media_type: draft.media_type as MediaType,
      trigger: draft.trigger,
      enabled: draft.enabled,
      policy: {
        target_depot_id: draft.target_depot_id,
        organize_rule_id: draft.organize_rule_id || null,
      },
    }
    try {
      if (draft.mode === 'edit' && draft.originalId) {
        await actions.saveOrigin.mutateAsync({ originId: draft.originalId, data: payload })
      } else {
        await actions.createOrigin.mutateAsync(payload)
      }
      onSaved()
    } catch (error) {
      onActionError(error)
    }
  }

  const saveInlineOriginDraft = () => saveOriginDraft(originDraft, () => setOriginDraft(null))

  const requestRemoveOrigin = (origin: OriginSummary) => {
    const assessment = assessOriginRemoval(origin, organizeSessions.data ?? [], t)
    setConfirmAction({
      title: t('removeOrigin'),
      description: t('removeOriginConfirm', { name: origin.name }),
      confirmLabel: t('remove'),
      destructive: true,
      confirmDisabled: !assessment.canRemove,
      notice: {
        tone: assessment.canRemove ? 'info' : 'warning',
        message: assessment.message,
      },
      onConfirm: () => actions.deleteOrigin.mutate(origin.id, { onError: onActionError }),
    })
  }

  const requestRemoveDepot = (depot: DepotSummary) => {
    const assessment = assessDepotRemoval(
      depot,
      originUsersByDepotId.get(depot.id) ?? [],
      organizeSessions.data ?? [],
      transferJobs.data ?? [],
      t,
    )
    setConfirmAction({
      title: t('removeDepot'),
      description: t('removeDepotConfirm', { name: depot.name }),
      confirmLabel: t('remove'),
      destructive: true,
      confirmDisabled: !assessment.canRemove,
      notice: {
        tone: assessment.canRemove ? 'info' : 'warning',
        message: assessment.message,
      },
      onConfirm: () => actions.deleteDepot.mutate(depot.id, { onError: onActionError }),
    })
  }

  const saveDepotDraft = async () => {
    if (!depotDraft) return
    const error = validateDepotDraft(depotDraft, t)
    if (error) {
      setMessage(error)
      return
    }
    const payload: ApiDepotDraft = {
      name: depotDraft.name.trim(),
      path: depotDraft.path,
      media_type: depotDraft.media_type as MediaType,
      resolve_mode: depotDraft.media_type === 'tv' ? depotDraft.resolveMode : 'full',
      enabled: depotDraft.enabled,
      policy: {
        target_library_path: depotDraft.target_library_path,
        trigger: depotDraft.trigger,
        transfer_rule_id: depotDraft.transfer_rule_id || null,
        schedule: depotDraft.trigger === 'scheduled' ? depotDraft.schedule : null,
      },
    }
    try {
      if (depotDraft.mode === 'edit' && depotDraft.originalId) {
        await actions.saveDepot.mutateAsync({ depotId: depotDraft.originalId, data: payload })
      } else {
        await actions.createDepot.mutateAsync(payload)
      }
      setDepotDraft(null)
    } catch (error) {
      onActionError(error)
    }
  }

  const toggleDepot = (depotId: string) => {
    setExpandedDepotIds((current) => {
      const next = new Set(current)
      if (next.has(depotId)) next.delete(depotId)
      else next.add(depotId)
      return next
    })
  }

  return (
    <AsyncFrame
      loading={origins.isLoading || depots.isLoading || organizeRules.isLoading || organizeSessions.isLoading || transferJobs.isLoading || transferRules.isLoading}
      error={origins.error || depots.error || organizeRules.error || organizeSessions.error || transferJobs.error || transferRules.error}
    >
      <Card size="sm">
        <CardHeader>
          <div className="min-w-0">
            <CardTitle className="!text-base">{t('foldersTab')}</CardTitle>
            <CardDescription>{t('pathPlanningDescription')}</CardDescription>
          </div>
          <CardAction className="flex gap-2">
            <Button onClick={() => openDepotDraft(emptyDepotDraft())}>
              <Plus data-icon="inline-start" />
              {t('createDepot')}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
          {sortedDepots.length === 0 ? (
            <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">{t('createDepotBeforeAutoOrganize')}</div>
          ) : (
            <div className="flex flex-col gap-2">
              {sortedDepots.map((depot) => {
                const sourceOrigins = originsByDepotId.get(depot.id) ?? []
                const users = originUsersByDepotId.get(depot.id) ?? []
                const expanded = expandedDepotIds.has(depot.id)
                return (
                  <DepotFolderSection
                    key={depot.id}
                    depot={depot}
                    sourceOrigins={sourceOrigins}
                    users={users}
                    expanded={expanded}
                    activeOriginDraft={originDraft?.target_depot_id === depot.id ? originDraft : null}
                    organizeRules={organizeRules.data ?? []}
                    transferRules={transferRules.data ?? []}
                    savingOrigin={actions.createOrigin.isPending || actions.saveOrigin.isPending}
                    onToggle={() => toggleDepot(depot.id)}
                    onEditDepot={() => openDepotDraft(depotToDraft(depot))}
                    onRemoveDepot={() => requestRemoveDepot(depot)}
                    onAddOrigin={() => openOriginDraft(emptyOriginDraftForDepot(depot))}
                    onEditOrigin={(origin) => openOriginDraft(originToDraftForDepot(origin, depot))}
                    onOriginDraftChange={setOriginDraft}
                    onSaveOrigin={saveInlineOriginDraft}
                    onCancelOrigin={() => setOriginDraft(null)}
                    onRemoveOrigin={requestRemoveOrigin}
                    t={t}
                  />
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
      <DepotDialog
        draft={depotDraft}
        transferRules={transferRules.data ?? []}
        saving={actions.createDepot.isPending || actions.saveDepot.isPending}
        onChange={setDepotDraft}
        onSave={saveDepotDraft}
        onClose={() => setDepotDraft(null)}
      />
      <ConfirmDialog state={confirmAction} onOpenChange={(open) => { if (!open) setConfirmAction(null) }} />
    </AsyncFrame>
  )
}
