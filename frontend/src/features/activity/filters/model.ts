import type { MessageKey } from '@/app/i18n/messages'
import { activityAreaLabel, knownDisplayLabel, type TFunction } from '@/app/i18n/labels'
import type { ActivityAction, ActivityArea, ActivityStatus, ListActivityEventHistoryParams } from '@/api/types'

export type HistoryGroupFilter = '' | 'organize' | 'file_operations' | 'transfer' | 'automation'
export type HistoryFocusFilter = '' | 'attention' | 'failed' | 'unmatched'
export type HistoryTimeRangeFilter = '' | 'today' | 'week' | '30d' | 'custom'

export type ActivityFilterDraft = {
  q: string
  group: HistoryGroupFilter
  focus: HistoryFocusFilter
  timeRange: HistoryTimeRangeFilter
  from: string
  to: string
  area: string
  action: string
  status: string
  reason: string
  originId: string
  depotId: string
  libraryPath: string
  mediaType: string
  tmdbId: string
}

export const emptyActivityFilters: ActivityFilterDraft = {
  q: '',
  group: '',
  focus: '',
  timeRange: '',
  from: '',
  to: '',
  area: '',
  action: '',
  status: '',
  reason: '',
  originId: '',
  depotId: '',
  libraryPath: '',
  mediaType: '',
  tmdbId: '',
}

const groupValues = new Set<HistoryGroupFilter>(['', 'organize', 'file_operations', 'transfer', 'automation'])
const focusValues = new Set<HistoryFocusFilter>(['', 'attention', 'failed', 'unmatched'])
const timeRangeValues = new Set<HistoryTimeRangeFilter>(['', 'today', 'week', '30d', 'custom'])
const areas = new Set(['manual_organize', 'watch_organize', 'file_management', 'manual_transfer', 'scheduled_transfer'])
const actions = new Set(['identify', 'move_to_depot', 'return', 'transfer', 'rename', 'delete', 'cancel'])
const statuses = new Set(['queued', 'started', 'succeeded', 'failed', 'skipped'])
const mediaTypes = new Set(['movie', 'tv'])
const defaultHistoryLimit = 250

export function activityFiltersFromSearch(search: Partial<ActivityFilterDraft>): ActivityFilterDraft {
  return { ...emptyActivityFilters, ...search }
}

export function normalizeActivitySearch(search: Record<string, unknown>): Partial<ActivityFilterDraft> {
  const group = stringValue(search.group)
  const focus = stringValue(search.focus || search.result)
  const timeRange = stringValue(search.timeRange)
  const from = dateValue(search.from)
  const to = dateValue(search.to)
  return cleanActivitySearch({
    q: stringValue(search.q),
    group: groupValues.has(group as HistoryGroupFilter) ? (group as HistoryGroupFilter) : '',
    focus: focusValues.has(focus as HistoryFocusFilter) ? (focus as HistoryFocusFilter) : '',
    timeRange: timeRangeValues.has(timeRange as HistoryTimeRangeFilter) ? (timeRange as HistoryTimeRangeFilter) : from || to ? 'custom' : '',
    from,
    to,
    area: stringValue(search.area),
    action: stringValue(search.action),
    status: stringValue(search.status),
    reason: stringValue(search.reason),
    originId: stringValue(search.originId),
    depotId: stringValue(search.depotId),
    libraryPath: stringValue(search.libraryPath),
    mediaType: stringValue(search.mediaType),
    tmdbId: stringValue(search.tmdbId),
  })
}

export function cleanActivitySearch(filters: Partial<ActivityFilterDraft>): Partial<ActivityFilterDraft> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== ''),
  ) as Partial<ActivityFilterDraft>
}

export function buildActivityParams(filters: ActivityFilterDraft): ListActivityEventHistoryParams {
  const { fromAt, toAt } = historyTimeBounds(filters)
  const area = activityAreasForFilters(filters)
  return {
    area,
    group: filters.group || undefined,
    focus: filters.focus || undefined,
    action: actions.has(filters.action) ? (filters.action as ActivityAction) : undefined,
    status: statuses.has(filters.status) ? (filters.status as ActivityStatus) : undefined,
    reason: filters.reason || undefined,
    origin_id: filters.originId || undefined,
    depot_id: filters.depotId || undefined,
    library_path: filters.libraryPath || undefined,
    media_type: mediaTypes.has(filters.mediaType) ? (filters.mediaType as 'movie' | 'tv') : undefined,
    tmdb_id: filters.tmdbId || undefined,
    q: filters.q || undefined,
    from_at: fromAt,
    to_at: toAt,
    limit: defaultHistoryLimit,
  } as ListActivityEventHistoryParams
}

