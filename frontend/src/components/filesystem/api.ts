import { useQuery } from '@tanstack/react-query'
import { listInventoryDirectories } from '@/api/generated/inventory/inventory'

export const filesystemKeys = {
  directoryListing: (path?: string | null) => ['inventory', 'directories', path ?? ''] as const,
}

export function useDirectoryListing(path?: string | null, enabled = true) {
  return useQuery({
    queryKey: filesystemKeys.directoryListing(path),
    queryFn: ({ signal }) => listInventoryDirectories(path ? { path } : undefined, { signal }),
    enabled,
  })
}
