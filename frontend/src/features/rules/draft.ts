import type { MessageKey } from '@/app/i18n/messages'
import type { OrganizeRuleDraft, OrganizeRule, RuleOperator, RuleReferences, TransferRuleDraft, TransferRule } from '@/api/types'
import { countryReferenceOptions, genreReferenceOptions, type RuleReferenceOption } from './references'
import type { RuleTemplate } from './template'

export type RuleKind = 'organize' | 'transfer'
export type RuleSelection = { kind: RuleKind; id: string }
export type RuleRow = { kind: RuleKind; rule: OrganizeRule | TransferRule }
export type ConditionDraft = { field: string; op: string; value: string }
export type CategoryDraft = { name: string; bucket: string; conditions: ConditionDraft[] }
export type RuleDraft = {
  id: string
  name: string
  description: string
  fallback_bucket: string
  categories: CategoryDraft[]
}
export type RuleMutationPayload = OrganizeRuleDraft | TransferRuleDraft

const organizeFieldOptions = [
  { value: 'tmdb.genre_ids', labelKey: 'fieldTmdbGenreIds' },
  { value: 'tmdb.origin_country', labelKey: 'fieldTmdbOriginCountry' },
  { value: 'tmdb.release_year', labelKey: 'fieldTmdbReleaseYear' },
  { value: 'relative_path', labelKey: 'fieldRelativePath' },
]
const transferFieldOptions = [{ value: 'relative_path', labelKey: 'fieldRelativePath' }]
const conditionOperators: Record<RuleKind, Record<string, string[]>> = {
  organize: {
    'tmdb.genre_ids': ['contains', 'in'],
    'tmdb.origin_country': ['contains', 'in'],
    'tmdb.release_year': ['equals', 'in_range'],
    relative_path: ['contains', 'matches'],
  },
  transfer: {
    relative_path: ['contains', 'matches'],
  },
}
const operatorLabelKeys: Record<string, MessageKey> = {
  contains: 'operatorContains',
  in: 'operatorIn',
  equals: 'operatorEquals',
  matches: 'operatorMatches',
  in_range: 'operatorInRange',
}
export const bucketVariableOptions = ['{first_char}', '{decade}']

export function updateCondition(category: CategoryDraft, index: number, condition: ConditionDraft) {
  return { ...category, conditions: category.conditions.map((item, currentIndex) => (currentIndex === index ? condition : item)) }
}

export function bucketHelpText(t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string) {
  return t('bucketTargetHelp')
}

export function fallbackBucketHelpText(t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string) {
  return t('bucketTargetHelp')
}

export function toggleCollapsedCategoryIndex(current: Set<number>, categoryIndex: number) {
  const next = new Set(current)
  if (next.has(categoryIndex)) next.delete(categoryIndex)
  else next.add(categoryIndex)
  return next
}

export function shiftCollapsedCategoryIndexes(current: Set<number>, removedCategoryIndex: number) {
  const next = new Set<number>()
  current.forEach((categoryIndex) => {
    if (categoryIndex < removedCategoryIndex) next.add(categoryIndex)
    if (categoryIndex > removedCategoryIndex) next.add(categoryIndex - 1)
  })
  return next
}

export function toDraft(rule: OrganizeRule | TransferRule): RuleDraft {
  return {
    id: rule.id,
    name: rule.name,
    description: rule.description ?? '',
    fallback_bucket: rule.fallback_bucket ?? '',
    categories: (rule.categories ?? []).map((category) => ({
      name: category.name,
      bucket: category.bucket,
      conditions: (category.conditions ?? []).map((condition) => ({
        field: condition.field,
        op: condition.op,
        value: stringifyConditionValue(condition.value),
      })),
    })),
  }
}

export function applyTemplateToDraft(draft: RuleDraft, template: RuleTemplate): RuleDraft {
  return {
    id: draft.id,
    name: draft.name,
    description: draft.description,
    fallback_bucket: template.fallbackBucket,
    categories: template.categories.map((category) => ({
      name: category.name,
      bucket: category.bucket,
      conditions: category.conditions.map((condition) => ({
        field: condition.field,
        op: condition.op,
        value: stringifyConditionValue(condition.value),
      })),
    })),
  }
}

export function fromDraft(draft: RuleDraft): RuleMutationPayload {
  const categoryNames = generatedCategoryNames(draft.categories)
  return {
    name: draft.name.trim(),
    description: draft.description || null,
    fallback_bucket: draft.fallback_bucket,
    categories: draft.categories.map((category, index) => ({
      name: categoryNames[index],
      bucket: category.bucket,
      conditions: category.conditions.map((condition) => ({
        field: condition.field,
        op: condition.op as RuleOperator,
        value: parseConditionValue(condition.value),
      })),
    })),
  }
}

export function generatedCategoryNames(categories: CategoryDraft[]) {
  const used = new Set<string>()
  return categories.map((category, index) => {
    const base = generatedCategoryNameBase(category, index)
    let candidate = base
    let suffix = 2
    while (used.has(candidate)) {
      candidate = `${base}-${suffix}`
      suffix += 1
    }
    used.add(candidate)
    return candidate
  })
}

export function generatedCategoryNameBase(category: CategoryDraft, index: number) {
  const bucket = category.bucket.trim().replace(/[\\/]+/g, '-').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
  return bucket ? `category-${index + 1}-${bucket}` : `category-${index + 1}`
}

export function defaultRule(kind: RuleKind, t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string): OrganizeRule | TransferRule {
  return {
    id: '',
    name: t('newRuleName', { kind: kind === 'organize' ? t('organize') : t('transfer') }),
    description: null,
    fallback_bucket: '',
    categories: [],
  }
}

