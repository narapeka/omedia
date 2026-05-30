import { describe, expect, it } from 'vitest'
import { buildDepotGroups, buildDepotTree } from '@/features/transfer/depot/model'

describe('Depot transfer view models', () => {
  it('builds Depot groups with library targets, rule summaries, pending state, and busy jobs', () => {
    const groups = buildDepotGroups({
      depots: [
        {
          id: 'movies-depot',
          name: 'Movies Depot',
          path: 'D:/depot/movies',
          media_type: 'movie',
          enabled: true,
          pending_count: 2,
          policy: { target_library_path: 'D:/library/movies', trigger: 'manual', transfer_rule_id: 'movie-rule', schedule: null },
          last_failed_transfer: {
            id: 'job-failed',
            depot_id: 'movies-depot',
            status: 'failed',
            requested_by: 'test',
            created_at: '2026-05-02T04:00:00Z',
            message: 'Destination busy',
          },
        },
      ],
      jobs: [{ id: 'job-running', depot_id: 'movies-depot', status: 'running', requested_by: 'test', created_at: '2026-05-02T04:00:00Z' }],
      transferRules: [{ id: 'movie-rule', name: 'Movie library', fallback_bucket: 'M', categories: [{ name: '4K', bucket: '4K', conditions: [] }] }],
    })

    expect(groups[0]).toMatchObject({
      id: 'movies-depot',
      name: 'Movies Depot',
      mediaType: 'movie',
      depotPath: 'D:/depot/movies',
      libraryPath: 'D:/library/movies',
      transferRuleName: 'Movie library',
      transferRuleSummary: '1 category, fallback M',
      canTransferNow: false,
    })
    expect(groups[0].busyJob?.id).toBe('job-running')
    expect(groups[0].lastFailure?.message).toBe('Destination busy')
  })

  it('builds a Depot tree summary from Depot detail candidates and files', () => {
    const tree = buildDepotTree({
      id: 'movies-depot',
      name: 'Movies Depot',
      path: 'D:/depot/movies',
      media_type: 'movie',
      enabled: true,
      pending_count: 2,
      policy: { target_library_path: 'D:/library/movies', trigger: 'manual', transfer_rule_id: null, schedule: null },
      candidates: [
        {
          id: 'candidate-1',
          kind: 'folder',
          path: 'D:/depot/movies/Avatar',
          relative_path: 'Avatar',
          display_name: 'Avatar',
          size_bytes: 300,
          file_count: 2,
          media_count: 1,
          files: [],
          blocked_reason: null,
        },
        {
          id: 'candidate-2',
          kind: 'file',
          path: 'D:/depot/movies/Blocked.mkv',
          relative_path: 'Blocked.mkv',
          display_name: 'Blocked.mkv',
          size_bytes: 100,
          file_count: 1,
          media_count: 1,
          files: [],
          blocked_reason: 'busy',
        },
      ],
    })

    expect(tree).toMatchObject({
      depotId: 'movies-depot',
      candidateCount: 2,
      fileCount: 3,
      blockedCount: 1,
      pendingCount: 2,
      totalSizeBytes: 400,
    })
  })
})
