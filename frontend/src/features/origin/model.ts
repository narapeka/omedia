import type { OriginSummary } from '@/api/types'

export function isManualOrigin(origin: OriginSummary) {
  return origin.trigger !== 'watch'
}

export function compareOriginsByName(left: OriginSummary, right: OriginSummary) {
  const nameOrder = left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: 'base' })
  if (nameOrder !== 0) return nameOrder
  return left.id.localeCompare(right.id)
}

export function sortOriginsByName(origins: OriginSummary[]) {
  return [...origins].sort(compareOriginsByName)
}
