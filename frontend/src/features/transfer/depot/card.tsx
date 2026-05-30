import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ChevronDown, ChevronUp, ScanLine, X } from 'lucide-react'
import { mediaTypeLabel, statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { TransferJob, TransferRule } from '@/api/types'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { PathRoute } from '@/components/filesystem/PathRoute'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notifyError } from '@/lib/notifications'
import { useDepot, useDepotCandidateActions } from '@/features/depot/api'
import { useTransferActions } from '../api'
import { ReturnDialog } from '../return/dialog'
import { parentPath, returnRequestForTarget, type ReturnTarget } from '../return/model'
import { isActiveTransfer, toggleSet } from '../job/model'
import { TransferProgressLine } from '../job/progress'
import { DepotCandidateList } from './list'
import { DepotFilesystemEntryDialog, type DepotFilesystemEntryTarget } from './dialog'
import { buildDepotTree, depotOptionIncrementalLabel, depotSelectionSummary, formatDepotBytes, isActionableDepotCandidate, previewTransferRelativePath, type DepotGroupView } from './model'

export function DepotTransferCard({
  depot,
  jobs,
  transferRule,
  onRemove,
}: {
  depot: DepotGroupView
  jobs: TransferJob[]
  transferRule?: TransferRule | null
  onRemove: (depotId: string) => void
}) {
  const { t } = useI18n()
  const depotDetail = useDepot(depot.id)
  const transferActions = useTransferActions()
  const depotActions = useDepotCandidateActions()
  const [cardExpanded, setCardExpanded] = useState(false)
  const [ignoredCandidateIds, setIgnoredCandidateIds] = useState<Set<string>>(() => new Set())
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const [dialogTarget, setDialogTarget] = useState<DepotFilesystemEntryTarget | null>(null)
  const [returnTarget, setReturnTarget] = useState<ReturnTarget | null>(null)
  const depotTree = buildDepotTree(depotDetail.data)
  const candidates = depotTree?.candidates ?? []
  const actionableCandidates = useMemo(() => candidates.filter(isActionableDepotCandidate), [candidates])
  const candidateIds = actionableCandidates.map((candidate) => candidate.id)
  const candidateIdsKey = candidateIds.join('|')
  const acceptedCandidateIds = useMemo(
    () => candidateIds.filter((candidateId) => !ignoredCandidateIds.has(candidateId)),
    [candidateIdsKey, ignoredCandidateIds],
  )
  const acceptedCandidateIdSet = useMemo(() => new Set(acceptedCandidateIds), [acceptedCandidateIds])
  const selectedSummary = useMemo(() => depotSelectionSummary(actionableCandidates, acceptedCandidateIdSet), [actionableCandidates, acceptedCandidateIdSet])
  const selectedBlockedCount = selectedSummary.selected.filter((candidate) => candidate.blocked_reason).length
  const activeJob = jobs.find((job) => job.depot_id === depot.id && isActiveTransfer(job))
  const latestJob = jobs.find((job) => job.depot_id === depot.id)
  const mutationJob = transferActions.transferDepot.data?.depot_id === depot.id && isActiveTransfer(transferActions.transferDepot.data) ? transferActions.transferDepot.data : null
  const progressJob = activeJob ?? mutationJob
  const failedJob = latestJob?.status === 'failed' ? latestJob : depot.lastFailure
  const transferPending = transferActions.transferDepot.isPending
  const returnPending = depotActions.returnItems.isPending
  const cancelPending = transferActions.cancelTransferJob.isPending
  const actionPending = transferPending || cancelPending
  const canTransfer = depot.enabled && acceptedCandidateIds.length > 0 && !activeJob && !actionPending
  const resolveModeLabel = depotOptionIncrementalLabel(depot, t)
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  useEffect(() => {
    const validCandidateIds = new Set(candidateIds)
    setIgnoredCandidateIds((current) => new Set([...current].filter((id) => validCandidateIds.has(id))))
    setExpanded((current) => new Set([...current].filter((id) => validCandidateIds.has(id))))
  }, [candidateIdsKey])

  const transferDepot = () => {
    transferActions.transferDepot.mutate(
      { depotId: depot.id, data: { requested_by: 'web-ui-transfer', candidate_ids: acceptedCandidateIds } },
      { onError: onActionError },
    )
  }

  const cancelCard = () => {
    if (!activeJob) {
      onRemove(depot.id)
      return
    }
    transferActions.cancelTransferJob.mutate(activeJob.id, { onError: onActionError })
  }

  const returnItems = (destinationRoot: string) => {
    if (!returnTarget) return
    depotActions.returnItems.mutate(
      { depotId: depot.id, data: returnRequestForTarget(returnTarget, destinationRoot) },
      {
        onSuccess: () => {
          setReturnTarget(null)
        },
        onError: onActionError,
      },
    )
  }

  const scanCard = () => void depotDetail.refetch()
  return (
    <Card>
      <CardHeader>
        <div className="grid gap-3">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
            <div className="min-w-0">
              <CardTitle className="flex flex-wrap items-center gap-2">
                <Button
                  aria-label={cardExpanded ? t('collapseLabel', { label: depot.name }) : t('expandLabel', { label: depot.name })}
                  aria-expanded={cardExpanded}
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => setCardExpanded((current) => !current)}
                >
                  {cardExpanded ? <ChevronUp /> : <ChevronDown />}
                </Button>
                <span className="min-w-0 truncate font-medium" title={depot.name}>{depot.name}</span>
                <Badge color={badgeColorForMediaType(depot.mediaType)}>{mediaTypeLabel(t, depot.mediaType)}</Badge>
                {resolveModeLabel ? <Badge>{resolveModeLabel}</Badge> : null}
                <span className="ml-9 flex basis-[calc(100%-2.25rem)] flex-wrap gap-1.5 sm:ml-0 sm:basis-auto sm:gap-2">
                  <Badge tone={selectedSummary.selected.length ? 'warning' : undefined}>
                    {t('countAccepted', { count: selectedSummary.selected.length })}
                  </Badge>
                  <Badge>{t('countFiles', { count: selectedSummary.files })}</Badge>
                  <Badge>{formatDepotBytes(selectedSummary.size)}</Badge>
                  {selectedBlockedCount ? <Badge tone="danger">{t('countBlocked', { count: selectedBlockedCount })}</Badge> : null}
                  {activeJob ? <Badge tone="warning">{statusLabel(t, activeJob.status)}</Badge> : null}
                </span>
              </CardTitle>
              <CardDescription className="mt-2 ml-9">
                <PathRoute
                  className="w-full flex-nowrap sm:w-auto sm:flex-wrap"
                  pathClassName="truncate sm:overflow-visible sm:whitespace-normal sm:break-all"
                  source={depot.depotPath}
                  target={depot.libraryPath}
                />
              </CardDescription>
              {failedJob ? <div className="mt-1 ml-9 break-all text-sm text-destructive">{failedJob.message ?? failedJob.status}</div> : null}
            </div>
            <Button
              aria-label={t('cancel')}
              onClick={cancelCard}
              disabled={cancelPending || activeJob?.status === 'cancelling'}
              className="w-8 px-0 sm:w-28 sm:px-2.5"
              variant="ghost"
            >
              <X />
              <span className="sr-only sm:not-sr-only">{t('cancel')}</span>
            </Button>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              className="w-28 border-sky-500/40 bg-sky-500/10 text-sky-700 hover:bg-sky-500/20 disabled:border-border disabled:bg-muted disabled:text-muted-foreground dark:text-sky-200"
              onClick={scanCard}
              disabled={depotDetail.isFetching || Boolean(activeJob)}
              variant="outline"
            >
              <ScanLine data-icon="inline-start" />
              {t('scan')}
            </Button>
            <Button
              className="w-28 bg-emerald-500 text-emerald-950 hover:bg-emerald-400 disabled:bg-muted disabled:text-muted-foreground"
              variant="primary"
              onClick={transferDepot}
              disabled={!canTransfer}
            >
              <ArrowRight data-icon="inline-start" />
              {t('transfer')}
            </Button>
          </div>
        </div>
        {progressJob ? <TransferProgressLine status={progressJob.status} /> : null}
      </CardHeader>

      {cardExpanded ? (
        <CardContent className="overflow-auto">
          <div className="flex flex-col gap-3">
            {mutationJob ? (
              <div className="text-sm text-muted-foreground">{t('queuedDepot', { depotId: mutationJob.depot_id })}</div>
            ) : null}
            <AsyncFrame loading={depotDetail.isLoading} error={depotDetail.error}>
              <DepotCandidateList
                candidates={candidates}
                pendingCount={depotTree?.pendingCount ?? depot.pendingCount}
                selectedIds={acceptedCandidateIdSet}
                expandedIds={expanded}
                fetching={depotDetail.isFetching}
                selectionMode="decision"
                selectionDisabled={() => Boolean(activeJob) || actionPending}
                showHeader={false}
                showCandidateIcon={false}
                candidateListClassName="gap-4"
                onRefresh={() => void depotDetail.refetch()}
                onToggleSelected={(candidateId, checked) => setIgnoredCandidateIds((current) => toggleSet(current, candidateId, !checked))}
                onToggleExpanded={(candidateId) => setExpanded((current) => toggleSet(current, candidateId, !current.has(candidateId)))}
                onCandidateDetails={(candidate) => setDialogTarget({ type: 'candidate', candidate })}
                onFileDetails={(candidate, file) => setDialogTarget({ type: 'file', candidate, file })}
                onCandidateReturn={(candidate) => setReturnTarget({ type: 'candidate', candidate })}
                onFileReturn={(candidate, file) => setReturnTarget({ type: 'file', candidate, file })}
                candidateReturnDisabled={(candidate) => returnPending || Boolean(activeJob) || Boolean(candidate.blocked_reason)}
                fileReturnDisabled={(_candidate, file) => returnPending || Boolean(activeJob) || Boolean(file.blocked_reason)}
                getFileTargetPath={(_candidate, file) => previewTransferRelativePath(file.relative_path, transferRule)}
              />
            </AsyncFrame>
          </div>
        </CardContent>
      ) : null}
      <DepotFilesystemEntryDialog
        open={Boolean(dialogTarget)}
        onOpenChange={(open) => {
          if (!open) setDialogTarget(null)
        }}
        depotId={depot.id}
        target={dialogTarget}
      />
      <ReturnDialog
        open={Boolean(returnTarget)}
        title={t('chooseSendBackDestination')}
        initialPath={parentPath(depot.depotPath)}
        confirmLabel={t('sendBackHere')}
        onOpenChange={(open) => {
          if (!open) setReturnTarget(null)
        }}
        onSelect={returnItems}
      />
    </Card>
  )
}
