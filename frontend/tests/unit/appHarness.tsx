import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, vi } from 'vitest'
import { App } from '@/app/App'
import { I18nProvider } from '@/app/providers/I18nProvider'
import { LocaleProvider } from '@/app/providers/LocaleProvider'

export function resetAppTest() {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/organize')
  localStorage.clear()
  localStorage.setItem('omedia.locale', 'en-US')
  vi.restoreAllMocks()
}

export function renderApp(initialPath = '/organize') {
  window.history.pushState({}, '', initialPath)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <LocaleProvider>
      <I18nProvider>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </I18nProvider>
    </LocaleProvider>,
  )
}

export function mockMatchMedia(matchesByQuery: Record<string, boolean>) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: Boolean(matchesByQuery[query]),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  )
}

export async function chooseSelectOption(label: string, option: string | RegExp) {
  fireEvent.pointerDown(screen.getByLabelText(label), { button: 0, ctrlKey: false, pointerType: 'mouse' })
  fireEvent.click(await screen.findByRole('option', { name: option }))
}

export async function chooseTab(name: string) {
  const tab = await screen.findByRole('tab', { name })
  fireEvent.pointerDown(tab, { button: 0, ctrlKey: false, pointerType: 'mouse' })
  fireEvent.mouseDown(tab, { button: 0, ctrlKey: false })
  fireEvent.click(tab)
}

export async function chooseComboboxOption(label: string, option: string) {
  const input = screen.getByRole('combobox', { name: label })
  await waitFor(() => expect(input).not.toBeDisabled())
  const chips = input.closest('[data-slot="combobox-chips"]') as HTMLElement | null
  if (chips) fireEvent.pointerDown(chips, { button: 0, ctrlKey: false, pointerType: 'mouse' })
  fireEvent.focus(input)
  fireEvent.input(input, { target: { value: option }, inputType: 'insertText', data: option })
  fireEvent.change(input, { target: { value: option } })
  fireEvent.pointerDown(input, { button: 0, ctrlKey: false, pointerType: 'mouse' })
  fireEvent.click(input)
  fireEvent.keyDown(input, { key: 'ArrowDown', code: 'ArrowDown', altKey: true })
  fireEvent.keyDown(input, { key: ' ', code: 'Space' })
  fireEvent.keyDown(input, { key: 'ArrowDown', code: 'ArrowDown' })
  const listOption = await screen.findByRole('option', { name: new RegExp(option) })
  fireEvent.click(listOption)
}

const uiWait = { timeout: 3000 }

export async function expandSession(name = 'manual-movies') {
  await screen.findByText(name, {}, uiWait)
  if (screen.queryByRole('button', { name: `Collapse ${name}` })) return
  fireEvent.click(await screen.findByRole('button', { name: `Expand ${name}` }, uiWait))
  await screen.findByRole('button', { name: `Collapse ${name}` }, uiWait)
}

export async function expandSourceCandidate(name = 'Avatar') {
  await expandSession()
  fireEvent.click(await screen.findByRole('button', { name: `Expand ${name}` }))
}

