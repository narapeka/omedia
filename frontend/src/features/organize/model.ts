import { mediaTypeLabel, type TFunction } from '@/app/i18n/labels'
import type { DepotSummary, OriginSummary } from '@/api/types'

export function compareOriginsForPicker(left: OriginSummary, right: OriginSummary) {
  const leftTypeOrder = left.media_type === 'movie' ? 0 : 1
  const rightTypeOrder = right.media_type === 'movie' ? 0 : 1
  if (leftTypeOrder !== rightTypeOrder) return leftTypeOrder - rightTypeOrder
  return left.name.localeCompare(right.name)
}

export function manualOriginSelectionSummary(origins: OriginSummary[], t: TFunction) {
  if (origins.length === 0) return t('countSelected', { count: 0 })
  const movieCount = origins.filter((origin) => origin.media_type === 'movie').length
  const tvCount = origins.filter((origin) => origin.media_type === 'tv').length
  return [
    movieCount ? `${mediaTypeLabel(t, 'movie')} ${movieCount}` : '',
    tvCount ? `${mediaTypeLabel(t, 'tv')} ${tvCount}` : '',
  ].filter(Boolean).join(' / ')
}

export function adHocLauncherSummary(sourcePath: string, depot: DepotSummary | undefined, t: TFunction) {
  const source = sourcePath.trim() || t('sourcePath')
  const target = depot ? depot.name : t('targetDepot')
  return `${source} -> ${target}`
}

