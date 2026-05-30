import { mediaTypeLabel, type TFunction } from '@/app/i18n/labels'
import type { DepotSummary, OrganizeSession, OriginSummary, TransferJob } from '@/api/types'
import type { DepotDraft, OriginDraft } from './draft'

export type RemovalAssessment = {
  canRemove: boolean
  message: string
}

export function assessOriginRemoval(origin: OriginSummary, sessions: OrganizeSession[], t: TFunction): RemovalAssessment {
  const hasActiveSession = sessions.some((session) => isSessionForOrigin(session, origin))
  if (hasActiveSession) {
    return {
      canRemove: false,
      message: t('removeOriginBlockedActiveSession'),
    }
  }
  return {
    canRemove: true,
    message: t('removeOriginSafeNotice'),
  }
}

export function assessDepotRemoval(
  depot: DepotSummary,
  users: OriginSummary[],
  sessions: OrganizeSession[],
  transferJobs: TransferJob[],
  t: TFunction,
): RemovalAssessment {
  const blockers: string[] = []
  if (users.length) blockers.push(t('removeDepotBlockedOrigins', { count: users.length }))
  if (sessions.some((session) => session.policy.target_depot_id === depot.id)) {
    blockers.push(t('removeDepotBlockedActiveSession'))
  }
  if (transferJobs.some((job) => job.depot_id === depot.id && isActiveTransferJob(job))) {
    blockers.push(t('removeDepotBlockedActiveTransfer'))
  }
  if (blockers.length) {
    return {
      canRemove: false,
      message: blockers.join('\n'),
    }
  }
  return {
    canRemove: true,
    message: t('removeDepotSafeNotice'),
  }
}

function isSessionForOrigin(session: OrganizeSession, origin: OriginSummary) {
  const originId = (session as OrganizeSession & { origin_id?: string | null }).origin_id
  if (originId) return originId === origin.id
  return session.kind === 'origin' && sameConfiguredPath(session.path, origin.path)
}

function isActiveTransferJob(job: TransferJob) {
  return job.status === 'queued' || job.status === 'running' || job.status === 'cancelling'
}

function sameConfiguredPath(left: string, right: string) {
  return normalizeConfiguredPath(left) === normalizeConfiguredPath(right)
}

function normalizeConfiguredPath(path: string) {
  return path.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
}

export function validateOriginDraft(draft: OriginDraft, t: TFunction) {
  if (!draft.name.trim()) return t('originNameRequired')
  if (!draft.media_type) return t('originMediaTypeRequired')
  if (!draft.path.trim()) return t('originPathRequired')
  if (!draft.target_depot_id.trim()) return t('targetDepotRequired')
  return ''
}

export function validateDepotDraft(draft: DepotDraft, t: TFunction) {
  if (!draft.name.trim()) return t('depotNameRequired')
  if (!draft.media_type) return t('depotMediaTypeRequired')
  if (!draft.path.trim()) return t('depotPathRequired')
  if (!draft.target_library_path.trim()) return t('libraryPathRequired')
  return ''
}

export function ruleName(rules: { id: string; name?: string | null }[], id: string | null | undefined, t: TFunction) {
  if (!id) return t('none')
  return rules.find((rule) => rule.id === id)?.name ?? id
}

export function sortDepotsForCards(depots: DepotSummary[]) {
  return [...depots].sort((a, b) => {
    const mediaTypeOrder = depotMediaTypeOrder(a.media_type) - depotMediaTypeOrder(b.media_type)
    if (mediaTypeOrder !== 0) return mediaTypeOrder
    const nameOrder = a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
    if (nameOrder !== 0) return nameOrder
    return a.id.localeCompare(b.id)
  })
}

function depotMediaTypeOrder(mediaType: DepotSummary['media_type']) {
  if (mediaType === 'movie') return 0
  if (mediaType === 'tv') return 1
  return 2
}

export function mediaTypeOptions(t: TFunction) {
  return [
    { value: 'movie', label: mediaTypeLabel(t, 'movie') },
    { value: 'tv', label: mediaTypeLabel(t, 'tv') },
  ]
}
