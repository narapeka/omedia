import { useQuery } from '@tanstack/react-query'
import { settingsHealth as health } from '@/api/generated/settings/settings'
import { configKeys } from '@/features/config/cache'

export const healthKeys = {
  health: configKeys.health,
}

export function useHealth() {
  return useQuery({
    queryKey: healthKeys.health,
    queryFn: ({ signal }) => health({ signal }),
  })
}
