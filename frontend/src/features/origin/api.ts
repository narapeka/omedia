import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createOrigin as createOriginRequest,
  deleteOrigin,
  listOrigins,
  saveOrigin as saveOriginRequest,
} from '@/api/generated/origins/origins'
import type { Origin, OriginDraft, OriginSummary } from '@/api/types'
import { configKeys, invalidateConfigQueries } from '@/features/config/cache'

export const originKeys = {
  all: configKeys.origins,
  detail: (originId: string | undefined) => ['origin', originId] as const,
}

export function useOrigins() {
  return useQuery({
    queryKey: originKeys.all,
    queryFn: ({ signal }) => listOrigins({ signal }),
  })
}

export function useOriginActions() {
  const queryClient = useQueryClient()
  const invalidateConfig = () => invalidateConfigQueries(queryClient)
  const upsertOrigin = (origin: Origin) => {
    queryClient.setQueryData<OriginSummary[]>(originKeys.all, (current) => upsertById(current, origin))
  }
  const removeOrigin = (originId: string) => {
    queryClient.setQueryData<OriginSummary[]>(originKeys.all, (current) => removeById(current, originId))
  }

  return {
    saveOrigin: useMutation({
      mutationFn: ({ originId, data }: { originId: string; data: OriginDraft }) => saveOriginRequest(originId, data),
      onSuccess: (origin) => {
        upsertOrigin(origin)
        invalidateConfig()
      },
    }),
    createOrigin: useMutation({
      mutationFn: (data: OriginDraft) => createOriginRequest(data),
      onSuccess: (origin) => {
        upsertOrigin(origin)
        invalidateConfig()
      },
    }),
    deleteOrigin: useMutation({
      mutationFn: (originId: string) => deleteOrigin(originId),
      onSuccess: (_response, originId) => {
        removeOrigin(originId)
        invalidateConfig()
      },
    }),
  }
}

function upsertById<TItem extends { id: string }>(current: TItem[] | undefined, item: TItem) {
  if (!current) return current
  const index = current.findIndex((currentItem) => currentItem.id === item.id)
  if (index < 0) return [...current, item]
  return current.map((currentItem) => currentItem.id === item.id ? item : currentItem)
}

function removeById<TItem extends { id: string }>(current: TItem[] | undefined, itemId: string) {
  if (!current) return current
  return current.filter((currentItem) => currentItem.id !== itemId)
}
