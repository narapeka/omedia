import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Play, ScanLine, Search, X } from 'lucide-react'
import { fileCountLabel, mediaTypeLabel, statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { OrganizeSession, OriginSummary } from '@/api/types'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { PathRoute } from '@/components/filesystem/PathRoute'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notifyError } from '@/lib/notifications'
import { useSessionActions } from '../api'
import { formatBytes } from '../display'
import { SourceCandidateList } from '../candidate/list'
import { SessionProgressLine } from './progress'
import { organizeAcceptedSummary, originSessionTitle, scannedSelectionSummary } from './summary'

export function SessionCard({
  session,
  origins,
  depotNameById,
}: {
  session: OrganizeSession
  origins: OriginSummary[]
  depotNameById: Map<string, string>
}) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const [expanded, setExpanded] = useState(false)
  const reviewCandidates = session.review_candidates
  const acceptedSummary = useMemo(
    () => (session.state === 'scanned' ? scannedSelectionSummary(reviewCandidates) : organizeAcceptedSummary(reviewCandidates)),
    [reviewCandidates, session.state],
  )
  const actionPending =
    actions.cancelSession.isPending ||
    actions.runIdentifyPhase.isPending ||
    actions.restartScanPhase.isPending ||
    actions.organizeSession.isPending
  const canScan = !actionPending && (session.state === 'scanned' || session.state === 'identified')
  const canIdentify = session.state === 'scanned' && acceptedSummary.sources > 0
  const canOrganize = session.state === 'identified' && acceptedSummary.planItems > 0
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))
  const sessionTitle = session.kind === 'origin' ? originSessionTitle(session, origins) : t('adHocSessionTitle')
  const identifyPending = actions.runIdentifyPhase.isPending && actions.runIdentifyPhase.variables === session.id
  const scanPending = actions.restartScanPhase.isPending && actions.restartScanPhase.variables === session.id
  const organizingPending = actions.organizeSession.isPending && actions.organizeSession.variables === session.id
  const progressState =
    session.state === 'scanning' || scanPending
      ? 'scanning'
      : session.state === 'identifying' || identifyPending
        ? 'identifying'
        : session.state === 'organizing' || organizingPending
          ? 'organizing'
          : null

  return (
    <Card>
      <CardHeader>
        <div className="grid gap-3">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
            <div className="min-w-0">
              <CardTitle className="flex flex-wrap items-center gap-2">
                <Button
                  aria-label={expanded ? t('collapseLabel', { label: sessionTitle }) : t('expandLabel', { label: sessionTitle })}
                  aria-expanded={expanded}
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => setExpanded((current) => !current)}
                >
                  {expanded ? <ChevronUp /> : <ChevronDown />}
                </Button>
                <span className="min-w-0 max-w-full truncate sm:overflow-visible sm:whitespace-normal">{sessionTitle}</span>
                {session.state !== 'scanned' && session.state !== 'identified' ? <Badge>{statusLabel(t, session.state)}</Badge> : null}
                <Badge color={badgeColorForMediaType(session.media_type)}>{mediaTypeLabel(t, session.media_type)}</Badge>
                <span className="ml-9 flex basis-[calc(100%-2.25rem)] flex-wrap gap-1.5 sm:ml-0 sm:basis-auto sm:gap-2">
                  <Badge tone={acceptedSummary.sources ? 'warning' : undefined}>
                    {t('countAccepted', { count: acceptedSummary.sources })}
                  </Badge>
                  <Badge>{fileCountLabel(t, acceptedSummary.files)}</Badge>
                  <Badge>{formatBytes(acceptedSummary.size)}</Badge>
                </span>
              </CardTitle>
              <CardDescription className="mt-2 ml-9">
                <PathRoute
                  className="w-full flex-nowrap sm:w-auto sm:flex-wrap"
                  pathClassName="truncate sm:overflow-visible sm:whitespace-normal sm:break-all"
                  source={session.path}
                  target={depotNameById.get(session.policy.target_depot_id) ?? session.policy.target_depot_id}
                />
              </CardDescription>
            </div>
            <Button
              aria-label={t('cancel')}
              onClick={() => actions.cancelSession.mutate(session.id, { onError: onActionError })}
              disabled={actions.cancelSession.isPending}
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
              variant="outline"
              onClick={() => actions.restartScanPhase.mutate(session.id, { onError: onActionError })}
              disabled={!canScan}
            >
              <ScanLine data-icon="inline-start" />
              {t('scan')}
            </Button>
            <Button
              className="w-28 border-amber-500/40 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 disabled:border-border disabled:bg-muted disabled:text-muted-foreground dark:text-amber-200"
              variant="outline"
              onClick={() => actions.runIdentifyPhase.mutate(session.id, { onError: onActionError })}
              disabled={!canIdentify || actionPending}
            >
              <Search data-icon="inline-start" />
              {t('identify')}
            </Button>
            <Button
              className="w-28 bg-emerald-500 text-emerald-950 hover:bg-emerald-400 disabled:bg-muted disabled:text-muted-foreground"
              variant="primary"
              onClick={() => actions.organizeSession.mutate(session.id, { onError: onActionError })}
              disabled={!canOrganize || actionPending}
            >
              <Play data-icon="inline-start" />
              {t('organize')}
            </Button>
          </div>
        </div>
        {progressState ? <SessionProgressLine state={progressState} /> : null}
      </CardHeader>
      {expanded ? (
        <CardContent className="overflow-auto">
          <SourceCandidateList
            sourceCandidates={reviewCandidates}
            sessionId={session.id}
            mediaType={session.media_type}
            canReview={session.state === 'identified'}
            canSelectForIdentify={session.state === 'scanned'}
            canInspectSource={session.state === 'scanned' || session.state === 'identified'}
            canMutateSource={session.state === 'scanned'}
            showModifiedTime={session.state === 'scanned'}
          />
        </CardContent>
      ) : null}
    </Card>
  )
}
