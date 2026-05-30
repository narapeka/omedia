import type { ActivityEvent, OrganizeRule, OrganizeSession } from '@/api/types'
import { statusLabel as translatedStatusLabel, triggerLabel, type TFunction } from '@/app/i18n/labels'
import type { BadgeTone } from '@/components/common/Badge'
import type { DepotConfigurationView } from '@/features/depot/model'
import type {
  OrganizeActivityRow,
  OrganizeOverview,
  PipelineRow,
  TransferOverview,
  TransferOverviewRow,
} from './types'

export function buildOrganizeAttention(sessions: OrganizeSession[]) {
  const attentionStates = new Set(['scanned', 'identified', 'identifying', 'organizing', 'error'])
  const attentionSessions = sessions.filter((session) => attentionStates.has(String(session.state)))
  return { sessions: attentionSessions, total: attentionSessions.length }
}

export function buildOrganizeOverview(
  events: ActivityEvent[],
  manualActionSessions: OrganizeSession[],
  t: TFunction,
): OrganizeOverview {
  const organizeEvents = events.filter(isOrganizeActivityEvent)
  const rows = organizeEvents.filter(isOrganizeOverviewRowEvent).slice(0, 8).map((event) => organizeActivityRow(event, t))
  return {
    rows,
    moved: organizeEvents.filter(isMovedOrganizeEvent).length,
    unknown: organizeEvents.filter(isUnknownOrganizeEvent).length,
    failed: organizeEvents.filter(isFailedActivityEvent).length,
    manualActionCount: manualActionSessions.length,
  }
}

export function buildTransferOverview(
  t: TFunction,
  events: ActivityEvent[] = [],
): TransferOverview {
  const eventRows = events.filter(isTransferActivityEvent).map((event) => transferEventOverviewRow(event, t))
  const rows = eventRows
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
    .slice(0, 10)
  return {
    rows,
  }
}

export function buildPipelineRows(depots: DepotConfigurationView[], organizeRules: OrganizeRule[], t: TFunction): PipelineRow[] {
  const organizeRuleById = new Map(organizeRules.map((rule) => [rule.id, rule]))
  return depots.flatMap((depot) => {
    if (depot.origins.length === 0) {
      return [
        {
          id: `${depot.id}:unlinked`,
          originName: t('noOrigin'),
          originPath: '-',
          organizeType: '-',
          organizeRuleName: '-',
          depotName: depot.name,
          depotPath: depot.depotPath,
          depotMediaType: depot.mediaType,
          depotIsIncremental: depot.mediaType === 'tv' && depot.resolveMode === 'incremental',
          transferType: formatPipelineTrigger(depot.trigger, t),
          transferRuleName: depot.transferRuleName === 'None' ? t('none') : depot.transferRuleName,
          libraryPath: depot.libraryPath,
        },
      ]
    }

    return depot.origins.map((origin) => ({
      id: `${depot.id}:${origin.id}`,
      originName: origin.name,
      originPath: origin.path,
      organizeType: formatPipelineTrigger(origin.trigger, t),
      organizeRuleName: origin.policy.organize_rule_id
        ? organizeRuleById.get(origin.policy.organize_rule_id)?.name ?? origin.policy.organize_rule_id
        : t('none'),
      depotName: depot.name,
      depotPath: depot.depotPath,
      depotMediaType: depot.mediaType,
      depotIsIncremental: depot.mediaType === 'tv' && depot.resolveMode === 'incremental',
      transferType: formatPipelineTrigger(depot.trigger, t),
      transferRuleName: depot.transferRuleName === 'None' ? t('none') : depot.transferRuleName,
      libraryPath: depot.libraryPath,
    }))
  })
}

function organizeActivityRow(event: ActivityEvent, t: TFunction): OrganizeActivityRow {
  const result = organizeResultLabel(event, t)
  const source = event.entity_source ?? ''
  const destination = isUnknownOrganizeEvent(event) ? event.entity_target ?? '.unknown' : event.entity_target ?? event.library_path ?? ''
  return {
    id: event.id,
    source: source || '-',
    sourceTitle: source,
    type: event.area === 'watch_organize' ? t('triggerWatch') : t('triggerManual'),
    result,
    statusValue: event.status,
    tone: activityTone(event),
    destination: destination || '-',
    destinationTitle: destination,
    updatedAt: event.time,
  }
}

function transferEventOverviewRow(event: ActivityEvent, t: TFunction): TransferOverviewRow {
  const source = event.entity_source ?? ''
  const destination = event.entity_target ?? event.library_path ?? ''
  return {
    id: event.id,
    depot: source || '-',
    type: event.area === 'scheduled_transfer' ? t('triggerScheduled') : t('triggerManual'),
    statusValue: event.status,
    tone: transferTone(event.status),
    result: transferEventResult(event, t),
    destination: destination || '-',
    destinationTitle: destination,
    updatedAt: event.time,
  }
}

function isOrganizeActivityEvent(event: ActivityEvent) {
  return event.area === 'manual_organize' || event.area === 'watch_organize'
}

function isOrganizeOverviewRowEvent(event: ActivityEvent) {
  return isMovedOrganizeEvent(event) || isUnknownOrganizeEvent(event) || isFailedActivityEvent(event) || event.status === 'skipped'
}

function isMovedOrganizeEvent(event: ActivityEvent) {
  return event.entity_type !== 'organize_session' && event.action === 'move_to_depot' && event.status === 'succeeded'
}

function isFailedActivityEvent(event: ActivityEvent) {
  return event.status === 'failed'
}

function isUnknownOrganizeEvent(event: ActivityEvent) {
  return event.area === 'watch_organize' && event.action === 'return' && event.reason === 'unmatched'
}

function isTransferActivityEvent(event: ActivityEvent) {
  return (event.area === 'manual_transfer' || event.area === 'scheduled_transfer') && event.entity_type === 'file'
}

function organizeResultLabel(event: ActivityEvent, t: TFunction) {
  if (isFailedActivityEvent(event)) return t('resultFailed')
  if (isUnknownOrganizeEvent(event)) return t('resultUnknown')
  if (event.status === 'skipped') return t('resultSkipped')
  if (isMovedOrganizeEvent(event)) return t('resultMoved')
  return statusLabel(event.status, t)
}

function activityTone(event: ActivityEvent): BadgeTone | undefined {
  if (isFailedActivityEvent(event)) return 'danger'
  if (event.status === 'skipped' || isUnknownOrganizeEvent(event)) return 'warning'
  if (event.status === 'succeeded') return 'success'
  return undefined
}

function transferTone(status: string): BadgeTone {
  if (status === 'failed') return 'danger'
  if (status === 'succeeded' || status === 'skipped' || status === 'cancelled') return 'success'
  return 'warning'
}

function transferEventResult(event: ActivityEvent, t: TFunction) {
  return statusLabel(event.status, t)
}

function statusLabel(value: string, t: TFunction) {
  return translatedStatusLabel(t, value) || humanize(value)
}

function formatPipelineTrigger(trigger: string | null | undefined, t: TFunction) {
  return triggerLabel(t, trigger) || t('triggerManual')
}

function humanize(value: string) {
  return value
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
