import { defaultT, categoryCountLabel, knownDisplayLabel, mediaTypeLabel, statusLabel, type TFunction } from '@/app/i18n/labels'
import type { DepotCandidate, DepotCandidateActionOutcome, DepotCandidateKind, DepotDetail, DepotSummary, RuleCondition, TransferJob, TransferRule } from '@/api/types'
import { depotResolveMode } from '@/features/depot/model'
import { isActiveTransfer } from '../job/model'

export type DepotGroupView = {
  id: string
  name: string
  mediaType: DepotSummary['media_type']
  resolveMode: DepotSummary['resolve_mode']
  depotPath: string
  libraryPath: string
  transferRuleId: string | null
  transferRuleName: string
  transferRuleSummary: string
  trigger: string
  enabled: boolean
  pendingCount: number
  busyJob: TransferJob | null
  lastSuccess: TransferJob | null
  lastFailure: TransferJob | null
  canTransferNow: boolean
}

export type DepotTreeView = {
  depotId: string
  candidates: NonNullable<DepotDetail['candidates']>
  candidateCount: number
  fileCount: number
  blockedCount: number
  pendingCount: number
  totalSizeBytes: number
}

export function buildDepotGroups({
  depots,
  jobs,
  t = defaultT,
  transferRules,
}: {
  depots: DepotSummary[]
  jobs: TransferJob[]
  t?: TFunction
  transferRules: TransferRule[]
}): DepotGroupView[] {
  const activeJobByDepot = new Map(jobs.filter(isActiveTransfer).map((job) => [job.depot_id, job]))
  const ruleById = new Map(transferRules.map((rule) => [rule.id, rule]))
  return depots.map((depot) => {
    const rule = depot.policy.transfer_rule_id ? ruleById.get(depot.policy.transfer_rule_id) : undefined
    const pendingCount = depot.pending_count ?? 0
    const busyJob = activeJobByDepot.get(depot.id) ?? null
    const enabled = depot.enabled ?? true
    return {
      id: depot.id,
      name: depot.name,
      mediaType: depot.media_type,
      resolveMode: depotResolveMode(depot),
      depotPath: depot.path,
      libraryPath: depot.policy.target_library_path,
      transferRuleId: depot.policy.transfer_rule_id ?? null,
      transferRuleName: rule?.name ?? depot.policy.transfer_rule_id ?? t('none'),
      transferRuleSummary: ruleSummary(rule, t),
      trigger: depot.policy.trigger ?? 'manual',
      enabled,
      pendingCount,
      busyJob,
      lastSuccess: depot.last_successful_transfer ?? null,
      lastFailure: depot.last_failed_transfer ?? null,
      canTransferNow: enabled && pendingCount > 0 && !busyJob,
    }
  })
}

export function buildDepotTree(depot: DepotDetail | undefined): DepotTreeView | null {
  if (!depot) return null
  const candidates = depot.candidates ?? []
  return {
    depotId: depot.id,
    candidates,
    candidateCount: candidates.length,
    fileCount: candidates.reduce((total, candidate) => total + (candidate.file_count ?? candidate.files?.length ?? 0), 0),
    blockedCount: candidates.filter((candidate) => candidate.blocked_reason).length,
    pendingCount: depot.pending_count ?? 0,
    totalSizeBytes: candidates.reduce((total, candidate) => total + (candidate.size_bytes ?? 0), 0),
  }
}

function ruleSummary(rule: TransferRule | undefined, t: TFunction) {
  if (!rule) return t('none')
  const categoryCount = rule.categories?.length ?? 0
  const fallback = rule.fallback_bucket ? `, ${t('fallback').toLocaleLowerCase()} ${rule.fallback_bucket}` : ''
  return `${categoryCountLabel(t, categoryCount)}${fallback}`
}

export function depotCandidateKindLabel(kind: DepotCandidateKind | string | undefined, t?: TFunction) {
  if (!t) return kind === 'folder' ? 'Folder' : 'File'
  return kind === 'folder' ? t('folder') : t('file')
}

export function formatDepotBytes(value: number | null | undefined) {
  if (value === null || value === undefined) return '-'
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let current = value / 1024
  let unit = 0
  while (current >= 1024 && unit < units.length - 1) {
    current /= 1024
    unit += 1
  }
  return `${current.toFixed(current >= 10 ? 1 : 2)} ${units[unit]}`
}

