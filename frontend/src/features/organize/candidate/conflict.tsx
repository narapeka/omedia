import { Package, Replace, Tag } from 'lucide-react'
import { useState } from 'react'
import { type TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { ConflictReview, ConflictReviewAction, SourceCandidate } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useSessionActions } from '../api'

const OVERWRITE_WARNING_BADGE_CLASS = 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300'

export function ConflictReviewsPanel({
  groups,
  sourceCandidate,
  sessionId,
  canReview,
  onError,
}: {
  groups: ConflictReview[]
  sourceCandidate: SourceCandidate
  sessionId: string
  canReview: boolean
  onError: (error: unknown) => void
}) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const [tagGroup, setTagGroup] = useState<ConflictReview | null>(null)
  const [tagValue, setTagValue] = useState('')
  if (groups.length === 0) return null

  const pending = actions.applyConflictReviewAction.isPending
  const decide = (group: ConflictReview, action: ConflictReviewAction) => {
    actions.applyConflictReviewAction.mutate(
      { sessionId, data: { identity_key: group.identity_key, source_candidate_id: sourceCandidate.id, action } },
      { onError },
    )
  }
  const openTagVariant = (group: ConflictReview) => {
    setTagValue(group.source_tag ?? '')
    setTagGroup(group)
  }
  const submitTagVariant = () => {
    if (!tagGroup) return
    const tag = tagValue.trim()
    if (!tag) return
    actions.applyConflictReviewAction.mutate(
      {
        sessionId,
        data: {
          identity_key: tagGroup.identity_key,
          source_candidate_id: sourceCandidate.id,
          action: 'tag_variant',
          tag_override: tag,
        },
      },
      {
        onError,
        onSuccess: () => {
          setTagGroup(null)
          setTagValue('')
        },
      },
    )
  }
  return (
    <>
      <div className="border-b bg-muted/20 px-3 py-1.5">
        <div className="flex flex-col gap-1">
          {groups.map((group) => (
            <ConflictReviewRow
              key={group.identity_key}
              group={group}
              canReview={canReview}
              pending={pending}
              onKeep={() => decide(group, 'keep')}
              onReplaceTarget={() => decide(group, 'replace_target')}
              onKeepAndReplace={() => decide(group, 'keep_and_replace')}
              onTagVariant={() => openTagVariant(group)}
            />
          ))}
        </div>
      </div>
      <Dialog open={Boolean(tagGroup)} onOpenChange={(open) => {
        if (!open && !pending) setTagGroup(null)
      }}>
        <DialogContent className="sm:max-w-md">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              submitTagVariant()
            }}
          >
            <DialogHeader>
              <DialogTitle>{t('addTagVariant')}</DialogTitle>
              <DialogDescription className="sr-only">{t('tagVariantPrompt')}</DialogDescription>
            </DialogHeader>
            <div>
              <Input
                id="tag-variant-input"
                aria-label={t('tagVariantPrompt')}
                autoFocus
                value={tagValue}
                onChange={(event) => setTagValue(event.target.value)}
                disabled={pending}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" disabled={pending} onClick={() => setTagGroup(null)}>
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={pending || !tagValue.trim()}>
                {t('save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}

function ConflictReviewRow({
  group,
  canReview,
  pending,
  onKeep,
  onReplaceTarget,
  onKeepAndReplace,
  onTagVariant,
}: {
  group: ConflictReview
  canReview: boolean
  pending: boolean
  onKeep: () => void
  onReplaceTarget: () => void
  onKeepAndReplace: () => void
  onTagVariant: () => void
}) {
  const { t } = useI18n()
  const status = group.status ?? (group.conflict_reason === 'duplicate_source_package' ? 'duplicate_source' : group.existing ? 'target_exists' : 'ready')
  if (status === 'ready') return null
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-2 rounded-md px-2 py-1 text-xs">
      <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
        {conflictReviewStatusLabels(t, group).map((label) => (
          <Badge key={label} tone="warning" className={OVERWRITE_WARNING_BADGE_CLASS}>{label}</Badge>
        ))}
      </div>
      {canReview ? (
        <div className="flex shrink-0 flex-wrap gap-1">
          {status === 'duplicate_source' ? (
            <Button size="sm" variant="outline" disabled={pending} onClick={onKeep}>
              <Package data-icon="inline-start" />
              {t('keepThisVersion')}
            </Button>
          ) : null}
          {status === 'target_exists' ? (
            <Button size="sm" variant="outline" disabled={pending} onClick={onReplaceTarget}>
              <Replace data-icon="inline-start" />
              {t('replaceTargetPackage')}
            </Button>
          ) : null}
          {status === 'duplicate_source_and_target_exists' ? (
            <Button size="sm" variant="outline" disabled={pending} onClick={onKeepAndReplace}>
              <Replace data-icon="inline-start" />
              {t('keepAndReplaceTargetPackage')}
            </Button>
          ) : null}
          <Button size="sm" variant="outline" disabled={pending} onClick={onTagVariant}>
            <Tag data-icon="inline-start" />
            {t('addTagVariant')}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function conflictReviewStatusLabels(t: TFunction, group: ConflictReview) {
  if (group.status === 'duplicate_source_and_target_exists') {
    return [t('conflictReviewDuplicateSource'), t('conflictReviewPackageExists')]
  }
  if (group.status === 'duplicate_source') return [t('conflictReviewDuplicateSource')]
  if (group.status === 'target_exists') return [t('conflictReviewPackageExists')]
  if (group.conflict_reason === 'duplicate_source_package') return [t('conflictReviewDuplicateSource')]
  if (group.conflict_reason === 'package_exists') return [t('conflictReviewPackageExists')]
  return group.existing ? [t('conflictReviewPackageExists')] : [t('conflictReviewReady')]
}

export function buildConflictReviewModel(sourceCandidate: SourceCandidate) {
  const groups = sourceCandidate.conflict_reviews ?? []
  const visibleGroups = groups.filter((group) => (group.status ?? 'ready') !== 'ready')
  const lockedPlanItemIds = new Set<string>()

  for (const group of groups) {
    const status = group.status ?? (group.conflict_reason === 'duplicate_source_package' ? 'duplicate_source' : group.existing ? 'target_exists' : 'ready')
    if (status === 'ready') continue
    const acceptedSourceIds = group.accepted_source_candidate_ids ?? []
    const selected = acceptedSourceIds.includes(sourceCandidate.id)
    const actionTargetsSource = group.action_source_candidate_id === sourceCandidate.id
    const unlocked =
      (status === 'duplicate_source' && group.action === 'keep' && (selected || actionTargetsSource)) ||
      (status === 'target_exists' && group.action === 'replace_target' && actionTargetsSource && group.replace_intent) ||
      (status === 'duplicate_source_and_target_exists' && group.action === 'keep_and_replace' && actionTargetsSource && group.replace_intent)
    if (!unlocked) {
      for (const planItemId of group.plan_item_ids) lockedPlanItemIds.add(planItemId)
    }
  }

  return {
    visibleGroups,
    lockedPlanItemIds,
    hasActionRequiredGroup: visibleGroups.length > 0,
  }
}