export function emptyCategory(): CategoryDraft {
  return { name: '', bucket: '', conditions: [emptyCondition()] }
}

export function emptyCondition(): ConditionDraft {
  return { field: '', op: '', value: '' }
}

export function fieldOptions(kind: RuleKind, t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string) {
  return (kind === 'organize' ? organizeFieldOptions : transferFieldOptions).map((option) => ({
    value: option.value,
    label: t(option.labelKey as MessageKey),
  }))
}

export function operatorOptions(kind: RuleKind, field: string, t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string) {
  return allowedOperators(kind, field).map((op) => ({ value: op, label: t(operatorLabelKeys[op] ?? 'operator') }))
}

export function allowedOperators(kind: RuleKind, field: string) {
  return conditionOperators[kind][field] ?? []
}

export function conditionWithField(kind: RuleKind, condition: ConditionDraft, field: string): ConditionDraft {
  const allowed = allowedOperators(kind, field)
  const op = allowed.includes(condition.op) ? condition.op : ''
  return { field, op, value: field === condition.field ? normalizeConditionValueForOperator(condition.value, op) : '' }
}

export function conditionWithOperator(condition: ConditionDraft, op: string): ConditionDraft {
  return { ...condition, op, value: normalizeConditionValueForOperator(condition.value, op) }
}

export function validateRuleDraft(draft: RuleDraft, kind: RuleKind, t: (key: MessageKey, values?: Record<string, number | string | null | undefined>) => string) {
  if (!draft.name.trim()) return t('ruleNameRequired')
  for (const category of draft.categories) {
    if (!category.bucket.trim()) return t('categoryBucketRequired')
    if (category.conditions.length === 0) return t('categoryConditionRequired')
    for (const condition of category.conditions) {
      if (!condition.field.trim()) return t('conditionFieldRequired')
      if (!condition.op.trim()) return t('conditionOperatorRequired')
      if (!allowedOperators(kind, condition.field).includes(condition.op)) return t('conditionOperatorUnsupported')
      if (!conditionValueHasContent(condition)) return t('conditionValueRequired')
    }
  }
  return ''
}

export function pruneBlankConditions(draft: RuleDraft): RuleDraft {
  return {
    ...draft,
    categories: draft.categories.map((category) => ({
      ...category,
      conditions: category.conditions.filter((condition) => !isBlankCondition(condition)),
    })),
  }
}

export function isBlankCondition(condition: ConditionDraft) {
  return !condition.field.trim() && !condition.op.trim() && !condition.value.trim()
}

export function conditionValueHasContent(condition: ConditionDraft) {
  const parsed = parseConditionValue(condition.value)
  if (condition.op === 'in') {
    if (Array.isArray(parsed)) return parsed.length > 0 && parsed.every(conditionValueItemHasContent)
    return conditionValueItemHasContent(parsed)
  }
  return condition.value.trim().length > 0
}

export function conditionValueItemHasContent(value: unknown) {
  return value !== null && value !== undefined && String(value).trim().length > 0
}

export function referenceOptionsForCondition(condition: ConditionDraft, references: RuleReferences, locale: string) {
  if (condition.op !== 'contains' && condition.op !== 'in') return []
  if (condition.field === 'tmdb.genre_ids') return genreReferenceOptions(references, locale)
  if (condition.field === 'tmdb.origin_country') return countryReferenceOptions(references, locale)
  return []
}

export function selectedReferenceValues(condition: ConditionDraft) {
  const parsed = parseConditionValue(condition.value)
  if (condition.op === 'in') {
    if (Array.isArray(parsed)) return parsed.map((value) => normalizeReferenceValue(condition.field, value)).filter(Boolean)
    return condition.value.trim() ? [normalizeReferenceValue(condition.field, parsed)].filter(Boolean) : []
  }
  return condition.value.trim() ? [normalizeReferenceValue(condition.field, parsed)].filter(Boolean) : []
}

export function normalizeReferenceValue(field: string, value: unknown) {
  if (value === null || value === undefined || value === '') return ''
  if (field === 'tmdb.genre_ids') {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? String(numeric) : ''
  }
  if (field === 'tmdb.origin_country') return String(value).trim().toUpperCase()
  return String(value)
}

export function formatReferenceValue(field: string, op: string, values: string[]) {
  const cleaned = values.map((value) => normalizeReferenceValue(field, value)).filter(Boolean)
  if (op !== 'in') return cleaned[0] ?? ''
  if (field === 'tmdb.genre_ids') return `[${cleaned.map(Number).join(', ')}]`
  return JSON.stringify(cleaned)
}

export function normalizeConditionValueForOperator(value: string, op: string) {
  const parsed = parseConditionValue(value)
  if (op === 'in') {
    if (Array.isArray(parsed)) return value
    if (value.trim()) return JSON.stringify([parsed])
    return ''
  }
  if (Array.isArray(parsed)) return parsed.length ? stringifyConditionValue(parsed[0]) : ''
  return value
}

export function filterReferenceOptions(options: RuleReferenceOption[], query: string) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery) return options
  return options.filter((option) => {
    const haystack = [option.value, option.label, option.description, ...(option.keywords ?? [])].join(' ').toLocaleLowerCase()
    return haystack.includes(normalizedQuery)
  })
}

export function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
}

export function parseConditionValue(value: string): unknown {
  const trimmed = value.trim()
  if (!trimmed) return ''
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

export function stringifyConditionValue(value: unknown) {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

