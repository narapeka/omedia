import { describe, expect, it } from 'vitest'
import { activityFiltersFromSearch, buildActivityParams, cleanActivitySearch, emptyActivityFilters, normalizeActivitySearch } from '@/features/activity/filters/model'

describe('buildActivityParams', () => {
  it('maps event filters to Activity API query parameters and omits blank values', () => {
    expect(
      buildActivityParams({
        ...emptyActivityFilters,
        group: 'transfer',
        focus: 'failed',
        area: 'manual_transfer',
        action: 'transfer',
        status: 'failed',
        reason: 'depot_locked',
        originId: 'origin-1',
        depotId: 'depot-1',
        libraryPath: 'D:/library',
        mediaType: 'movie',
        tmdbId: '19995',
      }),
    ).toEqual({
      area: ['manual_transfer'],
      group: 'transfer',
      focus: 'failed',
      action: 'transfer',
      status: 'failed',
      reason: 'depot_locked',
      origin_id: 'origin-1',
      depot_id: 'depot-1',
      library_path: 'D:/library',
      media_type: 'movie',
      tmdb_id: '19995',
      q: undefined,
      from_at: undefined,
      to_at: undefined,
      limit: 250,
    })
  })

  it('drops invalid enum-like filters while keeping free-text TMDB IDs', () => {
    expect(
      buildActivityParams({
        ...emptyActivityFilters,
        action: 'move',
        status: 'timeout',
        mediaType: 'anime',
        tmdbId: 'tmdb-19995',
      }),
    ).toEqual({
      area: undefined,
      group: undefined,
      focus: undefined,
      action: undefined,
      status: undefined,
      reason: undefined,
      origin_id: undefined,
      depot_id: undefined,
      library_path: undefined,
      media_type: undefined,
      tmdb_id: 'tmdb-19995',
      q: undefined,
      from_at: undefined,
      to_at: undefined,
      limit: 250,
    })
  })

  it('maps quick presets to event filters', () => {
    expect(buildActivityParams({ ...emptyActivityFilters, group: 'organize' })).toMatchObject({
      area: undefined,
      group: 'organize',
    })
    expect(buildActivityParams({ ...emptyActivityFilters, group: 'transfer' })).toMatchObject({
      area: undefined,
      group: 'transfer',
    })
    expect(buildActivityParams({ ...emptyActivityFilters, focus: 'unmatched' })).toMatchObject({
      focus: 'unmatched',
      reason: undefined,
    })
  })

  it('normalizes and cleans URL search filters', () => {
    const normalized = normalizeActivitySearch({
      group: 'organize',
      result: 'unmatched',
      status: 'failed',
      depotId: 'movies',
      ignored: 'value',
      tmdbId: 42,
    })

    expect(normalized).toEqual({
      group: 'organize',
      focus: 'unmatched',
      status: 'failed',
      depotId: 'movies',
    })
    expect(activityFiltersFromSearch(normalized)).toEqual({
      ...emptyActivityFilters,
      group: 'organize',
      focus: 'unmatched',
      status: 'failed',
      depotId: 'movies',
    })
    expect(cleanActivitySearch(normalized)).toEqual({
      group: 'organize',
      focus: 'unmatched',
      status: 'failed',
      depotId: 'movies',
    })
  })
})
