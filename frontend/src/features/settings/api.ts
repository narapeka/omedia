import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { healthKeys } from '@/app/health/api'
import { backupAdmin, clearAdminTmdbCache as adminClearTmdb, pruneAdminActivity as adminPruneActivity, pruneAdminTransfer as adminPruneTransfer, restoreAdmin } from '@/api/generated/admin/admin'
import {
  organizeSettings as getOrganizeSettings,
  providerSettings as providerStatus,
  saveOrganizeSettings,
  saveProviderSettings,
} from '@/api/generated/settings/settings'
import type { AdminPruneRequest, OrganizeSettings, ProviderSettingsUpdate } from '@/api/types'
import { activityKeys } from '@/features/activity/api'
import { depotKeys } from '@/features/depot/api'
import { organizeKeys } from '@/features/organize/api'
import { originKeys } from '@/features/origin/api'
import { rulesKeys } from '@/features/rules/api'
import { servicesKeys } from '@/features/services/api'
import { transferKeys } from '@/features/transfer/api'

export const settingsKeys = {
  providerStatus: ['settings', 'providers'] as const,
  organizeSettings: ['settings', 'organize'] as const,
}

export function useProviderStatus() {
  return useQuery({
    queryKey: settingsKeys.providerStatus,
    queryFn: ({ signal }) => providerStatus({ signal }),
  })
}

export function useOrganizeSettings() {
  return useQuery({
    queryKey: settingsKeys.organizeSettings,
    queryFn: ({ signal }) => getOrganizeSettings({ signal }),
  })
}

export function useSettingsActions() {
  const queryClient = useQueryClient()
  return {
    saveOrganizeSettings: useMutation({
      mutationFn: (data: OrganizeSettings) => saveOrganizeSettings(data),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: settingsKeys.organizeSettings })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchStatus })
        void queryClient.invalidateQueries({ queryKey: healthKeys.health })
        void queryClient.invalidateQueries({ queryKey: organizeKeys.sessions })
      },
    }),
    saveProviderSettings: useMutation({
      mutationFn: (data: ProviderSettingsUpdate) => saveProviderSettings(data),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: settingsKeys.providerStatus })
        void queryClient.invalidateQueries({ queryKey: healthKeys.health })
      },
    }),
  }
}

export function useMaintenanceActions() {
  const queryClient = useQueryClient()
  return {
    clearTmdbCache: useMutation({
      mutationFn: () => adminClearTmdb(),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: healthKeys.health }),
    }),
    pruneOperationHistory: useMutation({
      mutationFn: async (data?: AdminPruneRequest) => {
        const [activity, transfer] = await Promise.all([
          adminPruneActivity(data ?? null),
          adminPruneTransfer(data ?? null),
        ])
        return { activity, transfer }
      },
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: activityKeys.root })
        void queryClient.invalidateQueries({ queryKey: transferKeys.root })
      },
    }),
    backupConfig: useMutation({
      mutationFn: async () => String(await backupAdmin()),
    }),
    restoreConfig: useMutation({
      mutationFn: (content: string) => restoreAdmin({ content }),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: originKeys.all })
        void queryClient.invalidateQueries({ queryKey: depotKeys.all })
        void queryClient.invalidateQueries({ queryKey: rulesKeys.organize })
        void queryClient.invalidateQueries({ queryKey: rulesKeys.transfer })
        void queryClient.invalidateQueries({ queryKey: transferKeys.root })
        void queryClient.invalidateQueries({ queryKey: activityKeys.root })
        void queryClient.invalidateQueries({ queryKey: settingsKeys.providerStatus })
        void queryClient.invalidateQueries({ queryKey: settingsKeys.organizeSettings })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchSettings })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchRuntimeSettings })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchStatus })
        void queryClient.invalidateQueries({ queryKey: servicesKeys.watchChildren })
        void queryClient.invalidateQueries({ queryKey: healthKeys.health })
      },
    }),
  }
}
