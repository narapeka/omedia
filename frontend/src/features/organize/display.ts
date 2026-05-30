import { knownDisplayLabel, type TFunction } from '@/app/i18n/labels'
import type { BadgeTone } from '@/components/common/Badge'

export function formatBytes(value: number | null | undefined) {
  if (value == null) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value >= 1000 * 1024 * 1024) return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export function formatUnixSeconds(value: number | null | undefined, locale = 'en-US') {
  if (value == null) return '-'
  const date = new Date(value * 1000)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function humanize(value: string | null | undefined, t?: TFunction) {
  if (!value) return '-'
  if (t) return knownDisplayLabel(t, value)
  return value.replaceAll('_', ' ')
}

export function sourceDisplayName(path: string) {
  const name = path.split(/[\\/]/).filter(Boolean).at(-1) ?? path
  return name.replace(/\.[^.]+$/, '') || name
}

export function metadataTitle(metadata: unknown) {
  if (isRecord(metadata)) {
    return stringValue(metadata.title) ?? stringValue(metadata.name) ?? stringValue(metadata.original_title) ?? '-'
  }
  return '-'
}

export function metadataYear(metadata: unknown) {
  if (!isRecord(metadata)) return ''
  return stringValue(metadata.release_year) ?? stringValue(metadata.year) ?? ''
}

export function evidenceText(evidence: Record<string, unknown> | null | undefined) {
  if (!evidence) return 'No evidence'
  const summary = evidence.summary
  if (Array.isArray(summary) && summary.length > 0) {
    return summary.map(evidenceSummaryText).join(' | ')
  }
  const scan = evidence.scan
  if (isRecord(scan)) {
    const parts = [
      stringValue(scan.display_name),
      stringValue(scan.structure),
      typeof scan.file_count === 'number' ? `${scan.file_count} file${scan.file_count === 1 ? '' : 's'}` : undefined,
    ].filter(Boolean)
    return parts.join(' | ') || 'Scanned'
  }
  return 'No evidence'
}

export function statusTone(status: string): BadgeTone | undefined {
  if (status === 'active' || status === 'matched' || status === 'planned_primary' || status === 'planned_video' || status === 'planned_subtitle') {
    return 'success'
  }
  if (status === 'deleted' || status === 'missing' || status === 'blocked' || status === 'unavailable') return 'danger'
  if (status.includes('ignored') || status.includes('unsupported') || status.includes('unplanned')) return 'warning'
  return undefined
}

export function confidenceTone(confidence: string): BadgeTone {
  if (confidence === 'high') return 'success'
  if (confidence === 'medium') return 'warning'
  if (confidence === 'none') return 'danger'
  return 'danger'
}

export function blockerText(blockers: string[] | null | undefined, t?: TFunction) {
  if (!blockers?.length) return ''
  return blockers.map((blocker) => humanize(blocker, t)).join(', ')
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function stringValue(value: unknown) {
  if (typeof value === 'number') return String(value)
  return typeof value === 'string' && value ? value : undefined
}

function evidenceSummaryText(value: unknown) {
  if (!isRecord(value)) return String(value)
  return [stringValue(value.source), stringValue(value.confidence), stringValue(value.reason)].filter(Boolean).join(' | ')
}
