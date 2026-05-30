import type { ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DepotCandidate } from '@/api/types'
import { I18nProvider } from '@/app/providers/I18nProvider'
import { LocaleProvider } from '@/app/providers/LocaleProvider'
import { DepotCandidateList } from '@/features/transfer/depot/list'

describe('DepotCandidateList grouping', () => {
  it('renders root media candidates without an extra same-name group header', () => {
    const name = 'Avatar (2009) {tmdb-19995}'
    renderList([
      candidateFixture({
        id: 'root-media',
        relative_path: name,
        display_name: name,
        file_count: 1,
        media_count: 1,
        path_split_confidence: 'system_marker',
      }),
    ])

    expect(screen.getAllByText(name)).toHaveLength(2)
    expect(screen.getByRole('button', { name: `Details ${name}` })).toBeInTheDocument()
  })

  it('renders empty root folders as display-only empty groups', () => {
    renderList([
      candidateFixture({
        id: 'empty-prefix',
        relative_path: 'Loose Prefix',
        display_name: 'Loose Prefix',
        file_count: 0,
        media_count: 0,
        path_split_confidence: 'ungrouped_root_file',
      }),
    ])

    expect(screen.getByText('Loose Prefix')).toBeInTheDocument()
    expect(screen.getByText('Empty folder')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Details Loose Prefix' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send back Loose Prefix' })).not.toBeInTheDocument()
  })

  it('groups media candidates only when the backend provides a candidate group', () => {
    const name = 'Avatar (2009) {tmdb-19995}'
    renderList([
      candidateFixture({
        id: 'grouped-media',
        relative_path: `Movies/${name}`,
        display_name: name,
        file_count: 1,
        media_count: 1,
        group: { key: 'depot:movies', organize_prefix: 'Movies', display_name: 'Movies' },
        path_split_confidence: 'system_marker',
      }),
    ])

    expect(screen.getByText('Movies')).toBeInTheDocument()
    expect(screen.getByText(name)).toBeInTheDocument()
  })
})

function renderList(candidates: DepotCandidate[]) {
  localStorage.setItem('omedia.locale', 'en-US')
  const selectedIds = new Set(candidates.map((candidate) => candidate.id))
  renderWithProviders(
    <DepotCandidateList
      candidates={candidates}
      pendingCount={candidates.length}
      selectedIds={selectedIds}
      expandedIds={new Set()}
      fetching={false}
      selectionMode="decision"
      showHeader={false}
      onRefresh={vi.fn()}
      onToggleSelected={vi.fn()}
      onToggleExpanded={vi.fn()}
      onCandidateDetails={vi.fn()}
      onFileDetails={vi.fn()}
      onCandidateReturn={vi.fn()}
      onFileReturn={vi.fn()}
    />,
  )
}

function renderWithProviders(ui: ReactElement) {
  return render(
    <LocaleProvider>
      <I18nProvider>{ui}</I18nProvider>
    </LocaleProvider>,
  )
}

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