export function formatDepotModifiedTime(value: number | null | undefined, locale = 'en-US') {
  if (!value) return '-'
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value * 1000))
}

export function depotCandidateCountSummary(candidate: DepotCandidate, t?: TFunction) {
  if (!t) {
    if (candidate.kind === 'file') return '1 file'
    const files = candidate.file_count ?? 0
    return `${files} file${files === 1 ? '' : 's'}`
  }
  if (candidate.kind === 'file') return t('countFiles', { count: 1 })
  const files = candidate.file_count ?? 0
  return t('countFiles', { count: files })
}

export function depotSelectionSummary(candidates: DepotCandidate[], selectedIds: Set<string>) {
  const selected = candidates.filter((candidate) => selectedIds.has(candidate.id))
  const files = selected.reduce((sum, candidate) => sum + (candidate.file_count ?? 0), 0)
  const media = selected.reduce((sum, candidate) => sum + (candidate.media_count ?? 0), 0)
  const size = selected.reduce((sum, candidate) => sum + (candidate.size_bytes ?? 0), 0)
  return { selected, files, media, size }
}

export function depotOutcomeMessage(outcome: DepotCandidateActionOutcome | null | undefined, t?: TFunction) {
  if (!outcome) return ''
  if (outcome.message) return outcome.message
  if (!t) {
    const action = outcome.action === 'rename' ? 'renamed' : outcome.action === 'delete' ? 'deleted' : 'updated'
    return `${outcome.scope === 'file' ? 'File' : 'Candidate'} ${action}: ${outcome.status}`
  }
  const action = outcome.action === 'rename' ? t('renamedEntity', { entity: '' }).trim() : outcome.action === 'delete' ? t('deletedEntity', { entity: '' }).trim() : t('updated')
  const scope = outcome.scope === 'file' ? t('file') : t('candidate')
  return `${scope} ${action}: ${statusLabel(t, outcome.status) || knownDisplayLabel(t, outcome.status)}`
}

