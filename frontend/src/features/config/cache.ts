import type { QueryClient } from '@tanstack/react-query'

export const configKeys = {
  origins: ['origins'] as const,
  depots: ['depots'] as const,
  watchSettings: ['watch-settings'] as const,
  watchStatus: ['watch-status'] as const,
  watchChildren: ['watch-children'] as const,
  watchRuntimeSettings: ['settings', 'watch-runtime'] as const,
  health: ['health'] as const,
}

export function invalidateConfigQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: configKeys.origins })
  void queryClient.invalidateQueries({ queryKey: configKeys.depots })
  void queryClient.invalidateQueries({ queryKey: configKeys.watchSettings })
  void queryClient.invalidateQueries({ queryKey: configKeys.watchStatus })
  void queryClient.invalidateQueries({ queryKey: configKeys.watchChildren })
  void queryClient.invalidateQueries({ queryKey: configKeys.health })
}
