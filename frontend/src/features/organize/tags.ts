import type { PlanItem, SourceCandidate } from '@/api/types'

const PLAN_EVIDENCE_KEYS = ['movie_plan', 'tv_episode_plan'] as const
export const PLAN_TAG_BADGE_CLASS = 'border-violet-500/30 bg-violet-500/15 text-violet-700 dark:text-violet-300'
export const PLAN_TAG_HIGHLIGHT_CLASS = 'rounded bg-violet-500/15 px-1 font-semibold text-violet-700 dark:text-violet-300'

export function planItemTag(planItem: PlanItem) {
  for (const key of PLAN_EVIDENCE_KEYS) {
    const evidence = planEvidence(planItem, key)
    const value = evidence?.tag
    if (typeof value === 'string' && value) return value
  }
  return null
}

export function planItemTagSuffix(planItem: PlanItem) {
  for (const key of PLAN_EVIDENCE_KEYS) {
    const evidence = planEvidence(planItem, key)
    const value = evidence?.tag_suffix
    if (typeof value === 'string' && value) return value
  }
  return null
}

export function candidateUniformPlanTag(sourceCandidate: SourceCandidate) {
  const taggedPlanItems = sourceCandidate.plan_items.filter((planItem) => planItem.preview.proposed_relative_path)
  if (taggedPlanItems.length === 0) return null

  let uniformTag: string | null = null
  for (const planItem of taggedPlanItems) {
    const tag = planItemTag(planItem)
    if (!tag) return null
    if (uniformTag == null) {
      uniformTag = tag
      continue
    }
    if (tag !== uniformTag) return null
  }
  return uniformTag
}

function planEvidence(planItem: PlanItem, key: (typeof PLAN_EVIDENCE_KEYS)[number]) {
  const evidence = planItem.evidence?.[key]
  return evidence && typeof evidence === 'object' && !Array.isArray(evidence)
    ? evidence as Record<string, unknown>
    : null
}

