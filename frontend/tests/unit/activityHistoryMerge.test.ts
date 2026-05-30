import { describe, expect, it } from 'vitest'
import type { ActivityEvent } from '@/api/types'
import { buildHistoryItems } from '@/features/activity/history/rows'

describe('buildHistoryItems', () => {
  it('builds newest-first rows from Activity events', () => {
    const items = buildHistoryItems({
      events: [organizeEvent(), transferEvent()],
    })

    expect(items.map((item) => item.id)).toEqual(['transfer-complete', 'activity-organized'])
    expect(items[0]).toMatchObject({
      status: 'succeeded',
      area: 'Manual transfer',
      event: 'Transfer completed',
      source: 'movie',
      target: 'D:/media/library/movies',
      result: 'Completed',
      summary: 'moved=2 skipped=0 failed=0 timed_out=0',
    })
    expect(items[1]).toMatchObject({
      status: 'succeeded',
      area: 'Manual organize',
      event: 'Moved file to Depot',
      summary: 'Movie moved',
      result: 'Completed',
    })
  })

  it('keeps details user-facing and excludes raw trace data', () => {
    const items = buildHistoryItems({
      events: [organizeEvent({ context: { moved: 1, trace_id: 'trace-1', headers: { authorization: 'secret' } } })],
    })

    expect(items[0].contextRows).toContainEqual({ label: 'TMDB ID', value: '19995' })
    expect(items[0].contextRows).toContainEqual({ label: 'Moved', value: '1' })
    expect(items[0].contextRows.some((row) => row.label === 'Trace')).toBe(false)
    expect(items[0].contextRows.some((row) => row.value.includes('secret'))).toBe(false)
  })

  it('keeps full source and target paths for table end truncation', () => {
    const source = 'H:/DEMO/watch/movie-watch/Some Very Long Movie Folder Name/Some Very Long Movie File Name [43.25GB].iso'
    const target = 'H:/DEMO/stage/movie/Some Very Long Target Folder Name/Some Very Long Target File Name (2026).iso'

    const items = buildHistoryItems({
      events: [organizeEvent({ entity_source: source, entity_target: target })],
    })

    expect(items[0].source).toBe(source)
    expect(items[0].target).toBe(target)
    expect(items[0].source).not.toContain('...')
    expect(items[0].target).not.toContain('...')
  })
})

function organizeEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return activityEvent({
    id: 'activity-organized',
    time: '2026-05-02T04:00:00Z',
    area: 'manual_organize',
    action: 'move_to_depot',
    status: 'succeeded',
    summary: 'Movie moved',
    entity_type: 'file',
    media_type: 'movie',
    tmdb_id: '19995',
    entity_source: 'D:/media/manual/Avatar.mkv',
    entity_target: 'D:/media/depot/Avatar/Avatar.mkv',
    depot_id: 'movies-depot',
    depot_name: 'movie',
    ...overrides,
  })
}

function transferEvent(): ActivityEvent {
  return activityEvent({
    id: 'transfer-complete',
    time: '2026-05-02T04:03:00Z',
    area: 'manual_transfer',
    action: 'transfer',
    status: 'succeeded',
    summary: 'moved=2 skipped=0 failed=0 timed_out=0',
    entity_type: 'transfer_job',
    entity_source: 'movie',
    entity_target: 'D:/media/library/movies',
    depot_id: 'movies-depot',
    depot_name: 'movie',
  })
}

function activityEvent(overrides: Partial<ActivityEvent>): ActivityEvent {
  return {
    id: 'event',
    time: '2026-05-02T04:00:00Z',
    area: 'manual_organize',
    action: 'move_to_depot',
    status: 'succeeded',
    reason: null,
    summary: null,
    entity_type: 'file',
    trace_id: null,
    entity_source: null,
    entity_target: null,
    media_type: null,
    tmdb_id: null,
    origin_id: null,
    origin_name: null,
    origin_path: null,
    depot_id: null,
    depot_name: null,
    depot_path: null,
    library_path: null,
    rule_id: null,
    rule_name: null,
    context: {},
    ...overrides,
  }
}
