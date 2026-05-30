import { describe, expect, it } from 'vitest'
import type { DepotSummary, OriginSummary } from '@/api/types'
import { buildDepotConfigurationModel, isWatchDirectChild } from '@/features/depot/model'

describe('buildDepotConfigurationModel', () => {
  it('composes Depots, linked Origins, broken Origins, disabled state, media mismatch, and Watch child status', () => {
    const model = buildDepotConfigurationModel({
      depots: [
        depot({ id: 'movies-depot', name: 'Movies Depot', path: 'D:/depot/movies', media_type: 'movie' }),
        depot({ id: 'tv-depot', name: 'TV Depot', path: 'D:/depot/tv', media_type: 'tv', enabled: false }),
        depot({ id: 'empty-depot', name: 'Empty Depot', path: 'D:/depot/empty', media_type: 'movie' }),
      ],
      origins: [
        origin({ id: 'manual-movies', name: 'Manual Movies', path: 'D:/manual/movies', media_type: 'movie', trigger: 'manual', target: 'movies-depot' }),
        origin({ id: 'watch-movies', name: 'Watch Movies', path: 'D:/incoming/watch-movies', media_type: 'movie', trigger: 'watch', target: 'movies-depot' }),
        origin({ id: 'mismatch-tv', name: 'Mismatch TV', path: 'D:/manual/tv', media_type: 'tv', trigger: 'manual', target: 'movies-depot' }),
        origin({ id: 'broken', name: 'Broken', path: 'D:/manual/broken', media_type: 'movie', trigger: 'manual', target: 'missing-depot' }),
      ],
      organizeRules: [{ id: 'movie-rule', name: 'Movie rule', categories: [], fallback_bucket: 'M' }],
      transferRules: [{ id: 'library-rule', name: 'Library rule', categories: [], fallback_bucket: 'L' }],
      watchSettings: { id: 'root', path: 'D:/incoming', enabled: true },
      watchChildren: [{ name: 'watch-movies', path: 'D:/incoming/watch-movies', status: 'configured', origin_id: 'watch-movies' }],
    })

    expect(model.counts.configured).toBe(3)
    expect(model.counts.disabled).toBe(1)
    expect(model.counts.unlinkedDepots).toBe(2)
    expect(model.counts.brokenOrigins).toBe(1)
    expect(model.brokenOrigins[0]).toMatchObject({ id: 'broken', targetDepotId: 'missing-depot' })
    expect(model.depots.find((depot) => depot.id === 'movies-depot')).toMatchObject({
      manualOrigins: expect.arrayContaining([expect.objectContaining({ id: 'manual-movies' })]),
      watchOrigins: expect.arrayContaining([expect.objectContaining({ id: 'watch-movies', watchDirectChild: true })]),
      health: 'broken',
    })
  })

  it('validates direct-child Watch paths', () => {
    expect(isWatchDirectChild('D:/incoming', 'D:/incoming/movies')).toBe(true)
    expect(isWatchDirectChild('D:/incoming', 'D:/incoming/movies/nested')).toBe(false)
    expect(isWatchDirectChild('D:/incoming', 'D:/other/movies')).toBe(false)
  })
})

function depot(overrides: Partial<DepotSummary>): DepotSummary {
  return {
    id: 'depot',
    name: 'Depot',
    path: 'D:/depot',
    media_type: 'movie',
    enabled: true,
    pending_count: 0,
    policy: { target_library_path: 'D:/library', trigger: 'manual', transfer_rule_id: 'library-rule', schedule: null },
    ...overrides,
  }
}

function origin({
  target,
  ...overrides
}: Partial<OriginSummary> & { target: string }): OriginSummary {
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
    policy: { target_depot_id: target, organize_rule_id: 'movie-rule' },
    ...overrides,
  }
}