export function hasAdvancedActivityFilters(filters: ActivityFilterDraft) {
  return Boolean(
    filters.area ||
    filters.action ||
    filters.status ||
    filters.reason ||
    filters.originId ||
    filters.depotId ||
    filters.libraryPath ||
    filters.mediaType ||
    filters.tmdbId ||
    filters.from ||
    filters.to,
  )
}

export function historyTimeBounds(filters: ActivityFilterDraft, now = new Date()) {
  if (filters.timeRange === 'today') {
    return { fromAt: startOfLocalDay(now).toISOString(), toAt: undefined }
  }
  if (filters.timeRange === 'week') {
    return { fromAt: startOfLocalWeek(now).toISOString(), toAt: undefined }
  }
  if (filters.timeRange === '30d') {
    const start = new Date(now)
    start.setDate(start.getDate() - 30)
    return { fromAt: start.toISOString(), toAt: undefined }
  }
  if (filters.timeRange === 'custom') {
    return {
      fromAt: filters.from ? localDateStart(filters.from).toISOString() : undefined,
      toAt: filters.to ? localDateEnd(filters.to).toISOString() : undefined,
    }
  }
  return { fromAt: undefined, toAt: undefined }
}

function activityAreasForFilters(filters: ActivityFilterDraft): ActivityArea[] | undefined {
  if (areas.has(filters.area)) return [filters.area as ActivityArea]
  return undefined
}

function startOfLocalDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function startOfLocalWeek(date: Date) {
  const start = startOfLocalDay(date)
  const day = start.getDay()
  const mondayOffset = day === 0 ? -6 : 1 - day
  start.setDate(start.getDate() + mondayOffset)
  return start
}

function localDateStart(value: string) {
  return new Date(`${value}T00:00:00`)
}

function localDateEnd(value: string) {
  return new Date(`${value}T23:59:59.999`)
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function dateValue(value: unknown) {
  const text = stringValue(value)
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : ''
}


export const quickFilters: Array<{
  key: string
  labelKey: MessageKey
  patch: Pick<ActivityFilterDraft, 'group' | 'focus'>
}> = [
  { key: 'all', labelKey: 'all', patch: { group: '', focus: '' } },
  { key: 'attention', labelKey: 'needsAttention', patch: { group: '', focus: 'attention' } },
  { key: 'unmatched', labelKey: 'unmatched', patch: { group: '', focus: 'unmatched' } },
  { key: 'failed', labelKey: 'failed', patch: { group: '', focus: 'failed' } },
  { key: 'organize', labelKey: 'organize', patch: { group: 'organize', focus: '' } },
  { key: 'transfer', labelKey: 'transfer', patch: { group: 'transfer', focus: '' } },
  { key: 'automation', labelKey: 'automation', patch: { group: 'automation', focus: '' } },
  { key: 'file-operations', labelKey: 'fileOperations', patch: { group: 'file_operations', focus: '' } },
]

export const timeFilters: Array<{ value: HistoryTimeRangeFilter; labelKey: MessageKey }> = [
  { value: '', labelKey: 'allTime' },
  { value: 'today', labelKey: 'today' },
  { value: 'week', labelKey: 'thisWeek' },
  { value: '30d', labelKey: 'last30Days' },
]

export const activityActions = ['', 'identify', 'move_to_depot', 'return', 'transfer', 'rename', 'delete', 'cancel']
export const activityStatuses = ['', 'queued', 'started', 'succeeded', 'skipped', 'failed']
export const activityReasons = [
  '',
  'unmatched',
  'source_missing',
  'blocked',
  'timed_out',
  'resolve_disabled',
  'interrupted',
]

export function advancedFilterCount(filters: ActivityFilterDraft) {
  return [
    filters.area,
    filters.action,
    filters.status,
    filters.reason,
    filters.originId,
    filters.depotId,
    filters.libraryPath,
    filters.mediaType,
    filters.tmdbId,
    filters.from,
    filters.to,
  ].filter(Boolean).length
}

export function hasActiveFilters(filters: ActivityFilterDraft) {
  return Object.values(filters).some(Boolean)
}

export function activityAreaOptions(t: TFunction) {
  return [
    { value: '', label: t('any') },
    { value: 'manual_organize', label: activityAreaLabel(t, 'manual_organize') },
    { value: 'watch_organize', label: activityAreaLabel(t, 'watch_organize') },
    { value: 'file_management', label: activityAreaLabel(t, 'file_management') },
    { value: 'manual_transfer', label: activityAreaLabel(t, 'manual_transfer') },
    { value: 'scheduled_transfer', label: activityAreaLabel(t, 'scheduled_transfer') },
  ]
}

export function actionOptionLabel(t: TFunction, value: string) {
  if (value === 'move_to_depot') return t('depot')
  if (value === 'return') return t('sendBack')
  return knownDisplayLabel(t, value)
}
