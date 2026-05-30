import { messages, type MessageKey } from '@/app/i18n/messages'

export type TFunction = (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string

export const defaultT: TFunction = (key, values) => {
  const text = messages['en-US'][key]
  if (!values) return text
  return text.replace(/\{(\w+)\}/g, (_match, valueKey: string) => {
    const value = values[valueKey]
    return value === null || value === undefined ? '' : String(value)
  })
}

const mediaTypeKeys = {
  movie: 'mediaMovie',
  tv: 'mediaTv',
} as const satisfies Record<string, MessageKey>

const triggerKeys = {
  manual: 'triggerManual',
  watch: 'triggerWatch',
  scheduled: 'triggerScheduled',
} as const satisfies Record<string, MessageKey>

const statusKeys = {
  active: 'statusActive',
  queued: 'statusQueued',
  started: 'statusStarted',
  running: 'statusRunning',
  stopped: 'statusStopped',
  error: 'statusError',
  cancelling: 'statusCancelling',
  succeeded: 'statusSucceeded',
  skipped: 'statusSkipped',
  failed: 'statusFailed',
  cancelled: 'statusCancelled',
  configured: 'statusConfigured',
  unconfigured: 'statusUnconfigured',
  missing: 'statusMissing',
  idle: 'statusIdle',
  scanning: 'statusScanning',
  scanned: 'statusScanned',
  identifying: 'statusIdentifying',
  identified: 'statusIdentified',
  organizing: 'statusOrganizing',
  conflict: 'statusConflict',
  unavailable: 'unavailable',
  unsupported: 'unsupported',
} as const satisfies Record<string, MessageKey>

const confidenceKeys = {
  high: 'confidenceHigh',
  medium: 'confidenceMedium',
  low: 'confidenceLow',
  none: 'confidenceNone',
} as const satisfies Record<string, MessageKey>

const reasonKeys = {
  unmatched: 'reasonUnmatched',
  source_missing: 'reasonSourceMissing',
  resolve_disabled: 'reasonOverwriteDisabled',
  depot_locked: 'reasonDepotBusy',
  depot_transfer_busy: 'reasonDepotBusy',
  timed_out: 'reasonTimedOut',
  user_cancelled: 'reasonUserCancelled',
  blocked: 'reasonBlocked',
  interrupted: 'reasonInterrupted',
} as const satisfies Record<string, MessageKey>

const activityAreaKeys = {
  manual_organize: 'areaManualOrganize',
  watch_organize: 'areaWatchOrganize',
  file_management: 'areaFileManagement',
  manual_transfer: 'areaManualTransfer',
  scheduled_transfer: 'areaScheduledTransfer',
} as const satisfies Record<string, MessageKey>

const entityKeys = {
  file: 'entityFile',
  folder: 'entityFolder',
  directory: 'entityFolder',
  media_item: 'entityMediaItem',
  organize_session: 'entityOrganizeSession',
  watch_run: 'entityWatchRun',
  transfer_job: 'entityTransferJob',
} as const satisfies Record<string, MessageKey>

const actionKeys = {
  identify: 'identify',
  organize: 'organize',
  transfer: 'transfer',
  rename: 'rename',
  delete: 'delete',
  cancel: 'cancel',
  scan: 'scan',
  move_to_depot: 'depot',
  return: 'sendBack',
  Depot: 'depot',
} as const satisfies Record<string, MessageKey>

const genericKeys = {
  file: 'file',
  regular_file: 'regularFile',
  directory: 'folder',
  folder: 'folder',
  candidate: 'candidate',
  video: 'video',
  subtitle: 'subtitle',
  generic_sidecar: 'sidecar',
  sidecar: 'sidecar',
  deleted: 'delete',
} as const satisfies Record<string, MessageKey>

export function mediaTypeLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, mediaTypeKeys, value)
}

export function triggerLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, triggerKeys, value)
}

export function statusLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, statusKeys, value)
}

export function confidenceLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, confidenceKeys, value || 'none')
}

export function reasonLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, reasonKeys, value)
}

export function activityAreaLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, activityAreaKeys, value)
}

export function entityLabel(t: TFunction, value: string | null | undefined) {
  return translateKnown(t, entityKeys, value)
}

export function knownDisplayLabel(t: TFunction, value: string | null | undefined) {
  return (
    mediaTypeLabel(t, value) ||
    triggerLabel(t, value) ||
    statusLabel(t, value) ||
    reasonLabel(t, value) ||
    activityAreaLabel(t, value) ||
    translateKnown(t, actionKeys, value) ||
    translateKnown(t, genericKeys, value) ||
    humanizeIdentifier(value)
  )
}

export function humanizeIdentifier(value: string | null | undefined) {
  if (!value) return '-'
  return value
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || '-'
}

export function formatCount(t: TFunction, key: MessageKey, count: number) {
  return t(key, { count })
}

export function categoryCountLabel(t: TFunction, count: number) {
  return t(count === 1 ? 'countCategory' : 'countCategories', { count })
}

export function fileCountLabel(t: TFunction, count: number) {
  return t(count === 1 ? 'countFile' : 'countFiles', { count })
}

function translateKnown(
  t: TFunction,
  labels: Partial<Record<string, MessageKey>>,
  value: string | null | undefined,
) {
  if (!value) return ''
  const key = labels[value]
  return key ? t(key) : ''
}
