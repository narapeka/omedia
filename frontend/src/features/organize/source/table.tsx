import { Ban, File, FileText, Film, Info, ShieldAlert, Trash2 } from 'lucide-react'
import { knownDisplayLabel, statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { CandidateDecision, PlanItem, SourceFile, SourceCandidate } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { PathArrow } from '@/components/filesystem/PathRoute'
import { TextSwitch } from '@/components/common/TextSwitch'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { notifyError } from '@/lib/notifications'
import { useIs2xl } from '@/lib/useMediaQuery'
import { useSessionActions } from '../api'
import { blockerText, formatBytes, statusTone } from '../display'
import { PLAN_TAG_HIGHLIGHT_CLASS, planItemTagSuffix } from '../tags'
import { planItemIssueLabels, planItemNeedsIdentificationFix } from '../evidence'

type PlanItemTagHighlight = {
  rootRelativePath?: string
  tagSuffix: string
}

const PLAN_ITEM_WARNING_BADGE_CLASS = 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300'

export function SourceInventoryTable({
  sourceCandidate,
  sessionId,
  canReview,
  lockedPlanItemIds,
  canInspectSource,
  onDetail,
}: {
  sourceCandidate: SourceCandidate
  sessionId: string
  canReview: boolean
  lockedPlanItemIds?: Set<string>
  canInspectSource: boolean
  onDetail: (sourceFile: SourceFile) => void
}) {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  if (sourceCandidate.files.length === 0) {
    return <div className="border-t bg-muted/20 p-3 text-sm text-muted-foreground">{t('noInventoryFilesFound')}</div>
  }

  const attachments = attachPlanItemsToFiles(sourceCandidate.files, sourceCandidate.plan_items)
  const tagHighlights = buildPlanItemTagHighlightMap(sourceCandidate)

  return (
    <div className="flex flex-col">
      {!is2xl ? (
      <div className="border-t bg-background">
        {sourceCandidate.files.map((sourceFile, index) => (
          <div key={sourceFile.id} className="grid gap-2 border-b p-3 last:border-b-0" data-status={sourceFile.status}>
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <TreeIndentGuide isLast={index === sourceCandidate.files.length - 1} />
                <SourceFileClassificationIcon sourceFile={sourceFile} />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium" title={sourceFile.relative_path}>{sourceFile.relative_path}</div>
                  {sourceFile.status !== 'active' ? (
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <Badge tone={statusTone(sourceFile.status)}>{statusLabel(t, sourceFile.status)}</Badge>
                    </div>
                  ) : null}
                </div>
              </div>
              <Badge className="shrink-0 whitespace-nowrap">{formatBytes(sourceFile.size_bytes)}</Badge>
            </div>
            <div className="ml-9 flex min-w-0 items-start gap-2 text-xs text-muted-foreground">
              <PathArrow className="mt-0.5 size-3.5" />
              <SourceFileMovePlan
                planItems={attachments.planItemsByFileId.get(sourceFile.id) ?? []}
                tagHighlights={tagHighlights}
              />
            </div>
            <div className="ml-9 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                {canInspectSource ? (
                  <Button
                    aria-label={t('detailsLabel', { label: sourceFile.relative_path })}
                    className="whitespace-nowrap"
                    variant="outline"
                    size="sm"
                    onClick={() => onDetail(sourceFile)}
                  >
                    <Info data-icon="inline-start" />
                    {t('details')}
                  </Button>
                ) : null}
              </div>
              <SourceFileMoveActions
                planItems={attachments.planItemsByFileId.get(sourceFile.id) ?? []}
                sessionId={sessionId}
                canReview={canReview}
                lockedPlanItemIds={lockedPlanItemIds}
              />
            </div>
          </div>
        ))}
      </div>
      ) : null}
      {is2xl ? (
      <div className="overflow-x-auto border-t bg-background">
        <Table className="min-w-[1060px] table-fixed">
          <colgroup>
            <col style={{ width: '50%' }} />
            <col style={{ width: '5.75rem' }} />
            <col />
            <col style={{ width: '13rem' }} />
          </colgroup>
          <TableBody>
            {sourceCandidate.files.map((sourceFile, index) => (
              <TableRow key={sourceFile.id} data-status={sourceFile.status}>
                <TableCell className="whitespace-nowrap py-3 pl-3 pr-3 align-middle">
                  <div className="flex min-w-0 items-center gap-2">
                    <TreeIndentGuide isLast={index === sourceCandidate.files.length - 1} />
                    <SourceFileClassificationIcon sourceFile={sourceFile} />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium" title={sourceFile.relative_path}>{sourceFile.relative_path}</div>
                      {sourceFile.status !== 'active' ? (
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <Badge tone={statusTone(sourceFile.status)}>{statusLabel(t, sourceFile.status)}</Badge>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="whitespace-nowrap py-3 pr-3 text-right align-middle">
                  <div className="flex justify-end">
                    <Badge className="whitespace-nowrap">{formatBytes(sourceFile.size_bytes)}</Badge>
                  </div>
                </TableCell>
                <TableCell className="whitespace-nowrap py-3 pl-3 pr-3 align-middle">
                  <div className="flex min-w-0 items-center gap-3">
                    <PathArrow className="size-4" />
                    <SourceFileMovePlan
                      planItems={attachments.planItemsByFileId.get(sourceFile.id) ?? []}
                      tagHighlights={tagHighlights}
                    />
                  </div>
                </TableCell>
                <TableCell className="py-3 pr-3 align-middle">
                  <div className="flex flex-nowrap items-center justify-end gap-2">
                    {canInspectSource ? (
                      <Button
                        aria-label={t('detailsLabel', { label: sourceFile.relative_path })}
                        className="whitespace-nowrap"
                        variant="outline"
                        size="sm"
                        onClick={() => onDetail(sourceFile)}
                      >
                        <Info data-icon="inline-start" />
                        {t('details')}
                      </Button>
                    ) : null}
                    <SourceFileMoveActions
                      planItems={attachments.planItemsByFileId.get(sourceFile.id) ?? []}
                      sessionId={sessionId}
                      canReview={canReview}
                      lockedPlanItemIds={lockedPlanItemIds}
                    />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      ) : null}
      {attachments.unmatchedPlanItems.length ? (
        <AdditionalPlanItems planItems={attachments.unmatchedPlanItems} sessionId={sessionId} canReview={canReview} lockedPlanItemIds={lockedPlanItemIds} tagHighlights={tagHighlights} />
      ) : null}
    </div>
  )
}

function TreeIndentGuide({ isLast }: { isLast: boolean }) {
  return (
    <span aria-hidden="true" className="relative min-h-5 w-7 shrink-0 self-stretch">
      <span className={`absolute left-3 w-px bg-border ${isLast ? 'top-0 h-1/2' : 'inset-y-0'}`} />
      <span className="absolute left-3 top-1/2 h-px w-4 bg-border" />
    </span>
  )
}

function SourceFileClassificationIcon({ sourceFile }: { sourceFile: SourceFile }) {
  const { t } = useI18n()
  const Icon = classificationIcon(sourceFile.classification)
  const iconTone = classificationIconTone(sourceFile.classification, sourceFile.status)
  const label = knownDisplayLabel(t, sourceFile.classification)

  return (
    <span
      className={`inline-flex size-5 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 ${iconTone}`}
      title={label}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}</span>
    </span>
  )
}

function classificationIcon(classification: SourceFile['classification']) {
  switch (classification) {
    case 'video':
      return Film
    case 'subtitle':
      return FileText
    case 'generic_sidecar':
      return File
    case 'deleted':
      return Trash2
    case 'blocked':
      return ShieldAlert
    case 'missing':
    case 'unsupported':
      return Ban
    default:
      return File
  }
}

function classificationIconTone(classification: SourceFile['classification'], status: SourceFile['status']) {
  if (status !== 'active' || classification === 'blocked' || classification === 'deleted' || classification === 'missing' || classification === 'unsupported') {
    return 'text-destructive'
  }
  if (classification === 'video') return 'text-primary'
  if (classification === 'subtitle') return 'text-sky-500'
  return 'text-muted-foreground'
}

function SourceFileMovePlan({
  planItems,
  tagHighlights,
}: {
  planItems: PlanItem[]
  tagHighlights: Map<string, PlanItemTagHighlight>
}) {
  const { t } = useI18n()
  if (planItems.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <div className="text-xs text-muted-foreground">{t('noMovePlannedYet')}</div>
      </div>
    )
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      {planItems.map((planItem) => (
        <PlanItemInline key={planItem.id} planItem={planItem} tagHighlight={tagHighlights.get(planItem.id)} />
      ))}
    </div>
  )
}

function AdditionalPlanItems({
  planItems,
  sessionId,
  canReview,
  lockedPlanItemIds,
  tagHighlights,
}: {
  planItems: PlanItem[]
  sessionId: string
  canReview: boolean
  lockedPlanItemIds?: Set<string>
  tagHighlights: Map<string, PlanItemTagHighlight>
}) {
  const { t } = useI18n()
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="text-sm font-medium">{t('additionalPlannedMoves')}</div>
      <div className="mt-1 text-xs text-muted-foreground">
        {t('additionalPlannedMovesDescription')}
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {planItems.map((planItem) => (
          <div key={planItem.id} className="flex flex-wrap items-start justify-between gap-2 rounded-md border bg-background p-2">
            <PlanItemInline planItem={planItem} tagHighlight={tagHighlights.get(planItem.id)} />
            <SourceFileMoveActions planItems={[planItem]} sessionId={sessionId} canReview={canReview} lockedPlanItemIds={lockedPlanItemIds} />
          </div>
        ))}
      </div>
    </div>
  )
}

function PlanItemInline({
  planItem,
  tagHighlight,
}: {
  planItem: PlanItem
  tagHighlight?: PlanItemTagHighlight
}) {
  const { t } = useI18n()
  const needsIdentificationFix = planItemNeedsIdentificationFix(planItem)
  const blockers = needsIdentificationFix ? '' : blockerText(planItem.acceptance.blockers, t)
  const issueLabels = needsIdentificationFix ? [] : planItemIssueLabels(planItem, t)
  const target = needsIdentificationFix ? t('needsIdentifyCorrection') : planItem.preview.proposed_relative_path ?? t('noRenderableTarget')

  return (
    <div className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1">
      <div className="min-w-0 truncate text-sm" title={target}>{renderTargetWithTagHighlight(target, tagHighlight)}</div>
      {issueLabels.length ? (
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          {issueLabels.slice(0, 3).map((label) => (
            <Badge key={label} tone="warning" className={PLAN_ITEM_WARNING_BADGE_CLASS}>{label}</Badge>
          ))}
        </div>
      ) : null}
      {!planItem.acceptance.can_accept && blockers ? <div className="col-span-2 text-xs text-muted-foreground">{blockers}</div> : null}
    </div>
  )
}

function buildPlanItemTagHighlightMap(sourceCandidate: SourceCandidate) {
  const planItemsById = new Map(sourceCandidate.plan_items.map((planItem) => [planItem.id, planItem]))
  const result = new Map<string, PlanItemTagHighlight>()

  for (const group of sourceCandidate.conflict_reviews ?? []) {
    for (const planItemId of group.plan_item_ids) {
      const planItem = planItemsById.get(planItemId)
      const tagSuffix = planItem ? planItemTagSuffix(planItem) : null
      if (tagSuffix) {
        result.set(planItemId, {
          rootRelativePath: group.root_relative_path,
          tagSuffix,
        })
      }
    }
  }

  for (const planItem of sourceCandidate.plan_items) {
    if (result.has(planItem.id)) continue
    const tagSuffix = planItemTagSuffix(planItem)
    if (tagSuffix) result.set(planItem.id, { tagSuffix })
  }

  return result
}

function renderTargetWithTagHighlight(target: string, highlight?: PlanItemTagHighlight) {
  if (!highlight?.tagSuffix) return target
  const index = targetTagIndex(target, highlight)
  if (index < 0) return target
  const before = target.slice(0, index)
  const tag = target.slice(index, index + highlight.tagSuffix.length)
  const after = target.slice(index + highlight.tagSuffix.length)
  return (
    <>
      {before}
      <span className={PLAN_TAG_HIGHLIGHT_CLASS}>{tag}</span>
      {after}
    </>
  )
}

function targetTagIndex(target: string, highlight: PlanItemTagHighlight) {
  const tagSuffix = highlight.tagSuffix
  if (highlight.rootRelativePath) {
    const rootStart = target.indexOf(highlight.rootRelativePath)
    const tagInRoot = highlight.rootRelativePath.lastIndexOf(tagSuffix)
    if (rootStart >= 0 && tagInRoot >= 0) return rootStart + tagInRoot

    const normalizedTarget = target.replaceAll('\\', '/')
    const normalizedRoot = highlight.rootRelativePath.replaceAll('\\', '/')
    const normalizedRootStart = normalizedTarget.indexOf(normalizedRoot)
    const normalizedTagInRoot = normalizedRoot.lastIndexOf(tagSuffix)
    if (normalizedRootStart >= 0 && normalizedTagInRoot >= 0) return normalizedRootStart + normalizedTagInRoot
  }
  return target.indexOf(tagSuffix)
}

function SourceFileMoveActions({
  planItems,
  sessionId,
  canReview,
  lockedPlanItemIds,
}: {
  planItems: PlanItem[]
  sessionId: string
  canReview: boolean
  lockedPlanItemIds?: Set<string>
}) {
  if (planItems.length === 0) return null
  return (
    <div className="flex flex-col items-end gap-1">
      {planItems.map((planItem) => (
        <div key={planItem.id} className="flex items-center justify-end gap-2">
          <PlanDecisionSwitcher
            planItem={planItem}
            sessionId={sessionId}
            canReview={canReview}
            locked={Boolean(lockedPlanItemIds?.has(planItem.id))}
          />
        </div>
      ))}
    </div>
  )
}

function PlanDecisionSwitcher({
  planItem,
  sessionId,
  canReview,
  locked,
}: {
  planItem: PlanItem
  sessionId: string
  canReview: boolean
  locked: boolean
}) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))
  const pending = actions.setPlanItemDecision.isPending
  const accepted = planItem.user_decision === 'accept'
  const canAccept = canReview && planItem.acceptance.can_accept
  const canIgnore = canReview
  const disabled = pending || locked || (accepted ? !canIgnore : !canAccept)
  const nextDecision: CandidateDecision = accepted ? 'ignore' : 'accept'
  const target = planItem.preview.proposed_relative_path ?? t('plannedMoveTarget')
  const label = accepted
    ? t('acceptedTargetClickIgnore', { target })
    : t('ignoredTargetClickAccept', { target })

  return (
    <TextSwitch
      checked={accepted}
      checkedLabel={t('accept')}
      uncheckedLabel={t('ignore')}
      ariaLabel={label}
      disabled={disabled}
      onCheckedChange={() =>
        actions.setPlanItemDecision.mutate(
          { sessionId, planItemId: planItem.id, data: { decision: nextDecision } },
          { onError: onActionError },
        )
      }
      title={locked ? t('overwriteConflictFileActionDisabled') : accepted ? t('acceptedClickIgnore') : planItem.acceptance.can_accept ? t('ignoredPendingClickAccept') : blockerText(planItem.acceptance.blockers, t) || t('cannotAcceptMove')}
      widthRem={5.5}
    />
  )
}

function attachPlanItemsToFiles(sourceFiles: SourceFile[], planItems: PlanItem[]) {
  const planItemById = new Map(planItems.map((planItem) => [planItem.id, planItem]))
  const planItemsByFileId = new Map<string, PlanItem[]>()
  const attachedPlanItemIds = new Set<string>()

  for (const sourceFile of sourceFiles) {
    const attached: PlanItem[] = []
    for (const planItemId of sourceFile.planned_item_ids) {
      const planItem = planItemById.get(planItemId)
      if (planItem && !attachedPlanItemIds.has(planItem.id)) {
        attached.push(planItem)
        attachedPlanItemIds.add(planItem.id)
      }
    }
    for (const planItem of planItems) {
      if (planItem.source_file_id === sourceFile.id && !attachedPlanItemIds.has(planItem.id)) {
        attached.push(planItem)
        attachedPlanItemIds.add(planItem.id)
      }
    }
    planItemsByFileId.set(sourceFile.id, attached)
  }

  return {
    planItemsByFileId,
    unmatchedPlanItems: planItems.filter((planItem) => !attachedPlanItemIds.has(planItem.id)),
  }
}
