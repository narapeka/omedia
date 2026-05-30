import { useQuery } from '@tanstack/react-query'
import { listActivityEventHistory as listActivity } from '@/api/generated/activity/activity'
import type { ListActivityEventHistoryParams } from '@/api/types'

export const activityKeys = {
  root: ['activity'] as const,
  list: (params?: ListActivityEventHistoryParams) => ['activity', params ?? {}] as const,
}

export function useActivity(params?: ListActivityEventHistoryParams) {
  return useQuery({
    queryKey: activityKeys.list(params),
    queryFn: ({ signal }) => listActivity(params, { signal }),
  })
}
