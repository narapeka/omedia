import type { RuleReferenceGenre, RuleReferences } from '@/api/types'

export type RuleReferenceOption = {
  value: string
  label: string
  description?: string
  keywords?: string[]
}

export const emptyRuleReferences: RuleReferences = {
  movie_genres: [],
  tv_genres: [],
  countries: [],
  source: 'bundled',
}

export function normalizeRuleReferences(remote?: RuleReferences | null): RuleReferences {
  return {
    movie_genres: remote?.movie_genres ?? [],
    tv_genres: remote?.tv_genres ?? [],
    countries: remote?.countries ?? [],
    source: remote?.source || 'bundled',
  }
}

export function genreReferenceOptions(references: RuleReferences, locale: string): RuleReferenceOption[] {
  const byId = new Map<string, { id: number; names: Set<string>; mediaTypes: Set<string> }>()
  for (const [mediaType, genres] of [
    ['Movie', references.movie_genres ?? []],
    ['TV', references.tv_genres ?? []],
  ] as const) {
    for (const genre of genres) {
      const key = String(genre.id)
      const item = byId.get(key) ?? { id: genre.id, names: new Set<string>(), mediaTypes: new Set<string>() }
      item.names.add(localizedGenreName(genre, locale))
      item.mediaTypes.add(mediaType)
      byId.set(key, item)
    }
  }
  return Array.from(byId.values())
    .sort((left, right) => left.id - right.id)
    .map((item) => {
      const [label] = Array.from(item.names)
      const mediaTypes = Array.from(item.mediaTypes).join(' / ')
      return {
        value: String(item.id),
        label,
        description: `${item.id} - ${mediaTypes}`,
        keywords: Array.from(item.names),
      }
    })
}

export function countryReferenceOptions(references: RuleReferences, locale: string): RuleReferenceOption[] {
  const displayNames = regionDisplayNames(locale)
  return (references.countries ?? [])
    .map((country) => {
      const code = country.iso_3166_1.toUpperCase()
      const localized = displayNames?.of(code)
      const label = locale.startsWith('zh') ? country.native_name || localized || country.english_name || code : localized || country.english_name || code
      const description = [code, country.english_name].filter(Boolean).join(' - ')
      return {
        value: code,
        label,
        description,
        keywords: [country.english_name, country.native_name ?? ''],
      }
    })
    .sort((left, right) => left.value.localeCompare(right.value))
}

function localizedGenreName(genre: RuleReferenceGenre, locale: string) {
  const localized = genre as RuleReferenceGenre & { name_zh?: string; nameZh?: string }
  if (locale.startsWith('zh')) return localized.name_zh || localized.nameZh || genre.name
  return genre.name
}

function regionDisplayNames(locale: string) {
  try {
    return new Intl.DisplayNames([locale], { type: 'region' })
  } catch {
    return null
  }
}

