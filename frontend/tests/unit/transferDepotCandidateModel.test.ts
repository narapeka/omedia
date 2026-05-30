import { describe, expect, it } from 'vitest'
import type { DepotCandidate } from '@/api/types'
import {
  isActionableDepotCandidate,
  isDisplayOnlyEmptyRootGroupCandidate,
} from '@/features/transfer/depot/model'

describe('Depot candidate presentation helpers', () => {
  it('treats empty root folders without a backend group as display-only empty groups', () => {
    const candidate = candidateFixture({
      id: 'empty-root',
      relative_path: 'Loose Prefix',
      display_name: 'Loose Prefix',
      file_count: 0,
      files: [],
      group: null,
      path_split_confidence: 'ungrouped_root_file',
    })

    expect(isDisplayOnlyEmptyRootGroupCandidate(candidate)).toBe(true)
    expect(isActionableDepotCandidate(candidate)).toBe(false)
  })

  it('keeps non-empty root folders actionable without making them display-only groups', () => {
    const candidate = candidateFixture({
      id: 'root-with-files',
      relative_path: 'Loose',
      display_name: 'Loose',
      file_count: 1,
      files: [{ id: 'file-1' } as NonNullable<DepotCandidate['files']>[number]],
      group: null,
      path_split_confidence: 'ungrouped_root_file',
    })

    expect(isDisplayOnlyEmptyRootGroupCandidate(candidate)).toBe(false)
    expect(isActionableDepotCandidate(candidate)).toBe(true)
  })

  it('does not hide grouped empty media candidates, blocked folders, or root media folders', () => {
    const grouped = candidateFixture({
      id: 'grouped-empty',
      relative_path: 'Movies/Avatar (2009) {tmdb-19995}',
      display_name: 'Avatar (2009) {tmdb-19995}',
      file_count: 0,
      files: [],
      group: { key: 'depot:movies', organize_prefix: 'Movies', display_name: 'Movies' },
      path_split_confidence: 'system_marker',
    })
    const blocked = candidateFixture({
      id: 'blocked-empty-root',
      relative_path: 'Blocked',
      display_name: 'Blocked',
      file_count: 0,
      files: [],
      group: null,
      blocked_reason: 'scan_error',
      path_split_confidence: 'ungrouped_root_file',
    })
    const rootMedia = candidateFixture({
      id: 'root-media-empty',
      relative_path: 'Avatar (2009) {tmdb-19995}',
      display_name: 'Avatar (2009) {tmdb-19995}',
      file_count: 0,
      files: [],
      group: null,
      path_split_confidence: 'system_marker',
    })

    expect(isDisplayOnlyEmptyRootGroupCandidate(grouped)).toBe(false)
    expect(isActionableDepotCandidate(grouped)).toBe(true)
    expect(isDisplayOnlyEmptyRootGroupCandidate(blocked)).toBe(false)
    expect(isActionableDepotCandidate(blocked)).toBe(true)
    expect(isDisplayOnlyEmptyRootGroupCandidate(rootMedia)).toBe(false)
    expect(isActionableDepotCandidate(rootMedia)).toBe(true)
  })
})

function candidateFixture(patch: Partial<DepotCandidate>): DepotCandidate {
  return {
    id: 'candidate',
    kind: 'folder',
    path: `D:/Depot/${patch.relative_path ?? 'Candidate'}`,
    relative_path: 'Candidate',
    display_name: 'Candidate',
    size_bytes: 0,
    modified_time: null,
    file_count: 0,
    media_count: 0,
    group: null,
    media_relative_path: null,
    path_split_confidence: null,
    files: [],
    tree: {},
    blocked_reason: null,
    ...patch,
  }
}
