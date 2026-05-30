import type { PlanItem } from '@/api/types'
import { type TFunction } from '@/app/i18n/labels'
import type { MessageKey } from '@/app/i18n/messages'
import { blockerText, humanize, isRecord, stringValue } from './display'

const IDENTIFICATION_FIX_BLOCKERS = new Set(['missing_metadata', 'missing_target_path'])
const RENDER_WARNING_LABELS: Record<string, MessageKey> = {
  missing_episode_title: 'episodeTitleMissing',
  missing_year: 'renderWarningMissingYear',
  missing_tmdb_id: 'renderWarningMissingTmdbId',
  missing_movie_part_token: 'renderWarningMissingMoviePartToken',
}

export function planItemIssueLabels(planItem: PlanItem, t: TFunction) {
  const labels: string[] = []
  if (!planItem.acceptance.can_accept) {
    const blockers = blockerText(planItem.acceptance.blockers, t)
    if (blockers) labels.push(blockers)
  }
  labels.push(...planItem.preview.render_warnings.map((warning) => renderWarningLabel(warning, t)))

  const tvPlan = tvEpisodePlan(planItem)
  if (tvPlan) {
    if (tvPlan.confident === false) labels.push(t('episodeNeedsReview'))
    if (!stringValue(tvPlan.episode_title) || stringValue(tvPlan.episode_title_source) === 'none') {
      labels.push(t('episodeTitleMissing'))
    }
    const resolution = tvPlan.resolution
    if (isRecord(resolution)) {
      const status = stringValue(resolution.status)
      if (status && status !== 'not_needed' && status !== 'applied') {
        labels.push(t('resolutionStatus', { status: humanize(status, t) }))
      }
      const warning = stringValue(resolution.warning)
      if (warning) labels.push(warning)
    }
  }

  return [...new Set(labels.filter(Boolean))]
}

function renderWarningLabel(warning: string, t: TFunction) {
  const messageKey = RENDER_WARNING_LABELS[warning]
  if (messageKey) return t(messageKey)
  if (warning.endsWith('_sanitized')) return t('renderWarningNameSanitized')
  return humanize(warning, t)
}

export function planItemHasIssue(planItem: PlanItem) {
  if (!planItem.acceptance.can_accept || planItem.preview.render_warnings.length > 0) return true
  const tvPlan = tvEpisodePlan(planItem)
  if (!tvPlan) return false
  if (tvPlan.confident === false) return true
  if (!stringValue(tvPlan.episode_title) || stringValue(tvPlan.episode_title_source) === 'none') return true
  const resolution = tvPlan.resolution
  if (!isRecord(resolution)) return false
  const status = stringValue(resolution.status)
  return Boolean(status && status !== 'not_needed' && status !== 'applied') || Boolean(stringValue(resolution.warning))
}

export function planItemNeedsIdentificationFix(planItem: PlanItem) {
  return planItem.acceptance.blockers.some((blocker) => IDENTIFICATION_FIX_BLOCKERS.has(blocker))
}

export function tvEpisodePlan(planItem: PlanItem) {
  const value = planItem.evidence?.tv_episode_plan
  return isRecord(value) ? value : null
}

