import type { SourceCandidate } from '@/api/types'
import { metadataYear, stringValue } from '../display'

type ExtractedSearchNames = {
  chinese?: string
  english?: string
}

export function buildSearchSignature(query: string, year: string) {
  return JSON.stringify({ query: query.trim(), year: parseYear(year) })
}

export function formatOriginCountries(countries: string[] | null | undefined, locale: string) {
  const codes = uniqueTextParts((countries ?? []).map((country) => country.trim().toUpperCase())).filter(Boolean)
  if (codes.length === 0) return ''
  const names = codes.map((code) => regionName(code, locale))
  try {
    return new Intl.ListFormat(locale, { style: 'short', type: 'conjunction' }).format(names)
  } catch {
    return names.join(', ')
  }
}

function regionName(code: string, locale: string) {
  try {
    return new Intl.DisplayNames([locale], { type: 'region' }).of(code) ?? code
  } catch {
    return code
  }
}

export function formatPeople(people: string[] | null | undefined, limit?: number) {
  const names = uniqueTextParts((people ?? []).map((name) => name.trim())).filter(Boolean)
  const visible = limit ? names.slice(0, limit) : names
  return visible.join('、')
}

export function searchSeed(sourceCandidate: SourceCandidate) {
  const metadata = sourceCandidate.match?.metadata ?? {}
  const fallbackQuery = normalizedSourceQuery(sourceCandidate)
  const query = combinedExtractedQuery(extractedSearchNames(sourceCandidate)) || fallbackQuery
  const year = evidenceYear(sourceCandidate) || metadataYear(metadata) || yearFromText(query) || yearFromText(fallbackQuery) || ''
  return { query, year, fallbackQuery }
}

export function parseYear(value: string) {
  const trimmed = value.trim()
  return /^\d{4}$/.test(trimmed) ? Number(trimmed) : null
}

function yearFromText(value: string) {
  return value.match(/\b((?:19|20)\d{2})\b/)?.[1]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function extractedSearchNames(sourceCandidate: SourceCandidate): ExtractedSearchNames {
  const result: ExtractedSearchNames = {}
  for (const item of evidenceSummary(sourceCandidate)) {
    if (stringValue(item.source) !== 'llm_hint' || !isRecord(item.values)) continue
    const titles = item.values.titles
    if (!Array.isArray(titles)) continue
    for (const title of titles) {
      if (!isRecord(title)) continue
      const value = stringValue(title.value)?.trim()
      if (!value) continue
      if (stringValue(title.kind) === 'chinese' && !result.chinese) result.chinese = value
      if (stringValue(title.kind) === 'english' && !result.english) result.english = value
    }
  }
  return result
}

function combinedExtractedQuery(names: ExtractedSearchNames) {
  return uniqueTextParts([names.chinese, names.english]).join(' ')
}

function evidenceYear(sourceCandidate: SourceCandidate) {
  for (const source of ['llm_hint', 'source_hint']) {
    for (const item of evidenceSummary(sourceCandidate)) {
      if (stringValue(item.source) !== source || !isRecord(item.values)) continue
      const year = parseYear(String(item.values.year ?? ''))
      if (year) return String(year)
    }
  }
  return ''
}

function evidenceSummary(sourceCandidate: SourceCandidate): Record<string, unknown>[] {
  const summary = sourceCandidate.match?.evidence?.summary
  return Array.isArray(summary) ? summary.filter(isRecord) : []
}

function normalizedSourceQuery(sourceCandidate: SourceCandidate) {
  const rawName = (sourceCandidate.display_name || basename(sourceCandidate.source_path) || '').trim()
  return rawName
    .replace(/\.(?:mkv|mp4|avi|mov|wmv|m4v|ts|m2ts|srt|ass|ssa|sub|idx|nfo)$/i, '')
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function basename(path: string) {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path
}

export function uniqueTextParts(parts: Array<string | undefined>) {
  const seen = new Set<string>()
  const result: string[] = []
  for (const part of parts) {
    const value = part?.trim()
    if (!value) continue
    const key = value.toLocaleLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    result.push(value)
  }
  return result
}

