import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createDepot as createDepotRequest,
  deleteDepot,
  deleteDepotCandidate,
  deleteDepotCandidateFile,
  depotCandidateDetail as getDepotCandidateDetail,
  depotCandidateFileDetail as getDepotCandidateFileDetail,
  depotDetail as getDepot,
  listDepots,
  renameDepotCandidate,
  renameDepotCandidateFile,
  returnDepotItems as returnItems,
  saveDepot as saveDepotRequest,
} from '@/api/generated/depots/depots'
import type {
  Depot,
  DepotDraft,
  DepotSummary,
  RenameRequest,
  ReturnRequest,
} from '@/api/types'
import { activityKeys } from '@/features/activity/api'
import { configKeys, invalidateConfigQueries } from '@/features/config/cache'

export const depotKeys = {
  all: configKeys.depots,
  detail: (depotId: string | undefined) => ['depot', depotId] as const,
}

export function useDepots() {
  return useQuery({
    queryKey: depotKeys.all,
    queryFn: ({ signal }) => listDepots({ signal }),
  })
}

export function useDepot(depotId: string | undefined) {
  return useQuery({
    queryKey: depotKeys.detail(depotId),
    queryFn: ({ signal }) => getDepot(required(depotId, 'depot id'), { signal }),
    enabled: Boolean(depotId),
  })
}

export function useDepotConfigActions() {
  const queryClient = useQueryClient()
  const invalidateConfig = () => invalidateConfigQueries(queryClient)
  const upsertDepot = (depot: Depot) => {
    queryClient.setQueryData<DepotSummary[]>(depotKeys.all, (current) => upsertById(current, depot))
  }
  const removeDepot = (depotId: string) => {
    queryClient.setQueryData<DepotSummary[]>(depotKeys.all, (current) => removeById(current, depotId))
  }

  return {
    saveDepot: useMutation({
      mutationFn: ({ depotId, data }: { depotId: string; data: DepotDraft }) => saveDepotRequest(depotId, data),
      onSuccess: (depot) => {
        upsertDepot(depot)
        invalidateConfig()
      },
    }),
    createDepot: useMutation({
      mutationFn: (data: DepotDraft) => createDepotRequest(data),
      onSuccess: (depot) => {
        upsertDepot(depot)
        invalidateConfig()
      },
    }),
    deleteDepot: useMutation({
      mutationFn: (depotId: string) => deleteDepot(depotId),
      onSuccess: (_response, depotId) => {
        removeDepot(depotId)
        invalidateConfig()
      },
    }),
  }
}

export function useDepotCandidateActions() {
  const queryClient = useQueryClient()
  const refreshDepotData = (depotId: string) => {
    void queryClient.invalidateQueries({ queryKey: depotKeys.detail(depotId) })
    void queryClient.invalidateQueries({ queryKey: depotKeys.all })
    void queryClient.invalidateQueries({ queryKey: activityKeys.root })
  }
  const refreshDepotMutation = (_response: unknown, variables: { depotId: string }) => refreshDepotData(variables.depotId)

  return {
    returnItems: useMutation({
      mutationFn: ({ depotId, data }: { depotId: string; data: ReturnRequest }) => returnItems(depotId, data),
      onSuccess: (_response, variables) => refreshDepotData(variables.depotId),
    }),
    getDepotCandidateDetail: useMutation({
      mutationFn: ({ depotId, candidateId }: { depotId: string; candidateId: string }) =>
        getDepotCandidateDetail(depotId, candidateId),
    }),
    getDepotCandidateFileDetail: useMutation({
      mutationFn: ({ depotId, candidateId, fileId }: { depotId: string; candidateId: string; fileId: string }) =>
        getDepotCandidateFileDetail(depotId, candidateId, fileId),
    }),
    renameDepotCandidate: useMutation({
      mutationFn: ({ depotId, candidateId, data }: { depotId: string; candidateId: string; data: RenameRequest }) =>
        renameDepotCandidate(depotId, candidateId, data),
      onSuccess: refreshDepotMutation,
    }),
    renameDepotCandidateFile: useMutation({
      mutationFn: ({
        depotId,
        candidateId,
        fileId,
        data,
      }: {
        depotId: string
        candidateId: string
        fileId: string
        data: RenameRequest
      }) => renameDepotCandidateFile(depotId, candidateId, fileId, data),
      onSuccess: refreshDepotMutation,
    }),
    deleteDepotCandidate: useMutation({
      mutationFn: ({ depotId, candidateId }: { depotId: string; candidateId: string }) =>
        deleteDepotCandidate(depotId, candidateId),
      onSuccess: refreshDepotMutation,
    }),
    deleteDepotCandidateFile: useMutation({
      mutationFn: ({ depotId, candidateId, fileId }: { depotId: string; candidateId: string; fileId: string }) =>
        deleteDepotCandidateFile(depotId, candidateId, fileId),
      onSuccess: refreshDepotMutation,
    }),
  }
}

function required(value: string | undefined, label: string) {
  if (!value) throw new Error(`Missing ${label}`)
  return value
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
