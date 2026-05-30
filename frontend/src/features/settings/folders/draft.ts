import type { DepotSummary, OriginSummary, ResolveMode } from '@/api/types'
import { depotResolveMode } from '@/features/depot/model'

export type MediaType = 'movie' | 'tv'

export type OriginDraft = {
  mode: 'create' | 'edit'
  originalId?: string
  name: string
  path: string
  media_type: MediaType | ''
  trigger: 'manual' | 'watch'
  enabled: boolean
  target_depot_id: string
  organize_rule_id: string
}

export type DepotDraft = {
  mode: 'create' | 'edit'
  originalId?: string
  name: string
  path: string
  media_type: MediaType | ''
  resolveMode: ResolveMode
  enabled: boolean
  target_library_path: string
  trigger: 'manual' | 'scheduled'
  transfer_rule_id: string
  schedule: string
}

export function emptyOriginDraft(): OriginDraft {
  return {
    mode: 'create',
    name: '',
    path: '',
    media_type: '',
    trigger: 'manual',
    enabled: true,
    target_depot_id: '',
    organize_rule_id: '',
  }
}

export function emptyOriginDraftForDepot(depot: DepotSummary): OriginDraft {
  return {
    ...emptyOriginDraft(),
    media_type: depot.media_type,
    target_depot_id: depot.id,
  }
}

export function originToDraftForDepot(origin: OriginSummary, depot: DepotSummary): OriginDraft {
  return {
    mode: 'edit',
    originalId: origin.id,
    name: origin.name,
    path: origin.path,
    media_type: depot.media_type,
    trigger: 'manual',
    enabled: origin.enabled ?? true,
    target_depot_id: depot.id,
    organize_rule_id: origin.policy.organize_rule_id ?? '',
  }
}

export function emptyDepotDraft(): DepotDraft {
  return {
    mode: 'create',
    name: '',
    path: '',
    media_type: '',
    resolveMode: 'full',
    enabled: true,
    target_library_path: '',
    trigger: 'manual',
    transfer_rule_id: '',
    schedule: '',
  }
}

export function depotToDraft(depot: DepotSummary): DepotDraft {
  return {
    mode: 'edit',
    originalId: depot.id,
    name: depot.name,
    path: depot.path,
    media_type: depot.media_type,
    resolveMode: depotResolveMode(depot),
    enabled: depot.enabled ?? true,
    target_library_path: depot.policy.target_library_path,
    trigger: depot.policy.trigger === 'scheduled' ? 'scheduled' : 'manual',
    transfer_rule_id: depot.policy.transfer_rule_id ?? '',
    schedule: depot.policy.schedule ?? '',
  }
}
