import type { DepotSummary } from '@/api/types'
import type { TFunction } from '@/app/i18n/labels'

export type TransferAutomationDraft = {
  schedule: string
}

export type ScheduleMode = 'daily' | 'weekly' | 'monthly' | 'advanced'

export type CronDraft = {
  mode: ScheduleMode
  time: string
  weekday: string
  monthDay: string
}

export const DEFAULT_CRON = '0 4 * * *'

export const WEEKDAY_OPTIONS = [
  { value: '0', label: 'Monday' },
  { value: '1', label: 'Tuesday' },
  { value: '2', label: 'Wednesday' },
  { value: '3', label: 'Thursday' },
  { value: '4', label: 'Friday' },
  { value: '5', label: 'Saturday' },
  { value: '6', label: 'Sunday' },
]

export function weekdayOptions(t: TFunction) {
  return [
    { value: '0', label: t('monday') },
    { value: '1', label: t('tuesday') },
    { value: '2', label: t('wednesday') },
    { value: '3', label: t('thursday') },
    { value: '4', label: t('friday') },
    { value: '5', label: t('saturday') },
    { value: '6', label: t('sunday') },
  ]
}

export function buildTransferDrafts(depots: DepotSummary[]) {
  return Object.fromEntries(depots.map((depot) => [depot.id, depotToTransferDraft(depot)]))
}

export function depotToTransferDraft(depot: DepotSummary): TransferAutomationDraft {
  return {
    schedule: depot.policy.schedule ?? '',
  }
}

export function isTransferDraftDirty(depot: DepotSummary, draft: TransferAutomationDraft | undefined) {
  if (!draft) return false
  const saved = depotToTransferDraft(depot)
  return draft.schedule.trim() !== saved.schedule.trim()
}

export function transferDraftError(draft: TransferAutomationDraft | undefined, t?: TFunction) {
  if (!draft?.schedule.trim()) return ''
  return supportedCronError(draft.schedule, t)
}

export function scheduleDisplayLabel(value: string, t: TFunction) {
  const schedule = value.trim()
  if (!schedule) return t('manualOnly')

  const parsed = parseCronSchedule(schedule)
  if (parsed.mode === 'daily') return `${t('daily')} ${parsed.time}`
  if (parsed.mode === 'weekly') {
    const weekday = weekdayOptions(t).find((option) => option.value === parsed.weekday)?.label ?? parsed.weekday
    return `${t('weekly')} ${weekday} ${parsed.time}`
  }
  if (parsed.mode === 'monthly') return `${t('monthly')} ${parsed.monthDay} ${parsed.time}`
  return schedule
}

export function parseCronSchedule(value: string): CronDraft {
  const fields = value.trim().split(/\s+/)
  if (fields.length !== 5) return { mode: 'advanced', time: '04:00', weekday: '0', monthDay: '1' }

  const [minute, hour, day, month, weekday] = fields
  const time = cronTime(minute, hour)
  if (!time) return { mode: 'advanced', time: '04:00', weekday: '0', monthDay: '1' }
  if (day === '*' && month === '*' && weekday === '*') return { mode: 'daily', time, weekday: '0', monthDay: '1' }
  if (day === '*' && month === '*' && isIntegerInRange(weekday, 0, 6)) return { mode: 'weekly', time, weekday, monthDay: '1' }
  if (isIntegerInRange(day, 1, 31) && month === '*' && weekday === '*') return { mode: 'monthly', time, weekday: '0', monthDay: day }
  return { mode: 'advanced', time, weekday: '0', monthDay: '1' }
}

export function buildCronSchedule(draft: CronDraft) {
  const [hour, minute] = draft.time.split(':').map((part) => Number.parseInt(part, 10))
  const minuteText = Number.isFinite(minute) ? String(minute) : '0'
  const hourText = Number.isFinite(hour) ? String(hour) : '4'
  if (draft.mode === 'weekly') return `${minuteText} ${hourText} * * ${draft.weekday}`
  if (draft.mode === 'monthly') return `${minuteText} ${hourText} ${clampMonthDay(draft.monthDay)} * *`
  return `${minuteText} ${hourText} * * *`
}

export function clampMonthDay(value: string) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) return '1'
  return String(Math.min(31, Math.max(1, parsed)))
}

function cronTime(minute: string, hour: string) {
  if (!isIntegerInRange(minute, 0, 59) || !isIntegerInRange(hour, 0, 23)) return ''
  return `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
}

function supportedCronError(value: string, t?: TFunction) {
  const fields = value.trim().split(/\s+/)
  if (fields.length !== 5) return t ? t('cronFiveFields') : 'Use a 5-field cron expression.'
  return fields.every(isSupportedCronField) ? '' : t ? t('unsupportedCronField') : 'Unsupported cron field.'
}

function isSupportedCronField(field: string) {
  if (field === '*') return true
  return field.split(',').every((part) => /^\d+$/.test(part) || /^\d+-\d+$/.test(part) || /^\*\/\d+$/.test(part))
}

function isIntegerInRange(value: string, min: number, max: number) {
  if (!/^\d+$/.test(value)) return false
  const parsed = Number.parseInt(value, 10)
  return parsed >= min && parsed <= max
}
