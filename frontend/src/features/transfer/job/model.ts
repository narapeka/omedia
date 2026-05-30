import type { TransferJob } from '@/api/types'

export const AUTO_REMOVE_STATUSES = new Set(['succeeded', 'skipped', 'cancelled'])

export function isActiveTransfer(job: TransferJob) {
  return job.status === 'queued' || job.status === 'running' || job.status === 'cancelling'
}

export function mergeUnique(current: string[], additions: string[]) {
  const next = [...current]
  for (const id of additions) {
    if (!next.includes(id)) next.push(id)
  }
  return next.length === current.length ? current : next
}

export function toggleSet(current: Set<string>, value: string, checked: boolean) {
  const next = new Set(current)
  if (checked) next.add(value)
  else next.delete(value)
  return next
}

