import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  saveWatchRuntimeSettings,
  watchRuntimeSettings as getWatchRuntimeSettings,
} from '@/api/generated/settings/settings'
import {
  listWatchSettingsChildren as listWatchChildren,
  restartWatchRuntime as restartWatch,
  saveWatchSettings,
  startWatchRuntime as startWatch,
  stopWatchRuntime as stopWatch,
  watchRuntimeStatus as getWatchStatus,
  watchSettings as getWatchSettings,
} from '@/api/generated/watch/watch'
import type { WatchRuntimeSettings, WatchSettings } from '@/api/types'
import { configKeys, invalidateConfigQueries } from '@/features/config/cache'

export const servicesKeys = {
  watchSettings: configKeys.watchSettings,
  watchStatus: configKeys.watchStatus,
  watchChildren: configKeys.watchChildren,
  watchRuntimeSettings: configKeys.watchRuntimeSettings,
}

export function useWatchSettings() {
  return useQuery({
    queryKey: servicesKeys.watchSettings,
    queryFn: ({ signal }) => getWatchSettings({ signal }),
  })
}

export function useWatchChildren() {
  return useQuery({
    queryKey: servicesKeys.watchChildren,
    queryFn: ({ signal }) => listWatchChildren({ signal }),
  })
}

export function useWatchStatus() {
  return useQuery({
    queryKey: servicesKeys.watchStatus,
    queryFn: ({ signal }) => getWatchStatus({ signal }),
    refetchInterval: 3_000,
  })
}

export function useWatchRuntimeSettings() {
  return useQuery({
    queryKey: servicesKeys.watchRuntimeSettings,
    queryFn: ({ signal }) => getWatchRuntimeSettings({ signal }),
  })
}

export function useWatchActions() {
  const queryClient = useQueryClient()
  const invalidateWatchConfig = () => invalidateConfigQueries(queryClient)

  return {
    saveWatchSettings: useMutation({
      mutationFn: (payload: WatchSettings) => saveWatchSettings(payload),
      onSuccess: invalidateWatchConfig,
    }),
    startWatch: useMutation({
      mutationFn: () => startWatch(),
      onSuccess: invalidateWatchConfig,
    }),
    stopWatch: useMutation({
      mutationFn: () => stopWatch(),
      onSuccess: invalidateWatchConfig,
    }),
    restartWatch: useMutation({
      mutationFn: () => restartWatch(),
      onSuccess: invalidateWatchConfig,
    }),
    saveWatchRuntimeSettings: useMutation({
      mutationFn: (data: WatchRuntimeSettings) => saveWatchRuntimeSettings(data),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchRuntimeSettings })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchStatus })
        void queryClient.invalidateQueries({ queryKey: configKeys.health })
      },
    }),
  }
}
