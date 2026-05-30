import type { ActivityEvent } from '@/api/types'
import { entityLabel, knownDisplayLabel, reasonLabel, type TFunction } from '@/app/i18n/labels'

export type AutomationActivityItem = {
  id: string
  source: string
  status: string
  title: string
  detail: string
  createdAt: string
}

export function buildAutomationActivity(events: ActivityEvent[], t: TFunction): AutomationActivityItem[] {
  return events
    .filter((event) => event.area === 'watch_organize' || event.area === 'scheduled_transfer')
    .map((event) => ({
      id: event.id,
      source: event.area === 'scheduled_transfer' ? t('transfer') : t('watch'),
      status: event.status,
      title: eventLabel(event, t),
      detail: eventDetail(event, t),
      createdAt: event.time,
    }))
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
    .slice(0, 10)
}

export function activityTone(status: string) {
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'succeeded' || status === 'success') return 'success'
  if (status === 'skipped' || status === 'queued' || status === 'started' || status === 'running' || status === 'cancelling') return 'warning'
  return undefined
}

function eventDetail(event: ActivityEvent, t: TFunction) {
  if (event.reason) return reasonLabel(t, event.reason)
  const source = event.entity_source
  const target = event.entity_target ?? event.library_path
  if (source && target) return `${source} -> ${target}`
  if (source) return source
  if (target) return target
  return event.depot_name || event.origin_name || knownDisplayLabel(t, event.area)
}

function eventLabel(event: ActivityEvent, t: TFunction) {
  if (event.area === 'watch_organize' && event.reason === 'unmatched') return t('unmatchedMedia')
  if (event.area === 'watch_organize' && event.action === 'move_to_depot') {
    if (event.status === 'started') return t('organizeStarted')
    if (event.status === 'succeeded') return t('movedEntityToDepot', { entity: entityLabel(t, event.entity_type) })
    if (event.status === 'skipped') return t('organizeSkipped')
    return t('organizeFailed')
  }
  if (event.area === 'scheduled_transfer' && event.status === 'queued') return t('scheduledTransferQueued')
  if (event.area === 'scheduled_transfer' && event.status === 'started') return t('scheduledTransferStarted')
  if (event.area === 'scheduled_transfer' && event.status === 'succeeded') return t('scheduledTransferCompleted')
  return knownDisplayLabel(t, event.action)
}
