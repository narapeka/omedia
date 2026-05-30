import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelTransferJobRun as cancelTransferJob,
  createTransferJob as transferDepot,
  listTransferJobHistory as listTransferJobs,
} from '@/api/generated/transfer/transfer'
import type { ListTransferJobHistoryParams, TransferRequest } from '@/api/types'
import { activityKeys } from '@/features/activity/api'
import { depotKeys } from '@/features/depot/api'

export const transferKeys = {
  root: ['transfer-jobs'] as const,
  jobs: (params?: ListTransferJobHistoryParams) => ['transfer-jobs', params ?? {}] as const,
}

export function useTransferJobs(params?: ListTransferJobHistoryParams, { poll = true }: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: transferKeys.jobs(params),
    queryFn: ({ signal }) => listTransferJobs(params, { signal }),
    refetchInterval: poll ? 2_000 : false,
  })
}

export function useTransferActions() {
  const queryClient = useQueryClient()
  const refreshTransfers = () => {
    void queryClient.invalidateQueries({ queryKey: transferKeys.root })
    void queryClient.invalidateQueries({ queryKey: depotKeys.all })
    void queryClient.invalidateQueries({ queryKey: activityKeys.root })
  }

  return {
    transferDepot: useMutation({
      mutationFn: ({ depotId, data }: { depotId: string; data: Omit<TransferRequest, 'depot_id'> }) =>
        transferDepot({ ...data, depot_id: depotId }),
      onSuccess: (_job, variables) => {
        refreshTransfers()
        void queryClient.invalidateQueries({ queryKey: depotKeys.detail(variables.depotId) })
      },
    }),
    cancelTransferJob: useMutation({
      mutationFn: (jobId: string) => cancelTransferJob(jobId),
      onSuccess: refreshTransfers,
    }),
  }
}
