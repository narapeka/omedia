import type { ActivityEvent } from '@/api/types'

export function appendUniqueEvents(current: ActivityEvent[], next: ActivityEvent[]) {
  const seen = new Set(current.map((event) => event.id))
  return [
    ...current,
    ...next.filter((event) => {
      if (seen.has(event.id)) return false
      seen.add(event.id)
      return true
    }),
  ]
}

