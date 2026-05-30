import { describe, expect, it } from 'vitest'
import type { DepotSummary, OrganizeSession, OriginSummary, TransferJob } from '@/api/types'
import {
  depotToDraft,
  emptyDepotDraft,
  emptyOriginDraft,
  emptyOriginDraftForDepot,
  originToDraftForDepot,
} from '@/features/settings/folders/draft'
import {
  assessDepotRemoval,
  assessOriginRemoval,
  sortDepotsForCards,
  validateDepotDraft,
  validateOriginDraft,
} from '@/features/settings/folders/validate'

const t = ((key: string, values?: Record<string, number | string | null | undefined>) =>
  values?.count === undefined ? key : `${key}:${values.count}`) as never

describe('settings folder draft and validation models', () => {
  it('maps Origin and Depot API data into frontend drafts', () => {
    const tvDepot = depot({
      id: 'tv-depot',
      media_type: 'tv',
      resolve_mode: 'incremental',
      policy: {
        target_library_path: 'D:/library/tv',
        trigger: 'scheduled',
        transfer_rule_id: 'tv-rule',
        schedule: '0 2 * * *',
      },
    })
    const movieDepot = depot({ id: 'movie-depot', media_type: 'movie', resolve_mode: 'incremental' })
    const configuredOrigin = origin({ id: 'origin-1', target: tvDepot.id, media_type: 'movie', organizeRuleId: 'movie-rule' })

    expect(emptyDepotDraft()).toMatchObject({ mode: 'create', resolveMode: 'full', trigger: 'manual' })
    expect(depotToDraft(tvDepot)).toMatchObject({
      mode: 'edit',
      originalId: 'tv-depot',
      resolveMode: 'incremental',
      trigger: 'scheduled',
      schedule: '0 2 * * *',
    })
    expect(depotToDraft(movieDepot).resolveMode).toBe('full')
    expect(emptyOriginDraftForDepot(tvDepot)).toMatchObject({ media_type: 'tv', target_depot_id: 'tv-depot' })
    expect(originToDraftForDepot(configuredOrigin, tvDepot)).toMatchObject({
      mode: 'edit',
      originalId: 'origin-1',
      media_type: 'tv',
      target_depot_id: 'tv-depot',
      organize_rule_id: 'movie-rule',
    })
  })

  it('validates required folder fields and removal blockers', () => {
    expect(validateOriginDraft(emptyOriginDraft(), t)).toBe('originNameRequired')
    expect(validateDepotDraft(emptyDepotDraft(), t)).toBe('depotNameRequired')

    const linkedOrigin = origin({ id: 'origin-1', target: 'movie-depot' })
    const removableOrigin = assessOriginRemoval(linkedOrigin, [], t)
    const activeOrigin = assessOriginRemoval(linkedOrigin, [session({ kind: 'origin', path: linkedOrigin.path })], t)
    expect(removableOrigin).toEqual({ canRemove: true, message: 'removeOriginSafeNotice' })
    expect(activeOrigin).toEqual({ canRemove: false, message: 'removeOriginBlockedActiveSession' })

    const blockedDepot = assessDepotRemoval(
      depot({ id: 'movie-depot' }),
      [linkedOrigin],
      [session({ depotId: 'movie-depot' })],
      [transferJob({ depotId: 'movie-depot', status: 'running' })],
      t,
    )
    expect(blockedDepot.canRemove).toBe(false)
    expect(blockedDepot.message).toContain('removeDepotBlockedOrigins:1')
    expect(blockedDepot.message).toContain('removeDepotBlockedActiveSession')
    expect(blockedDepot.message).toContain('removeDepotBlockedActiveTransfer')
  })

  it('sorts Depot cards by media type, name, then id', () => {
    expect(
      sortDepotsForCards([
        depot({ id: 'tv-b', name: 'Beta', media_type: 'tv' }),
        depot({ id: 'movie-b', name: 'Beta', media_type: 'movie' }),
        depot({ id: 'movie-a', name: 'Alpha', media_type: 'movie' }),
      ]).map((item) => item.id),
    ).toEqual(['movie-a', 'movie-b', 'tv-b'])
  })
})

function depot(overrides: Partial<DepotSummary> = {}): DepotSummary {
  return {
    id: 'movie-depot',
    name: 'Movies',
    path: 'D:/depot/movies',
    media_type: 'movie',
    enabled: true,
    pending_count: 0,
    resolve_mode: 'full',
    policy: {
      target_library_path: 'D:/library/movies',
      trigger: 'manual',
      transfer_rule_id: null,
      schedule: null,
    },
    ...overrides,
  }
}

function origin({
  organizeRuleId,
  target,
  ...overrides
}: Partial<OriginSummary> & { target: string; organizeRuleId?: string }): OriginSummary {
  return {
    id: 'origin',
    name: 'Origin',
    path: 'D:/origin',
    media_type: 'movie',
    trigger: 'manual',
    enabled: true,
    candidate_count: 0,
    file_count: 0,
    unknown_count: 0,
    policy: { target_depot_id: target, organize_rule_id: organizeRuleId ?? null },
    ...overrides,
  }
}

function session({
  kind = 'ad_hoc',
  path = 'D:/other',
  depotId = 'other-depot',
}: {
  kind?: OrganizeSession['kind']
  path?: string
  depotId?: string
} = {}): OrganizeSession {
  return {
    id: 'session',
    kind,
    path,
    policy: { target_depot_id: depotId },
  } as OrganizeSession
}

function transferJob({ depotId, status }: { depotId: string; status: TransferJob['status'] }): TransferJob {
  return {
    id: 'job',
    depot_id: depotId,
    status,
  } as TransferJob
}
