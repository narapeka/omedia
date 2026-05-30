import { describe, expect, it } from 'vitest'
import { messages } from '@/app/i18n/messages'
import { errorMessage, notificationContent, notificationMessage } from '@/lib/notifications'

describe('notification messages', () => {
  it('translates duplicate rule errors from stable codes', () => {
    document.documentElement.lang = 'en-US'

    expect(
      errorMessage(
        { code: 'name.duplicate', details: { object: 'Organize rule', name: 'Movies' } },
        'Request failed',
      ),
    ).toBe('Organize rule name already exists: Movies')

    expect(
      errorMessage(
        { code: 'name.duplicate', details: { object: 'Transfer rule', name: 'Library' } },
        'Request failed',
      ),
    ).toBe('Transfer rule name already exists: Library')
  })

  it('translates partial bulk scan item errors from structured details', () => {
    document.documentElement.lang = 'en-US'

    expect(notificationMessage({ code: 'origin.disabled', details: { origin_id: 'manual-tv' } })).toBe(
      'Origin is disabled: manual-tv',
    )
  })

  it('explains managed path overlap errors with remediation', () => {
    document.documentElement.lang = 'en-US'
    const content = notificationContent(
      {
        code: 'path.overlap',
        details: {
          left_label: 'WatchSettings',
          left_path: 'H:\\DEMO\\watch',
          right_label: 'Origin origin_89853c8a35c4464eb401b8a7fb74280d',
          right_path: 'H:\\DEMO\\watch',
        },
      },
      messages['en-US'].requestFailed,
    )

    expect(content.title).toBe('Managed paths overlap: Watch root path and Origin path')
    expect(content.title).not.toContain('origin_')
    expect(content.description).toContain('same folder or one contains the other')
    expect(content.description).toContain('Watch root, Origins, Depots, and Library targets')
  })

  it('translates related path configuration errors', () => {
    document.documentElement.lang = 'en-US'

    expect(
      notificationMessage({
        code: 'path.overlap',
        details: {
          left_label: 'Ad hoc source',
          left_path: 'H:\\DEMO\\source',
          right_label: 'Depot depot_1 Library',
          right_path: 'H:\\DEMO\\lib',
        },
      }),
    ).toBe('Ad hoc source overlaps a managed path: Library path')

    expect(
      notificationMessage({
        code: 'path.watch_direct_child',
        details: { label: 'Origin origin_1' },
      }),
    ).toBe('Origin path must be a direct child of the Watch root.')
  })

  it('hides generated internal identifiers in user-facing messages', () => {
    document.documentElement.lang = 'en-US'
    const originId = 'origin_89853c8a35c4464eb401b8a7fb74280d'
    const candidateId = '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'

    expect(notificationMessage({ code: 'origin.unknown', details: { origin_id: originId } })).toBe(
      'Unknown Origin. It may have been removed; refresh and try again.',
    )
    expect(notificationMessage({ code: 'origin.manual_active_session', details: { origin_id: originId } })).toBe(
      'This manual Origin already has an active Organize session.',
    )
    expect(notificationMessage({ code: 'source_candidate.unknown', details: { source_candidate_id: candidateId } })).toBe(
      'Unknown Source candidate. It may have been removed; refresh and try again.',
    )
  })
})
