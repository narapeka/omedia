import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Info, Pencil } from 'lucide-react'
import { confidenceLabel, statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { SourceCandidate } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { notifyError } from '@/lib/notifications'
import { useIs2xl } from '@/lib/useMediaQuery'
import { blockerText, confidenceTone, formatBytes, formatUnixSeconds, statusTone } from '../display'
import { candidateUniformPlanTag, PLAN_TAG_BADGE_CLASS } from '../tags'
import { planItemHasIssue, planItemIssueLabels } from '../evidence'
import { SourceInventoryTable } from '../source/table'
import { OrganizeSourceEntryDialog, type OrganizeSourceEntryTarget } from '../source/entry'
import { TmdbSearchDialog } from '../tmdb/dialog'
import { buildConflictReviewModel, ConflictReviewsPanel } from './conflict'
import { CandidateDecisionSwitcher, confidenceBadgeClass, sourceCandidateDecision, sourceCandidateNeedsIdentificationFix } from './decision'
import { MoveReviewWarning, TmdbIdentityLink } from './identity'

export function SourceCandidateSection({
  sourceCandidate,
  sessionId,
  mediaType,
  canReview,
  canSelectForIdentify,
  canInspectSource,
  canMutateSource,
  showModifiedTime,
}: {
  sourceCandidate: SourceCandidate
  sessionId: string
  mediaType: 'movie' | 'tv'
  canReview: boolean
  canSelectForIdentify: boolean
  canInspectSource: boolean
  canMutateSource: boolean
  showModifiedTime: boolean
}) {
  const { locale, t } = useI18n()
  const [tmdbOpen, setTmdbOpen] = useState(false)
  const [entryTarget, setEntryTarget] = useState<OrganizeSourceEntryTarget | null>(null)
  const [expanded, setExpanded] = useState(false)
  const changeLabel = mediaType === 'tv' ? t('changeShow') : t('changeMovie')
  const confidence = sourceCandidate.match?.confidence ?? 'none'
  const canSelectSource = canSelectForIdentify && sourceCandidate.status === 'active'
  const canBulkDecide = canReview && sourceCandidate.status === 'active' && sourceCandidate.plan_items.length > 0
  const canAcceptSource = canBulkDecide && Boolean(sourceCandidate.match?.acceptance.can_accept)
  const needsIdentificationFix = sourceCandidateNeedsIdentificationFix(sourceCandidate)
  const acceptBlockers = needsIdentificationFix ? '' : blockerText(sourceCandidate.match?.acceptance.blockers, t)
  const blockedMoveCount = sourceCandidate.plan_items.filter((planItem) => !planItem.acceptance.can_accept).length
  const issueMoveCount = needsIdentificationFix ? 0 : sourceCandidate.plan_items.filter(planItemHasIssue).length
  const issueLabels = needsIdentificationFix ? [] : [...new Set(sourceCandidate.plan_items.flatMap((planItem) => planItemIssueLabels(planItem, t)))]
  const candidateDecision = canSelectForIdentify ? sourceCandidate.selection_decision : sourceCandidateDecision(sourceCandidate)
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))
  const modifiedTime = sourceCandidate.modified_time
  const conflictReview = buildConflictReviewModel(sourceCandidate)
  const canRenameSourceEntry = canMutateSource && sourceCandidate.status === 'active' && !conflictReview.hasActionRequiredGroup
  const canDeleteSourceEntry = sourceCandidate.status === 'active' && (
    entryTarget?.type === 'candidate'
      ? canMutateSource || canReview
      : canMutateSource && !conflictReview.hasActionRequiredGroup
  )
  const candidateTag = candidateUniformPlanTag(sourceCandidate)
  const hasNarrowMetadataLine = Boolean(sourceCandidate.match || issueMoveCount)
  const is2xl = useIs2xl()

  useEffect(() => {
    if (!canInspectSource) setEntryTarget(null)
  }, [canInspectSource])

  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      {!is2xl ? (
      <div className="grid gap-3 border-b bg-muted/30 p-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0 pr-0 sm:pr-3">
            <div className="flex min-w-0 items-center gap-2">
              <Button
                aria-label={expanded ? t('collapseLabel', { label: sourceCandidate.display_name }) : t('expandLabel', { label: sourceCandidate.display_name })}
                aria-expanded={expanded}
                size="icon-sm"
                variant="ghost"
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? <ChevronDown /> : <ChevronRight />}
              </Button>
              <span className="min-w-0 truncate font-medium" title={sourceCandidate.display_name}>{sourceCandidate.display_name}</span>
              {sourceCandidate.status !== 'active' ? <Badge tone={statusTone(sourceCandidate.status)} className="shrink-0 whitespace-nowrap">{statusLabel(t, sourceCandidate.status)}</Badge> : null}
              {candidateTag ? <Badge className={`${PLAN_TAG_BADGE_CLASS} shrink-0 whitespace-nowrap`}>{candidateTag}</Badge> : null}
            </div>
            <div className="mt-1 ml-9 truncate text-xs text-muted-foreground" title={sourceCandidate.source_path}>{sourceCandidate.source_path}</div>
            {hasNarrowMetadataLine ? (
              <div className="mt-2 ml-9 flex min-w-0 flex-wrap items-center gap-2 overflow-visible whitespace-normal sm:flex-nowrap sm:overflow-hidden sm:whitespace-nowrap">
                {sourceCandidate.match ? (
                  <Badge tone={confidenceTone(confidence)} className={`${confidenceBadgeClass(confidence)} shrink-0`}>{confidenceLabel(t, confidence)}</Badge>
                ) : null}
                {issueMoveCount ? <MoveReviewWarning count={issueMoveCount} labels={issueLabels} /> : null}
                {sourceCandidate.match && !needsIdentificationFix ? <TmdbIdentityLink match={sourceCandidate.match} mediaType={mediaType} /> : null}
              </div>
            ) : null}
            {!canAcceptSource && acceptBlockers ? <div className="mt-1 ml-9 text-xs text-muted-foreground">{acceptBlockers}</div> : null}
            {!needsIdentificationFix && canReview && blockedMoveCount ? (
              <div className="mt-1 ml-9 text-xs text-muted-foreground">
                {t('acceptCandidateLeavesBlocked', { count: blockedMoveCount })}
              </div>
            ) : null}
            {sourceCandidate.warnings.length ? (
              <div className="mt-2 ml-9 text-xs text-destructive">{sourceCandidate.warnings.join(' | ')}</div>
            ) : null}
          </div>

          <div className="ml-9 flex w-auto flex-row flex-wrap items-center justify-start gap-2 pt-0 sm:ml-0 sm:w-40 sm:shrink-0 sm:flex-col sm:items-end sm:gap-1 sm:pt-1">
            <div className="flex flex-wrap items-center justify-start gap-2 sm:justify-end">
              <Badge className="shrink-0 whitespace-nowrap border-border/80 bg-muted/60 text-foreground">{formatBytes(sourceCandidate.total_size)}</Badge>
              <Badge className="shrink-0 whitespace-nowrap border-border/80 bg-muted/60 text-foreground">{t('countFiles', { count: sourceCandidate.file_count })}</Badge>
            </div>
            {showModifiedTime ? <span className="min-w-0 truncate text-xs text-muted-foreground sm:w-full sm:pr-2 sm:text-right">{formatUnixSeconds(modifiedTime, locale)}</span> : null}
          </div>
        </div>

        <div className="ml-9 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {canReview ? (
              <Button
                aria-label={changeLabel}
                size="sm"
                variant="outline"
                onClick={() => setTmdbOpen(true)}
                disabled={sourceCandidate.status !== 'active'}
              >
                <Pencil data-icon="inline-start" />
                {t('change')}
              </Button>
            ) : null}
            {canInspectSource ? (
              <Button
                aria-label={t('detailsLabel', { label: sourceCandidate.display_name })}
                size="sm"
                variant="outline"
                onClick={() => setEntryTarget({ type: 'candidate', sourceCandidate })}
              >
                <Info data-icon="inline-start" />
                {t('details')}
              </Button>
            ) : null}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {canReview ? (
              <CandidateDecisionSwitcher
                sourceCandidate={sourceCandidate}
                sessionId={sessionId}
                currentDecision={candidateDecision}
                canAccept={canAcceptSource}
                canIgnore={canBulkDecide}
                lowConfidence={confidence === 'low'}
                onError={onActionError}
              />
            ) : null}
            {canSelectForIdentify ? (
              <CandidateDecisionSwitcher
                sourceCandidate={sourceCandidate}
                sessionId={sessionId}
                currentDecision={candidateDecision}
                canAccept={canSelectSource}
                canIgnore={canSelectSource}
                lowConfidence={false}
                onError={onActionError}
              />
            ) : null}
          </div>
        </div>
      </div>
      ) : null}

      {is2xl ? (
      <div className="overflow-hidden border-b bg-muted/30 overflow-x-auto">
        <div className="grid min-w-[1060px] grid-cols-[50%_5.75rem_minmax(0,1fr)] items-center gap-x-0 gap-y-3 p-3">
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 pr-3">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2">
                <Button
                  aria-label={expanded ? t('collapseLabel', { label: sourceCandidate.display_name }) : t('expandLabel', { label: sourceCandidate.display_name })}
                  aria-expanded={expanded}
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => setExpanded((value) => !value)}
                >
                  {expanded ? <ChevronDown /> : <ChevronRight />}
                </Button>
                <span className="min-w-0 truncate font-medium" title={sourceCandidate.display_name}>{sourceCandidate.display_name}</span>
                {sourceCandidate.status !== 'active' ? <Badge tone={statusTone(sourceCandidate.status)}>{statusLabel(t, sourceCandidate.status)}</Badge> : null}
              </div>
              <div className="mt-1 ml-9 truncate text-xs text-muted-foreground" title={sourceCandidate.source_path}>{sourceCandidate.source_path}</div>
              {!canAcceptSource && acceptBlockers ? <div className="mt-1 text-xs text-muted-foreground">{acceptBlockers}</div> : null}
              {!needsIdentificationFix && canReview && blockedMoveCount ? (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('acceptCandidateLeavesBlocked', { count: blockedMoveCount })}
                </div>
              ) : null}
              {sourceCandidate.warnings.length ? (
                <div className="mt-2 text-xs text-destructive">{sourceCandidate.warnings.join(' | ')}</div>
              ) : null}
            </div>
            {candidateTag ? <Badge className={`${PLAN_TAG_BADGE_CLASS} shrink-0 whitespace-nowrap`}>{candidateTag}</Badge> : null}
          </div>
          <div className="flex min-w-0 justify-end pr-3">
            <Badge className="whitespace-nowrap">{formatBytes(sourceCandidate.total_size)}</Badge>
          </div>
          <div className="min-w-0 overflow-hidden pl-3">
            <div className="flex min-w-0 flex-nowrap items-center gap-2">
              <Badge className="shrink-0 whitespace-nowrap">{t('countFiles', { count: sourceCandidate.file_count })}</Badge>
              {sourceCandidate.match ? (
                <Badge tone={confidenceTone(confidence)} className={`${confidenceBadgeClass(confidence)} shrink-0`}>{confidenceLabel(t, confidence)}</Badge>
              ) : null}
              {issueMoveCount ? <MoveReviewWarning count={issueMoveCount} labels={issueLabels} /> : null}
              {showModifiedTime ? <span className="shrink-0 text-xs text-muted-foreground">{formatUnixSeconds(modifiedTime, locale)}</span> : null}
              {sourceCandidate.match && !needsIdentificationFix ? <TmdbIdentityLink match={sourceCandidate.match} mediaType={mediaType} /> : null}
              <div className="ml-auto flex min-w-0 shrink-0 flex-nowrap items-center justify-end gap-2">
                <div className="flex flex-wrap gap-2">
                  {canReview ? (
                    <Button
                      aria-label={changeLabel}
                      size="sm"
                      variant="outline"
                      onClick={() => setTmdbOpen(true)}
                      disabled={sourceCandidate.status !== 'active'}
                    >
                      <Pencil data-icon="inline-start" />
                      {t('change')}
                    </Button>
                  ) : null}
                  {canInspectSource ? (
                    <Button
                      aria-label={t('detailsLabel', { label: sourceCandidate.display_name })}
                      size="sm"
                      variant="outline"
                      onClick={() => setEntryTarget({ type: 'candidate', sourceCandidate })}
                    >
                      <Info data-icon="inline-start" />
                      {t('details')}
                    </Button>
                  ) : null}
                </div>
                {canReview ? (
                  <CandidateDecisionSwitcher
                    sourceCandidate={sourceCandidate}
                    sessionId={sessionId}
                    currentDecision={candidateDecision}
                    canAccept={canAcceptSource}
                    canIgnore={canBulkDecide}
                    lowConfidence={confidence === 'low'}
                    onError={onActionError}
                  />
                ) : null}
                {canSelectForIdentify ? (
                  <CandidateDecisionSwitcher
                    sourceCandidate={sourceCandidate}
                    sessionId={sessionId}
                    currentDecision={candidateDecision}
                    canAccept={canSelectSource}
                    canIgnore={canSelectSource}
                    lowConfidence={false}
                    onError={onActionError}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
      ) : null}

      <ConflictReviewsPanel
        groups={conflictReview.visibleGroups}
        sourceCandidate={sourceCandidate}
        sessionId={sessionId}
        canReview={canReview && sourceCandidate.status === 'active'}
        onError={onActionError}
      />

      {expanded ? (
        <SourceInventoryTable
          sourceCandidate={sourceCandidate}
          sessionId={sessionId}
          canReview={canReview && sourceCandidate.status === 'active'}
          lockedPlanItemIds={conflictReview.lockedPlanItemIds}
          canInspectSource={canInspectSource}
          onDetail={(sourceFile) => setEntryTarget({ type: 'file', sourceCandidate, sourceFile })}
        />
      ) : null}

      <TmdbSearchDialog
        open={tmdbOpen}
        onOpenChange={setTmdbOpen}
        sessionId={sessionId}
        mediaType={mediaType}
        sourceCandidate={sourceCandidate}
      />
      <OrganizeSourceEntryDialog
        open={Boolean(entryTarget)}
        onOpenChange={(open) => {
          if (!open) setEntryTarget(null)
        }}
        sessionId={sessionId}
        target={entryTarget}
        canRename={canRenameSourceEntry}
        canDelete={canDeleteSourceEntry}
      />
    </section>
  )
}
