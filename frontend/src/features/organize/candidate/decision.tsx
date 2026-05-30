import type { CandidateDecision, SourceCandidate } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { TextSwitch } from '@/components/common/TextSwitch'
import { useSessionActions } from '../api'
import { planItemNeedsIdentificationFix } from '../evidence'

export type CandidateDecisionDisplay = CandidateDecision | 'mixed' | null

export function sourceCandidateDecision(sourceCandidate: SourceCandidate): CandidateDecisionDisplay {
  if (sourceCandidate.plan_items.length === 0) return null
  const decisions = sourceCandidate.plan_items.map((planItem) => planItem.user_decision)
  if (decisions.every((decision) => decision === 'accept')) return 'accept'
  if (decisions.some((decision) => decision === 'accept')) return 'mixed'
  return 'ignore'
}

export function sourceCandidateNeedsIdentificationFix(sourceCandidate: SourceCandidate) {
  const blockers = sourceCandidate.match?.acceptance.blockers ?? []
  return (
    blockers.includes('missing_metadata') ||
    blockers.includes('missing_target_path') ||
    sourceCandidate.plan_items.some(planItemNeedsIdentificationFix)
  )
}

export function confidenceBadgeClass(confidence: string) {
  if (confidence === 'high') return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
  if (confidence === 'medium') return 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300'
  return 'border-red-500/30 bg-red-500/15 text-red-700 dark:text-red-300'
}

export function CandidateDecisionSwitcher({
  sourceCandidate,
  sessionId,
  currentDecision,
  canAccept,
  canIgnore,
  lowConfidence,
  onError,
}: {
  sourceCandidate: SourceCandidate
  sessionId: string
  currentDecision: CandidateDecisionDisplay
  canAccept: boolean
  canIgnore: boolean
  lowConfidence: boolean
  onError: (error: unknown) => void
}) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const pending = actions.setSourceCandidateDecision.isPending
  const accepted = currentDecision === 'accept'
  const mixed = currentDecision === 'mixed'
  const activeVisual = accepted || mixed
  const disabled = pending || (accepted ? !canIgnore : !canAccept)
  const decide = (decision: CandidateDecision) => {
    actions.setSourceCandidateDecision.mutate(
      { sessionId, candidateId: sourceCandidate.id, data: { decision } },
      { onError },
    )
  }
  const nextDecision: CandidateDecision = accepted ? 'ignore' : 'accept'
  const label = accepted
    ? t('acceptedTargetClickIgnore', { target: sourceCandidate.display_name })
    : t(lowConfidence ? 'acceptAnywayTarget' : 'acceptTarget', { target: sourceCandidate.display_name })

  return (
    <TextSwitch
      checked={activeVisual}
      checkedLabel={t('accept')}
      uncheckedLabel={t('ignore')}
      ariaChecked={mixed ? 'mixed' : accepted}
      ariaLabel={label}
      className={mixed ? 'opacity-70' : undefined}
      disabled={disabled}
      onCheckedChange={() => decide(nextDecision)}
      title={accepted ? t('acceptedClickIgnore') : t('ignoredPendingClickAccept')}
      widthRem={5.5}
    />
  )
}