export function depotErrorMessage(error: unknown) {
  if (!error) return ''
  if (error instanceof Error) return error.message
  if (typeof error === 'object') {
    const nested = (error as { error?: { message?: unknown }; message?: unknown }).error?.message
    if (typeof nested === 'string') return nested
    const message = (error as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  return String(error)
}

const DISPLAY_ONLY_EMPTY_ROOT_GROUP_CONFIDENCES = new Set(['ungrouped_root_file', 'ungrouped_root_folder'])

export function isDisplayOnlyEmptyRootGroupCandidate(candidate: DepotCandidate) {
  return (
    !candidate.group
    && candidate.kind === 'folder'
    && splitRelativePath(candidate.relative_path).length === 1
    && !candidate.blocked_reason
    && candidateFileCount(candidate) === 0
    && DISPLAY_ONLY_EMPTY_ROOT_GROUP_CONFIDENCES.has(candidate.path_split_confidence ?? '')
  )
}

export function isActionableDepotCandidate(candidate: DepotCandidate) {
  return !isDisplayOnlyEmptyRootGroupCandidate(candidate)
}

function candidateFileCount(candidate: DepotCandidate) {
  return candidate.file_count ?? candidate.files?.length ?? 0
}

function splitRelativePath(relativePath: string) {
  return relativePath.split(/[\\/]+/).filter(Boolean)
}

const systemFolderPattern = /^(.+?)(?: \((\d{4})\))?(?: \{tmdb-\d+\})?$/
const tmdbPattern = /\{tmdb-\d+\}/
const yearPattern = /\(\d{4}\)/

export function previewTransferRelativePath(relativePath: string, rule?: TransferRule | null) {
  const split = splitDepotRelativePath(relativePath)
  const bucket = matchTransferBucket(relativePath, rule, split.mediaRelativePath)
  return joinPath(split.organizePrefix, bucket, split.mediaRelativePath)
}

function matchTransferBucket(relativePath: string, rule: TransferRule | null | undefined, mediaRelativePath: string) {
  if (!rule) return ''
  const variables = parseVariables(mediaRelativePath)
  for (const category of rule.categories ?? []) {
    if (!(category.conditions ?? []).every((condition) => conditionMatches(condition, relativePath))) continue
    const rendered = renderBucket(category.bucket, variables)
    if (rendered !== null) return rendered
  }
  return renderBucket(rule.fallback_bucket ?? '', variables) ?? ''
}

function conditionMatches(condition: RuleCondition, relativePath: string) {
  const expected = String(condition.value ?? '')
  if (condition.field !== 'relative_path') return false
  if (condition.op === 'contains') return normalizeText(relativePath).includes(normalizeText(expected))
  if (condition.op === 'matches') {
    try {
      return new RegExp(expected, 'i').test(relativePath)
    } catch {
      return false
    }
  }
  return false
}

function normalizeText(value: string) {
  return value.toLowerCase()
}

function parseVariables(relativePath: string) {
  const [firstPart] = relativePath.split(/[\\/]/)
  const mediaRootName = firstPart && !relativePath.includes('/') && !relativePath.includes('\\') ? stemForDirectFile(firstPart) : firstPart
  const match = mediaRootName?.match(systemFolderPattern)
  if (!match) return {}
  const variables: Record<string, string> = {}
  const title = match[1]
  const year = match[2]
  if (title) variables.first_char = firstCharBucket(title)
  if (year) variables.decade = String(Math.floor(Number(year) / 10) * 10)
  return variables
}

function renderBucket(bucket: string, variables: Record<string, string>) {
  try {
    return bucket.replace(/\{([^{}]+)\}/g, (_match, name: string) => {
      if (!(name in variables)) throw new Error(name)
      return variables[name]
    })
  } catch {
    return null
  }
}

function splitDepotRelativePath(relativePath: string) {
  const normalized = relativePath.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  const parts = normalized ? normalized.split('/').filter(Boolean) : []
  if (!parts.length) return { organizePrefix: '', mediaRelativePath: '', mediaRootName: null, confidence: 'unknown' as const }
  for (let index = 0; index < parts.length - 1; index += 1) {
    if (!isSystemMediaRootName(parts[index])) continue
    return {
      organizePrefix: parts.slice(0, index).join('/'),
      mediaRelativePath: parts.slice(index).join('/'),
      mediaRootName: parts[index],
      confidence: 'system_marker' as const,
    }
  }
  if (parts.length === 1 && isSystemMediaRootName(stemForDirectFile(parts[0]))) {
    return { organizePrefix: '', mediaRelativePath: parts[0], mediaRootName: stemForDirectFile(parts[0]), confidence: 'system_marker' as const }
  }
  return {
    organizePrefix: '',
    mediaRelativePath: normalized,
    mediaRootName: parts.length === 1 ? stemForDirectFile(parts[0]) : parts[0],
    confidence: parts.length === 1 ? ('ungrouped_root_file' as const) : ('ungrouped_root_folder' as const),
  }
}

function isSystemMediaRootName(value: string) {
  return Boolean(value && (tmdbPattern.test(value) || yearPattern.test(value)) && systemFolderPattern.test(value))
}

function stemForDirectFile(value: string) {
  const index = value.lastIndexOf('.')
  return index > 0 ? value.slice(0, index) : value
}

function firstCharBucket(title: string) {
  const first = title.trim().charAt(0).toUpperCase()
  if (!first || /\d/.test(first)) return '0-9'
  return first >= 'A' && first <= 'Z' ? first : '0-9'
}

function joinPath(...parts: string[]) {
  return parts
    .map((part) => part.replace(/\\/g, '/').replace(/^\/+|\/+$/g, ''))
    .filter(Boolean)
    .join('/')
}

export function compareDepotsForPicker(left: DepotGroupView, right: DepotGroupView) {
  const leftTypeOrder = left.mediaType === 'movie' ? 0 : 1
  const rightTypeOrder = right.mediaType === 'movie' ? 0 : 1
  if (leftTypeOrder !== rightTypeOrder) return leftTypeOrder - rightTypeOrder
  return left.name.localeCompare(right.name)
}

export function manualDepotSelectionSummary(depots: DepotGroupView[], t: TFunction) {
  if (depots.length === 0) return t('countSelected', { count: 0 })
  const movieCount = depots.filter((depot) => depot.mediaType === 'movie').length
  const tvCount = depots.filter((depot) => depot.mediaType === 'tv').length
  return [
    movieCount ? `${mediaTypeLabel(t, 'movie')} ${movieCount}` : '',
    tvCount ? `${mediaTypeLabel(t, 'tv')} ${tvCount}` : '',
  ].filter(Boolean).join(' / ')
}

export function depotOptionIncrementalLabel(depot: DepotGroupView, t: TFunction) {
  return depot.mediaType === 'tv' && depot.resolveMode === 'incremental' ? t('resolveModeIncremental') : ''
}
