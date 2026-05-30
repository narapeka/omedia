import { describe, expect, it } from 'vitest'
import type { ActivityEvent } from '@/api/types'
import { messages, type MessageKey } from '@/app/i18n/messages'
import { buildAutomationActivity } from '@/features/services/watch/activity'

describe('buildAutomationActivity', () => {
  it('localizes watch action titles and keeps full paths for end truncation', () => {
    const source = 'H:/DEMO/watch/movie-watch/Some Very Long Movie Folder Name/Some Very Long Movie File Name [43.25GB].iso'
    const target = 'H:/DEMO/stage/movie/Some Very Long Target Folder Name/Some Very Long Target File Name (2026).iso'

    const items = buildAutomationActivity(
      [
        activityEvent({
          summary: 'Moved to Depot',
          entity_source: source,
          entity_target: target,
        }),
      ],
      zhT,
    )

    expect(items[0]).toMatchObject({
      title: zhT('movedEntityToDepot', { entity: zhT('entityFile') }),
      detail: `${source} -> ${target}`,
    })
    expect(items[0].detail).not.toContain('...')
  })
})

const zhT = (key: MessageKey, values?: Record<string, number | string | null | undefined>) => {
  const template = messages['zh-CN'][key] ?? messages['en-US'][key]
  if (!values) return template
  return template.replace(/\{(\w+)\}/g, (match, valueKey: string) => {
    const value = values[valueKey]
    return value === null || value === undefined ? match : String(value)
  })
}

function activityEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: 'watch-moved',
    time: '2026-05-02T04:00:00Z',
    area: 'watch_organize',
    action: 'move_to_depot',
    status: 'succeeded',
    reason: null,
    summary: null,
    entity_type: 'file',
    trace_id: null,
    entity_source: null,
    entity_target: null,
    media_type: 'movie',
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