export function mockApi(
  options: {
    transferJobStatus?: string
    organizeMediaType?: 'movie' | 'tv'
    organizeCandidateCount?: number
    organizeDecision?: 'accept' | 'ignore' | null
    organizeSessionCount?: number
    tmdbTotalPages?: number
    organizeState?: 'scanning' | 'scanned' | 'identifying' | 'identified'
    bulkOrganizeFailure?: boolean
    organizeLlmTitleHints?: boolean
    activityEntries?: unknown[]
    includeScheduledDepot?: boolean
    scheduledTransferJobStatus?: string
    watchStatusState?: string
  } = {},
) {
  let organizeOverridden = false
  let organizeDecision: 'accept' | 'ignore' | null = options.organizeDecision ?? null
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = new URL(url.toString(), 'http://localhost').pathname
    if (init?.method === 'POST' || init?.method === 'PUT' || init?.method === 'DELETE') {
      if (path.endsWith('/search')) {
        const body = JSON.parse(String(init.body ?? '{}'))
        return jsonResponse(tmdbSearchResponse(body.page ?? 1, options.tmdbTotalPages ?? 1, options.organizeMediaType ?? 'movie'))
      }
      if (path.startsWith('/api/identify/sessions/') && !path.endsWith('/search') && !path.includes('/override')) {
        return jsonResponse(
          organizeSession({
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            state: 'identified',
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        )
      }
      if (path.endsWith('/scan')) {
        return jsonResponse(
          organizeSession({
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            state: 'scanned',
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        )
      }
      if (path.includes('/override')) {
        organizeOverridden = true
        return jsonResponse(
          organizeSession({
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            overridden: true,
            state: 'identified',
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        )
      }
      if (path === '/api/admin/cache/tmdb/clear') return jsonResponse({ ok: true, deleted_entries: 2 })
      if (path === '/api/admin/activity/prune') return jsonResponse({ ok: true, older_than_days: 180, cutoff: '2026-01-01T00:00:00Z', deleted_events: 3 })
      if (path === '/api/admin/transfer/prune') {
        return jsonResponse({ ok: true, older_than_days: 180, cutoff: '2026-01-01T00:00:00Z', deleted_jobs: 4 })
      }
      if (path === '/api/admin/restore') {
        return jsonResponse({
          ok: true,
          restored: { watch_settings: 1, origins: 1, depots: 1, organize_rules: 1, transfer_rules: 1 },
          cleared: { activity_events: 3, transfer_jobs: 4, tmdb_detail_cache: 2 },
        })
      }
      if (path === '/api/organize/sessions/bulk') {
        const body = JSON.parse(String(init.body ?? '{}'))
        const originIds = Array.isArray(body.origin_ids) ? body.origin_ids : []
        return jsonResponse({
          sessions: originIds.slice(0, 1).map((originId: string, index: number) =>
            organizeSession({
              sessionId: `session-bulk-${index + 1}`,
              sourcePath: `D:/media/manual/${originId}`,
              mediaType: options.organizeMediaType,
              candidateCount: options.organizeCandidateCount,
              state: options.organizeState ?? 'scanned',
              llmTitleHints: options.organizeLlmTitleHints,
            }),
          ),
          results: originIds.map((originId: string, index: number) =>
            options.bulkOrganizeFailure && index === 1
              ? {
                  origin_id: originId,
                  status: 'disabled',
                  session_id: null,
                  message: `Origin is disabled: ${originId}`,
                  code: 'origin.disabled',
                  details: { origin_id: originId },
                }
              : { origin_id: originId, status: 'created', session_id: `session-bulk-${index + 1}`, message: null },
          ),
        })
      }
      if (path.includes('/organize/sessions/') && path.endsWith('/execute')) {
        return jsonResponse({
          session_id: 'session-1',
          moved: 1,
          skipped: 0,
          failed: 1,
          results: [
            {
              plan_item_id: 'plan-item-1',
              source_candidate_id: 'source-candidate-1',
              status: 'failed',
              source_path: 'D:/media/manual/movies/Avatar.mkv',
              destination_path: null,
              message: 'Disk full',
            },
          ],
        })
      }
      if (path.startsWith('/api/transfer/jobs/') && path.endsWith('/cancel')) return jsonResponse(transferJob('job-running', 'cancelled'))
      if (path === '/api/watch/start') return jsonResponse(watchStatus('running'))
      if (path === '/api/watch/stop') return jsonResponse(watchStatus('stopped'))
      if (path === '/api/watch/restart') return jsonResponse(watchStatus('running'))
      if ((path.includes('/plan-items/') || path.includes('/candidates/')) && path.endsWith('/decision')) {
        organizeDecision = JSON.parse(String(init.body ?? '{}')).decision ?? organizeDecision
        return new Response(null, { status: 204 })
      }
      if (path.includes('/decision')) {
        organizeDecision = JSON.parse(String(init.body ?? '{}')).decision ?? organizeDecision
        return jsonResponse(
          organizeSession({
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            state: 'identified',
            decision: organizeDecision,
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        )
      }
      if (path.includes('/api/depots/') && path.endsWith('/return')) return jsonResponse({ activity_events: ['activity-1'] })
      if (path.includes('/api/depots/') && path.includes('/candidates/')) return jsonResponse(depotMutationResponse())
      if (path.includes('/candidates/')) {
        return jsonResponse(
          organizeSession({
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            state: options.organizeState ?? 'identified',
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        )
      }
      if (path.includes('/transfer')) return jsonResponse(transferJob('job-retry', 'queued'))
      return jsonResponse({ ok: true })
    }
    if (path.includes('/api/depots/') && path.includes('/files/') && path.endsWith('/detail')) return jsonResponse(depotCandidateFileDetail())
    if (path.includes('/api/depots/') && path.endsWith('/detail')) return jsonResponse(depotCandidateDetail())
    if (path.endsWith('/detail')) return jsonResponse(sourceFileDetail())
    if (path === '/api/settings/health') {
      const configuredDepots = depots({ includeScheduled: options.includeScheduledDepot })
      return jsonResponse({
        ok: true,
        database: true,
        config_loaded: true,
        origins: 3,
        depots: configuredDepots.length,
        organize_rules: 0,
        transfer_rules: 0,
        watched_folders: 1,
        scheduled_transfers: configuredDepots.filter((Depot) => Depot.policy.trigger === 'scheduled').length,
      })
    }
    if (path === '/api/settings/providers') {
      return jsonResponse({
        tmdb_configured: true,
        tmdb_api_key: 'tmdb-secret',
        tmdb_base_url: 'https://tmdb.example/3',
        tmdb_rate_limit: 2.5,
        tmdb_proxy: null,
        llm_configured: true,
        llm_api_key: 'llm-secret',
        llm_base_url: 'https://llm.example/v1/',
        llm_model: 'gpt-test',
        llm_batch_size: 3,
        llm_rate_limit: 0.25,
        llm_proxy: null,
      })
    }
    if (path === '/api/settings/organize') return jsonResponse({ extensions: { video: ['.mkv'], subtitle: ['.srt'], sidecar: ['.nfo'] }, min_non_subtitle_file_size_mb: 50 })
    if (path === '/api/admin/backup') {
      return new Response('format: omedia-config-backup\nversion: 1\n', {
        status: 200,
        headers: { 'Content-Type': 'application/x-yaml' },
      })
    }
    if (path === '/api/watch/settings') return jsonResponse({ id: 'root', path: 'D:/media/incoming', enabled: true })
    if (path === '/api/settings/watch-runtime') return jsonResponse({ poll_interval_seconds: 15, stability_debounce_seconds: 30 })
    if (path === '/api/watch/status') return jsonResponse(watchStatus(options.watchStatusState ?? 'running'))
    if (path === '/api/watch/children') return jsonResponse(watchChildren())
    if (path === '/api/inventory/directories') return jsonResponse(directoryListing())
    if (path === '/api/origins') return jsonResponse(origins())
    if (path === '/api/depots') return jsonResponse(depots({ includeScheduled: options.includeScheduledDepot }))
    if (path === '/api/depots/movies-depot') return jsonResponse(depotDetail())
    if (path === '/api/organize/sessions') {
      const sessionCount = options.organizeSessionCount ?? 1
      return jsonResponse(
        Array.from({ length: sessionCount }, (_, index) =>
          organizeSession({
            sessionId: `session-${index + 1}`,
            sourcePath: sessionCount === 1 ? 'D:/media/manual/movies' : `D:/media/manual/movies-${index + 1}`,
            mediaType: options.organizeMediaType,
            candidateCount: options.organizeCandidateCount,
            overridden: organizeOverridden,
            decision: organizeDecision,
            state: options.organizeState ?? 'identified',
            llmTitleHints: options.organizeLlmTitleHints,
          }),
        ),
      )
    }
    if (path === '/api/transfer/jobs') {
      const status = options.transferJobStatus ?? 'succeeded'
      const id = status === 'succeeded' ? 'job-complete' : `job-${status}`
      const jobs = [transferJob(id, status)]
      if (options.scheduledTransferJobStatus) {
        jobs.unshift(
          transferJob(`job-scheduled-${options.scheduledTransferJobStatus}`, options.scheduledTransferJobStatus, {
            depotId: 'tv-depot',
            requestedBy: 'schedule',
          }),
        )
      }
      return jsonResponse(jobs)
    }
    if (path === '/api/activity/events') return jsonResponse({ items: options.activityEntries ?? [], limit: 250, offset: 0, has_more: false })
    if (path === '/api/rules/organize') return jsonResponse([])
    if (path === '/api/rules/transfer') return jsonResponse([])
    return jsonResponse([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function watchStatus(state: string) {
  return {
    id: 'watch',
    label: 'Watch',
    running: state === 'running',
    state,
    last_event: 'D:/media/incoming/auto-movies/Avatar.mkv',
    last_error: null,
    started_at: '2026-05-02T04:00:00Z',
    updated_at: '2026-05-02T04:00:00Z',
  }
}

function watchChildren() {
  return [
    {
      name: 'auto-movies',
      path: 'D:/media/incoming/auto-movies',
      status: 'configured',
      origin_id: 'auto-movies',
      media_type: 'movie',
      candidate_count: 2,
      unknown_count: 1,
    },
    {
      name: 'dropbox',
      path: 'D:/media/incoming/dropbox',
      status: 'unconfigured',
      origin_id: null,
      media_type: 'movie',
      candidate_count: 0,
      unknown_count: 0,
    },
  ]
}

function directoryListing() {
  return {
    path: 'D:/media/return',
    parent_path: 'D:/media',
    entries: [
      { name: 'manual', path: 'D:/media/manual', modified_time: 1777675200, blocked_reason: null },
      { name: 'library', path: 'D:/media/library', modified_time: 1777675200, blocked_reason: null },
    ],
    error: null,
  }
}

function origins() {
  return [
    {
      id: 'manual-movies',
      name: 'manual-movies',
      path: 'D:/media/manual/movies',
      media_type: 'movie',
      trigger: 'manual',
      enabled: true,
      candidate_count: 1,
      file_count: 1,
      unknown_count: 0,
      policy: { target_depot_id: 'movies-depot', organize_rule_id: null },
    },
    {
      id: 'manual-tv',
      name: 'manual-tv',
      path: 'D:/media/manual/tv',
      media_type: 'tv',
      trigger: 'manual',
      enabled: true,
      candidate_count: 1,
      file_count: 1,
      unknown_count: 0,
      policy: { target_depot_id: 'movies-depot', organize_rule_id: null },
    },
    {
      id: 'auto-movies',
      name: 'auto-movies',
      path: 'D:/media/incoming/auto-movies',
      media_type: 'movie',
      trigger: 'watch',
      enabled: true,
      candidate_count: 2,
      file_count: 2,
      unknown_count: 1,
      policy: { target_depot_id: 'movies-depot', organize_rule_id: null },
    },
  ]
}

function depots({ includeScheduled = false }: { includeScheduled?: boolean } = {}) {
  const configuredDepots = [
    {
      id: 'movies-depot',
      name: 'movies-depot',
      path: 'D:/media/depot/movies',
      media_type: 'movie',
      enabled: true,
      pending_count: 2,
      policy: { target_library_path: 'D:/media/library/movies', trigger: 'manual', transfer_rule_id: null, schedule: null as string | null },
    },
  ]
  if (includeScheduled) {
    configuredDepots.push({
      id: 'tv-depot',
      name: 'tv-depot',
      path: 'D:/media/depot/tv',
      media_type: 'tv',
      enabled: true,
      pending_count: 3,
      policy: { target_library_path: 'D:/media/library/tv', trigger: 'scheduled', transfer_rule_id: null, schedule: '0 4 * * *' },
    })
  }
  return configuredDepots
}

function depotDetail() {
  return {
    ...depots()[0],
    candidates: [
      {
        id: 'depot-candidate-folder-1',
        kind: 'folder',
        path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}',
        relative_path: 'Avatar (2009) {tmdb-19995}',
        display_name: 'Avatar (2009) {tmdb-19995}',
        size_bytes: 4608,
        modified_time: 1777675200,
        file_count: 2,
        media_count: 1,
        files: [
          {
            id: 'depot-file-1',
            path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}/Avatar (2009).mkv',
            relative_path: 'Avatar (2009) {tmdb-19995}/Avatar (2009).mkv',
            candidate_relative_path: 'Avatar (2009).mkv',
            display_name: 'Avatar (2009).mkv',
            size_bytes: 4096,
            modified_time: 1777675200,
            extension: '.mkv',
            is_media: true,
            blocked_reason: null,
          },
          {
            id: 'depot-file-2',
            path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}/Avatar.nfo',
            relative_path: 'Avatar (2009) {tmdb-19995}/Avatar.nfo',
            candidate_relative_path: 'Avatar.nfo',
            display_name: 'Avatar.nfo',
            size_bytes: 512,
            modified_time: 1777675200,
            extension: '.nfo',
            is_media: false,
            blocked_reason: null,
          },
        ],
        tree: {},
        blocked_reason: null,
      },
      {
        id: 'depot-candidate-file-1',
        kind: 'file',
        path: 'D:/media/depot/movies/Loose.mkv',
        relative_path: 'Loose.mkv',
        display_name: 'Loose.mkv',
        size_bytes: 2048,
        modified_time: 1777675200,
        file_count: 1,
        media_count: 1,
        files: [],
        tree: {},
        blocked_reason: null,
      },
    ],
  }
}

function depotCandidateDetail() {
  const candidate = depotDetail().candidates[0]
  return {
    candidate,
    detail: {
      path: candidate.path,
      exists: true,
      file_type: 'directory',
      size_bytes: null,
      created_time: 1777671600,
      modified_time: 1777675200,
      is_symlink: false,
      is_reparse_point: false,
      safe_to_delete: true,
      blocked_reason: null,
    },
  }
}

function depotCandidateFileDetail() {
  const candidate = depotDetail().candidates[0]
  const file = candidate.files[0]
  return {
    candidate,
    file,
    detail: {
      path: file.path,
      exists: true,
      file_type: 'regular_file',
      size_bytes: file.size_bytes,
      created_time: 1777671600,
      modified_time: file.modified_time,
      is_symlink: false,
      is_reparse_point: false,
      safe_to_delete: true,
      blocked_reason: null,
    },
  }
}

function depotMutationResponse() {
  return {
    outcome: {
      action: 'rename',
      scope: 'candidate',
      status: 'succeeded',
      depot_id: 'movies-depot',
      candidate_id: 'depot-candidate-folder-1',
      old_candidate_id: 'depot-candidate-folder-1',
      new_candidate_id: 'depot-candidate-folder-2',
      file_id: null,
      old_file_id: null,
      new_file_id: null,
      old_path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}',
      new_path: 'D:/media/depot/movies/Avatar Fixed',
      affected_file_count: 2,
      total_size_bytes: 4608,
      message: 'depot candidate renamed',
      blocked_reason: null,
    },
  }
}

function organizeSession({
  sessionId = 'session-1',
  sourcePath = 'D:/media/manual/movies',
  mediaType = 'movie',
  candidateCount = 1,
  overridden = false,
  decision = null,
  state = 'identified',
  llmTitleHints = false,
}: {
  sessionId?: string
  sourcePath?: string
  mediaType?: 'movie' | 'tv'
  candidateCount?: number
  overridden?: boolean
  decision?: 'accept' | 'ignore' | null
  state?: 'scanning' | 'scanned' | 'identifying' | 'identified'
  llmTitleHints?: boolean
} = {}) {
  return {
    id: sessionId,
    kind: 'origin',
    path: sourcePath,
    media_type: mediaType,
    state,
    policy: { target_depot_id: 'movies-depot', organize_rule_id: null },
    created_at: '2026-05-02T04:00:00Z',
    last_active_at: '2026-05-02T04:00:00Z',
    expires_at: '2026-05-02T05:00:00Z',
    idle_timeout_seconds: 3600,
    review_candidates: [
      sourceCandidate({ mediaType, itemCount: candidateCount, overridden, decision, identified: state === 'identified', llmTitleHints }),
    ],
    last_source_action_outcome: null,
  }
}

function sourceCandidate({
  mediaType = 'movie',
  itemCount = 1,
  overridden = false,
  decision = null,
  identified = true,
  llmTitleHints = false,
}: {
  mediaType?: 'movie' | 'tv'
  itemCount?: number
  overridden?: boolean
  decision?: 'accept' | 'ignore' | null
  identified?: boolean
  llmTitleHints?: boolean
} = {}) {
  const isTv = mediaType === 'tv'
  const title = overridden ? (isTv ? 'Override Show' : 'Override Movie') : isTv ? 'Example Show' : 'Avatar'
  const tmdbId = overridden ? 2 : isTv ? 101 : 19995
  const year = overridden ? 2022 : isTv ? 2020 : 2009
  return {
    id: 'source-candidate-1',
    media_type: mediaType,
    source_root: isTv ? 'D:/media/manual/tv' : 'D:/media/manual/movies',
    source_path: isTv ? 'D:/media/manual/tv/Example Show' : 'D:/media/manual/movies/Avatar.mkv',
    display_name: isTv ? 'Example Show' : 'Avatar',
    structure: isTv ? 'tv_show' : 'movie_file',
    kind: isTv ? 'tv_show' : 'movie_file',
    status: 'active',
    selection_decision: 'accept',
    file_count: itemCount,
    active_file_count: itemCount,
    total_size: itemCount * 4096,
    active_total_size: itemCount * 4096,
    files: Array.from({ length: itemCount }, (_, index) => sourceFile({ mediaType, index, identified })),
    match: identified
      ? {
          source_candidate_id: 'source-candidate-1',
          confidence: 'high',
          metadata: { title, year, tmdb_id: tmdbId },
          metadata_source: overridden ? 'manual_override' : 'auto',
          manual_override_tmdb_id: overridden ? String(tmdbId) : null,
          evidence: llmTitleHints ? llmTitleEvidence(year) : {},
          acceptance: { can_accept: true, blockers: [] },
        }
      : null,
    plan_items: identified
      ? Array.from({ length: itemCount }, (_, index) => planItem({ mediaType, index, overridden, decision }))
      : [],
    warnings: [],
  }
}

function llmTitleEvidence(year: number) {
  return {
    summary: [
      {
        source: 'llm_hint',
        confidence: 'medium',
        values: {
          titles: [
            { value: '\u963f\u51e1\u8fbe', kind: 'chinese', source: 'llm' },
            { value: 'Avatar', kind: 'english', source: 'llm' },
          ],
          year,
          tmdb_id: null,
        },
        reason: null,
      },
    ],
  }
}

function sourceFile({
  mediaType = 'movie',
  index = 0,
  identified = true,
}: {
  mediaType?: 'movie' | 'tv'
  index?: number
  identified?: boolean
} = {}) {
  const isTv = mediaType === 'tv'
  const relativePath = isTv ? `Season 1/Example Show - S01E0${index + 1}.mkv` : 'Avatar.mkv'
  return {
    id: `source-file-${index + 1}`,
    path: isTv ? `D:/media/manual/tv/Example Show/${relativePath}` : 'D:/media/manual/movies/Avatar.mkv',
    relative_path: relativePath,
    extension: '.mkv',
    classification: 'video',
    status: 'active',
    size_bytes: 4096,
    modified_time: 1777675200,
    planned_item_ids: identified ? [`plan-item-${index + 1}`] : [],
    plan_status: identified ? (index === 0 ? 'planned_primary' : 'planned_video') : 'unplanned_extra_video',
  }
}

function planItem({
  mediaType = 'movie',
  index = 0,
  overridden = false,
  decision = null,
}: {
  mediaType?: 'movie' | 'tv'
  index?: number
  overridden?: boolean
  decision?: 'accept' | 'ignore' | null
} = {}) {
  const isTv = mediaType === 'tv'
  const title = overridden ? (isTv ? 'Override Show' : 'Override Movie') : isTv ? 'Example Show' : 'Avatar'
  const tmdbId = overridden ? 2 : isTv ? 101 : 19995
  const year = overridden ? 2022 : isTv ? 2020 : 2009
  const sourcePath = isTv ? `D:/media/manual/tv/Example Show/Season 1/Example Show - S01E0${index + 1}.mkv` : 'D:/media/manual/movies/Avatar.mkv'
  return {
    id: `plan-item-${index + 1}`,
    source_candidate_id: 'source-candidate-1',
    source_file_id: `source-file-${index + 1}`,
    source_path: sourcePath,
    source_size: 4096,
    source_mtime: 1777675200,
    confidence: 'high',
    metadata: { title, year, tmdb_id: tmdbId },
    metadata_source: overridden ? 'manual_override' : 'auto',
    manual_override_tmdb_id: overridden ? String(tmdbId) : null,
    evidence: {},
    preview: {
      preview_bucket: 'A',
      matched_category: null,
      proposed_relative_path: isTv
        ? `${title} (${year}) {tmdb-${tmdbId}}/Season 1/${title} - S01E0${index + 1}.mkv`
        : `${title} (${year}) {tmdb-${tmdbId}}/${title} (${year}).mkv`,
      render_warnings: [],
    },
    user_decision: decision,
    acceptance: { can_accept: true, blockers: [] },
  }
}

function sourceFileDetail() {
  return {
    path: 'D:/media/manual/movies/Avatar.mkv',
    exists: true,
    file_type: 'regular_file',
    size_bytes: 4096,
    created_time: 1777671600,
    modified_time: 1777675200,
    classification: 'video',
    source_candidate_id: 'source-candidate-1',
    source_candidate_display_name: 'Avatar',
    source_file_id: 'source-file-1',
    relative_path: 'Avatar.mkv',
    blocked_reason: null,
  }
}

function tmdbSearchResponse(page: number, totalPages: number, mediaType: 'movie' | 'tv') {
  const isTv = mediaType === 'tv'
  return {
    page,
    total_pages: totalPages,
    total_results: totalPages,
    results: [
      {
        tmdb_id: 2,
        media_type: mediaType,
        title: isTv ? 'Override Show' : 'Override Movie',
        original_title: isTv ? 'Override Show Original' : 'Override Movie Original',
        year: 2022,
        overview: 'A precise manual match.',
        poster_url: 'https://image.tmdb.org/t/p/w154/poster.jpg',
        vote_average: 8.2,
        popularity: 42,
        confidence: 'high',
        score: 9000,
        reason: 'exact_title_year_match',
      },
    ],
  }
}

function transferJob(
  id: string,
  status: string,
  { depotId = 'movies-depot', requestedBy = 'web-ui' }: { depotId?: string; requestedBy?: string } = {},
) {
  return {
    id,
    depot_id: depotId,
    status,
    requested_by: requestedBy,
    error_code: null,
    created_at: '2026-05-02T04:00:00Z',
    started_at: null,
    finished_at: null,
    message: status === 'failed' ? 'Transfer failed' : null,
    metadata: {},
  }
}

export function transferActivity(id: string, status: string, summary: string) {
  return {
    id,
    time: '2026-05-02T04:02:00Z',
    area: 'manual_transfer',
    action: 'transfer',
    status,
    reason: status === 'failed' ? 'destination_exists' : null,
    summary,
    entity_type: 'file',
    trace_id: 'job-complete',
    entity_source: 'D:/media/depot/movies/Avatar.mkv',
    entity_target: 'D:/media/library/movies/Avatar.mkv',
    media_type: 'movie',
    tmdb_id: '19995',
    origin_id: null,
    origin_name: null,
    origin_path: null,
    depot_id: 'movies-depot',
    depot_name: 'movie',
    depot_path: 'D:/media/depot/movies',
    library_path: 'D:/media/library/movies',
    rule_id: null,
    rule_name: null,
    context: {},
  }
}

export function transferExceptionActivity() {
  return transferActivity('activity-transfer-exception', 'failed', 'Transfer failed')
}

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
