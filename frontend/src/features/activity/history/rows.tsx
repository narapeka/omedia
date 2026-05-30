import type { ActivityEvent } from '@/api/types'
import {
  activityAreaLabel,
  defaultT,
  entityLabel as translatedEntityLabel,
  knownDisplayLabel,
  mediaTypeLabel,
  reasonLabel,
  statusLabel,
  type TFunction,
} from '@/app/i18n/labels'
import type { BadgeTone } from '@/components/common/Badge'

export type HistoryItem = {
  id: string
  occurredAt: string
  area: string
  event: string
  status: string
  result: string
  tone?: ActivityStatusTone
  source: string
  sourceTitle: string
  target: string
  targetTitle: string
  summary: string
  contextRows: HistoryContextRow[]
  raw: ActivityEvent
}

export type HistoryContextRow = {
  label: string
  value: string
}

export function buildHistoryItems({
  events,
  t = defaultT,
}: {
  events: ActivityEvent[]
  t?: TFunction
}) {
  return events
    .map((event) => activityHistoryItem(event, t))
    .sort((left, right) => new Date(right.occurredAt).getTime() - new Date(left.occurredAt).getTime())
}

function activityHistoryItem(event: ActivityEvent, t: TFunction): HistoryItem {
  const result = statusLabel(t, event.status)
  const contextRows = activityContextRows(event, t)
  return {
    id: event.id,
    occurredAt: event.time,
    area: activityAreaLabel(t, event.area),
    event: eventLabel(event, t),
    status: event.status,
    result,
    tone: statusTone(event.status, event.reason),
    source: historyPath(event.entity_source),
    sourceTitle: event.entity_source ?? '',
    target: historyPath(event.entity_target ?? event.library_path),
    targetTitle: event.entity_target ?? event.library_path ?? '',
    summary: event.summary ?? (reasonLabel(t, event.reason) || result),
    contextRows,
    raw: event,
  }
}

function historyPath(value: string | null | undefined) {
  return value || '-'
}

export type ActivityStatusTone = BadgeTone | 'info'

export function statusTone(status: string, reason?: string | null): ActivityStatusTone | undefined {
  if (status === 'failed') return 'danger'
  if (status === 'succeeded') return 'success'
  if (status === 'queued' || status === 'started') return 'info'
  if (status === 'skipped' || reason === 'unmatched') return 'warning'
  return undefined
}

export function activityStatusBadgeClass(tone: ActivityStatusTone | undefined) {
  switch (tone) {
    case 'success':
      return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200'
    case 'warning':
      return 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-200'
    case 'danger':
      return 'border-red-500/30 bg-red-500/15 text-red-700 dark:text-red-200'
    case 'info':
      return 'border-sky-500/30 bg-sky-500/15 text-sky-700 dark:text-sky-200'
    default:
      return undefined
  }
}

export function areaBadgeClass(area: string | null | undefined) {
  switch (area) {
    case 'watch_organize':
      return 'border-cyan-400/30 bg-cyan-950/35 text-cyan-700 dark:text-cyan-200'
    case 'manual_organize':
      return 'border-purple-400/30 bg-purple-950/35 text-purple-700 dark:text-purple-200'
    case 'manual_transfer':
      return 'border-lime-400/30 bg-lime-950/30 text-lime-700 dark:text-lime-200'
    case 'scheduled_transfer':
      return 'border-pink-400/30 bg-pink-950/35 text-pink-700 dark:text-pink-200'
    case 'file_management':
      return 'border-stone-400/30 bg-stone-900/50 text-stone-700 dark:text-stone-200'
    default:
      return undefined
  }
}

function activityContextRows(event: ActivityEvent, t: TFunction): HistoryContextRow[] {
  const countRows = countContextRows(event.context ?? {}, t)
  return [
    [t('when'), event.time],
    [t('area'), activityAreaLabel(t, event.area)],
    [t('event'), eventLabel(event, t)],
    [t('result'), statusLabel(t, event.status)],
    [t('reason'), reasonLabel(t, event.reason)],
    [t('source'), event.entity_source],
    [t('target'), event.entity_target],
    [t('origin'), event.origin_name || event.origin_path],
    [t('originPath'), event.origin_path],
    [t('depot'), event.depot_name || event.depot_path],
    [t('depotPath'), event.depot_path],
    [t('library'), event.library_path],
    [t('rule'), event.rule_name],
    [t('mediaType'), mediaTypeLabel(t, event.media_type)],
    [t('tmdbId'), event.tmdb_id],
    [t('summary'), event.summary],
    ...countRows.map((row) => [row.label, row.value] as [string, string]),
  ]
    .filter((row): row is [string, string] => Boolean(row[1]))
    .map(([label, value]) => ({ label, value }))
}

function countContextRows(context: Record<string, unknown>, t: TFunction): HistoryContextRow[] {
  return [
    [t('resultMoved'), context.moved],
    [t('resultSkipped'), context.skipped],
    [t('failed'), context.failed],
    [t('reasonTimedOut'), context.timed_out],
    [t('files'), context.affected_file_count ?? context.file_count],
    [t('size'), context.total_size_bytes],
  ]
    .filter((row): row is [string, unknown] => row[1] !== null && row[1] !== undefined && row[1] !== '')
    .map(([label, value]) => ({ label, value: String(value) }))
}

function eventLabel(event: ActivityEvent, t: TFunction) {
  if (event.area === 'watch_organize' && event.action === 'return' && event.reason === 'unmatched') {
    return t('unmatchedSentToReview', { entity: translatedEntityLabel(t, event.entity_type) })
  }
  if (event.entity_type === 'transfer_job' && event.action === 'transfer') {
    if (event.status === 'queued') return t('transferQueued')
    if (event.status === 'started') return t('transferStarted')
    if (event.status === 'succeeded') return t('transferCompleted')
    if (event.status === 'skipped') return t('transferSkipped')
    return t('transferFailed')
  }
  if (event.entity_type === 'transfer_job' && event.action === 'cancel') return t('transferCancelled')
  if (event.entity_type === 'organize_session' && event.action === 'move_to_depot') {
    if (event.status === 'started') return t('organizeStarted')
    if (event.status === 'succeeded') return t('organizeCompleted')
    if (event.status === 'skipped') return t('organizeSkipped')
    return t('organizeFailed')
  }
  if (event.action === 'rename') return t('renamedEntity', { entity: translatedEntityLabel(t, event.entity_type) })
  if (event.action === 'delete') return t('deletedEntity', { entity: translatedEntityLabel(t, event.entity_type) })
  if (event.action === 'move_to_depot') return t('movedEntityToDepot', { entity: translatedEntityLabel(t, event.entity_type) })
  if (event.action === 'return') return t('returnedEntity', { entity: translatedEntityLabel(t, event.entity_type) })
  if (event.action === 'transfer') return t('transferredEntity', { entity: translatedEntityLabel(t, event.entity_type) })
  if (event.action === 'cancel') return t('cancelledEntity', { entity: translatedEntityLabel(t, event.entity_type) })
  return knownDisplayLabel(t, event.action)
}
