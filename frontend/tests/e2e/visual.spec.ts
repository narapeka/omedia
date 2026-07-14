import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('omedia.locale', 'en-US')
  })
  await mockApi(page)
})

test('Dashboard surfaces real attention and primary navigation hides depot and Rules', async ({ page }) => {
  await page.goto('/dashboard')

  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByText('Pipelines Overview')).toBeVisible()
  await expect(page.getByText('Organize Overview')).toBeVisible()
  await expect(page.getByText('Transfer Overview')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open Scheduled Transfers' })).toContainText('1')
  await expect(page.getByText('Daily at 04:00')).toHaveCount(0)
  await expect(page.getByRole('columnheader', { name: 'Source' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Expand organize activity table' }).click()
  await expect(page.getByText('D:/media/manual/movies/Avatar.mkv')).toBeVisible()
  const workflowNav = page.getByRole('navigation', { name: 'Workflows' })
  await expect(workflowNav.getByRole('link', { name: /depot/ })).toHaveCount(0)
  await expect(workflowNav.getByRole('link', { name: /Rules/ })).toHaveCount(0)
  await expectNonBlankScreenshot(page)
})

test('Directory picker keeps its actions visible on desktop and mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.route('**/api/inventory/directories**', async (route) => {
    await route.fulfill({
      json: {
        path: 'D:/media/return',
        parent_path: 'D:/media',
        entries: Array.from({ length: 24 }, (_, index) => ({
          name: `directory-${index + 1}`,
          path: `D:/media/return/directory-${index + 1}`,
          modified_time: 1777675200,
          blocked_reason: null,
        })),
        error: null,
      },
    })
  })

  await page.goto('/settings')
  await page.getByRole('button', { name: 'Create Depot' }).click()
  await page.getByRole('dialog', { name: 'Create Depot' }).getByRole('button', { name: 'Select' }).first().click()

  const picker = page.getByRole('dialog', { name: 'Choose Depot path' })
  const cancel = picker.getByRole('button', { name: 'Cancel' })
  const confirm = picker.getByRole('button', { name: 'Use as Depot path' })
  await expect(cancel).toBeVisible()
  await expect(confirm).toBeVisible()
  await expect(cancel).toBeInViewport({ ratio: 1 })
  await expect(confirm).toBeInViewport({ ratio: 1 })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(cancel).toBeVisible()
  await expect(confirm).toBeVisible()
  await expect(cancel).toBeInViewport({ ratio: 1 })
  await expect(confirm).toBeInViewport({ ratio: 1 })
})

test('Settings manages Origins, Depots, and Watch configuration without synthetic grouping', async ({ page }) => {
  await page.goto('/settings')

  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Path planning' })).toBeVisible()
  await page.getByRole('button', { name: 'Expand movies-depot' }).click()
  await expect(page.getByRole('columnheader', { name: 'Origin name' })).toBeVisible()
  await page.getByRole('button', { name: 'Create Origin' }).click()
  await page.getByLabel('Name').fill('Movie Inbox')
  await page.getByLabel('Source path').fill('D:/media/manual/new-movies')
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.getByText('Movie Inbox')).toHaveCount(0)

  await page.getByRole('button', { name: 'Create Depot' }).click()
  await expect(page.getByRole('dialog', { name: 'Create Depot' })).toBeVisible()
  await page.getByRole('dialog', { name: 'Create Depot' }).getByLabel('Name').fill('Movies Staging')
  await chooseDialogSelectOption(page, 'Create Depot', 0, 'Movie')
  const createDepotDialog = page.getByRole('dialog', { name: 'Create Depot' })
  await createDepotDialog.getByRole('textbox', { name: /Depot path/ }).fill('D:/media/depot/new-movies')
  await createDepotDialog.getByRole('textbox', { name: /Library path/ }).fill('D:/media/library/new-movies')
  await page.getByRole('button', { name: 'Cancel' }).click()

  await page.goto('/services#watch')
  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('dialog', { name: 'Watch settings' })).toBeVisible()
  await page.getByRole('button', { name: 'Select' }).click()
  await expect(page.getByRole('dialog', { name: 'Choose Watch root' })).toBeVisible()
  await page.getByRole('button', { name: 'Use as Watch root' }).click()
  await expect(page.getByLabel('Watch root path')).toHaveValue('D:/media/return')
  await page.getByLabel('Poll interval seconds').fill('3')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Watch settings saved.')).toBeVisible()

  await page.goto('/settings?broken=1')
  await expect(page.getByRole('tab', { name: 'Path planning' })).toBeVisible()
  await expect(page.getByText('broken-origin')).toHaveCount(0)
  await expectNonBlankScreenshot(page)
})

test('Settings Rules, Providers, Media, and Maintenance render object-first controls', async ({ page }) => {
  await page.goto('/settings')

  await page.getByRole('tab', { name: 'Rules' }).click()
  await expect(page.getByText('Movie first-character buckets')).toBeVisible()
  await expect(page.getByText('Library decade buckets')).toBeVisible()
  await expect(page.getByText('Organize Rule Metadata')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Remove rule' }).first()).toBeVisible()
  await page.getByRole('tab', { name: 'Providers' }).click()
  await expect(page.getByText('TMDB provider')).toBeVisible()
  await page.getByLabel('Base URL').first().fill('https://api.themoviedb.org/3')
  await expect(page.getByText('These groups only affect Organize')).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Minimum non-subtitle size (MiB)' })).toHaveValue('50')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Media settings saved.')).toBeVisible()
  await page.getByRole('tab', { name: 'Maintenance' }).click()
  await expect(page.getByRole('heading', { name: 'Restore config' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Diagnostics' })).toHaveCount(0)
  await expectNonBlankScreenshot(page)
})

test('Organize scans manual Origins, cleans source, identifies, overrides, decides, and organizes', async ({ page }) => {
  await page.goto('/organize?smoke=source-review')

  await expect(page.getByRole('heading', { name: 'Organize' })).toBeVisible()
  await page.getByRole('button', { name: 'Expand manual-movies' }).click()
  await page.getByRole('button', { name: /Expand Avatar/ }).click()
  await expect(page.getByText('No move planned yet.')).toBeVisible()
  await page.getByRole('button', { name: 'Details' }).first().click()
  await page.getByRole('dialog', { name: 'Source candidate' }).getByLabel('Name').fill('Avatar.Renamed.mkv')
  await page.getByRole('dialog', { name: 'Source candidate' }).getByRole('button', { name: 'Rename' }).click()
  await expect(page.getByText('Avatar.Renamed.mkv', { exact: true })).toBeVisible()

  await page.getByRole('switch', { name: 'Accept Avatar' }).click()
  await expect(page.getByRole('button', { name: 'Identify' })).toBeEnabled()
  await page.getByRole('button', { name: 'Identify' }).click()
  await expect(page.getByText('Avatar (2009) {tmdb-19995}/Avatar (2009).mkv')).toBeVisible()
  await page.getByRole('button', { name: 'Correct movie match' }).click()
  await page.getByRole('dialog', { name: 'Correct movie match' }).getByRole('button', { name: 'Search' }).click()
  await page.getByRole('button', { name: /Override Movie/ }).click()
  await page.getByRole('button', { name: 'Apply selected' }).click()
  await expect(page.getByText('Override Movie (2022) {tmdb-2}/Override Movie (2022).mkv')).toBeVisible()
  await page.getByRole('switch', { name: 'Accept Avatar' }).click()
  const organizeResponse = page.waitForResponse(
    (response) => response.url().includes('/api/organize/sessions/session-1/execute') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Organize', exact: true }).click()
  await organizeResponse
  await expect(page.getByText('Organize complete')).toHaveCount(0)
  await expect(page.getByText('1 moved, 0 skipped, 0 failed')).toHaveCount(0)
  await expectNonBlankScreenshot(page)
})

test('Transfer supports scanned Depot cards, accepted candidates, send back, and job cancel', async ({ page }) => {
  await page.goto('/transfer')

  await expect(page.getByRole('heading', { name: 'Transfer' })).toBeVisible()
  await expect(page.getByText('Choose a Depot and scan to open a manual transfer card.')).toBeVisible()
  const scan = page.getByRole('button', { name: 'Scan' })
  await expect(scan).toBeDisabled()
  await page.getByRole('combobox', { name: 'Predefined Depots' }).click()
  await page.getByRole('combobox', { name: 'Predefined Depots' }).fill('movies-depot')
  await page.getByRole('option', { name: /movies-depot/ }).click()
  await expect(scan).toBeEnabled()
  await scan.click()
  await page.getByRole('button', { name: 'Expand movies-depot' }).click()
  await expect(page.getByRole('switch', { name: 'Accepted Avatar (2009) {tmdb-19995}; click to ignore' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Transfer Avatar (2009) {tmdb-19995}' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Transfer selected', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Send back selected' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Send back Avatar (2009) {tmdb-19995}' }).click()
  const sendBackDialog = page.getByRole('dialog', { name: 'Choose send back destination' })
  await expect(sendBackDialog).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Directory path' })).toBeVisible()
  await expect(page.getByLabel('Server path')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Browse' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Send back here' })).toBeEnabled()
  await sendBackDialog.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('button', { name: 'Transfer', exact: true }).click()
  await page.goto('/dashboard')
  await expect(page.getByText('Transfer Overview')).toBeVisible()
  await expect(page.getByText('running').first()).toBeVisible()
  await page.goto('/transfer')
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expectNonBlankScreenshot(page)
})

test('Services controls, Activity filters, and mobile smoke remain readable', async ({ page }) => {
  await page.goto('/services')

  await expect(page.getByRole('heading', { name: 'Services' })).toBeVisible()
  await expect(page.locator('[data-slot="card-title"]').filter({ hasText: 'Auto organize' })).toBeVisible()

  await page.goto('/activity')
  await expect(page.getByRole('heading', { name: 'Activity' })).toBeVisible()
  await expect(page.getByText('Transfer failed', { exact: true }).first()).toBeVisible()
  await page.getByPlaceholder('Search filename, path, media title, TMDB ID, Depot, or failure reason').fill('19995')
  await page.getByRole('button', { name: /Open history details for/ }).first().click()
  await expect(page.getByText('Overwrite blocked').first()).toBeVisible()
  await expect(page.getByText('Status', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('TMDB ID', { exact: true })).toBeVisible()
  await expect(page.getByText('19995', { exact: true })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 820 })
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(scrollWidth).toBeLessThanOrEqual(430)
  await expectNonBlankScreenshot(page)
})

async function expectNonBlankScreenshot(page: Page) {
  const screenshot = await page.screenshot()
  expect(screenshot.byteLength).toBeGreaterThan(20_000)
}

async function chooseDialogSelectOption(page: Page, dialogName: string | RegExp, index: number, option: string | RegExp) {
  await page.getByRole('dialog', { name: dialogName }).getByRole('combobox').nth(index).click()
  await page.getByRole('option', { name: option }).click()
}

async function mockApi(page: Page) {
  let smokeInitialized = false
  let sessionState: 'scanned' | 'identified' = 'identified'
  let overridden = false
  let renamed = false
  let selectionDecision: 'accept' | 'ignore' = 'ignore'
  let planDecision: 'accept' | 'ignore' | null = null
  let transferJobState: 'idle' | 'running' | 'cancelled' = 'idle'

  const sessionOptions = () => {
    if (page.url().includes('smoke=source-review') && !smokeInitialized) {
      sessionState = 'scanned'
      smokeInitialized = true
    }
    return { state: sessionState, overridden, renamed, selectionDecision, planDecision }
  }

  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const empty = page.url().includes('empty=1')
    const broken = page.url().includes('broken=1')

    if (method === 'POST' || method === 'PUT' || method === 'DELETE') {
      if (path.endsWith('/search')) return route.fulfill({ json: tmdbSearchResponse() })
      if (path.startsWith('/api/identify/sessions/') && !path.endsWith('/search') && !path.includes('/override')) {
        sessionState = 'identified'
        return route.fulfill({ json: organizeSessions(sessionOptions())[0] })
      }
      if (path.includes('/candidates/') && path.endsWith('/decision')) {
        const nextDecision = request.postDataJSON()?.decision
        if (sessionState === 'scanned') {
          selectionDecision = nextDecision ?? selectionDecision
        } else {
          planDecision = nextDecision ?? planDecision
        }
        return route.fulfill({ status: 204, body: '' })
      }
      if (path.includes('/plan-items/') && path.endsWith('/decision')) {
        planDecision = request.postDataJSON()?.decision ?? planDecision
        return route.fulfill({ status: 204, body: '' })
      }
      if (path.includes('/override')) {
        overridden = true
        return route.fulfill({ json: organizeSessions(sessionOptions())[0] })
      }
      if (method === 'PUT' && path.endsWith('/rename')) {
        renamed = true
        return route.fulfill({ json: organizeSessions(sessionOptions())[0] })
      }
      if (path.endsWith('/execute')) return route.fulfill({ json: { session_id: 'session-1', moved: 1, skipped: 0, failed: 0, results: [] } })
      if (path.startsWith('/api/transfer/jobs/') && path.endsWith('/cancel')) {
        transferJobState = 'cancelled'
        return route.fulfill({ json: transferJob('job-running', 'cancelled') })
      }
      if (path.includes('/transfer')) {
        transferJobState = 'running'
        return route.fulfill({ json: transferJob('job-running', 'running') })
      }
      if (path.includes('/depots/') && path.endsWith('/return')) return route.fulfill({ json: { activity_events: ['activity-1'] } })
      if (path.includes('/rules/organize')) return route.fulfill({ json: organizeRule() })
      if (path.includes('/rules/transfer')) return route.fulfill({ json: transferRule() })
      if (path.includes('/watch/settings')) return route.fulfill({ json: watchSettings() })
      if (path === '/api/settings/organize') return route.fulfill({ json: request.postDataJSON?.() ?? { extensions: { video: ['.mkv'], subtitle: ['.srt'], sidecar: ['.nfo'] }, min_non_subtitle_file_size_mb: 50 } })
      if (path.includes('/origins/')) return route.fulfill({ json: request.postDataJSON?.() ?? origins()[0] })
      if (path.includes('/depots/')) return route.fulfill({ json: request.postDataJSON?.() ?? depots()[0] })
      return route.fulfill({ json: { ok: true } })
    }

    if (path === '/api/settings/health') {
      return route.fulfill({
        json: {
          ok: true,
          database: true,
          config_loaded: true,
          origins: empty ? 0 : 2,
          depots: empty ? 0 : 2,
          organize_rules: 1,
          transfer_rules: 1,
          watched_folders: 1,
          scheduled_transfers: empty ? 0 : 1,
        },
      })
    }
    if (path === '/api/watch/settings') return route.fulfill({ json: watchSettings() })
    if (path === '/api/watch/status') return route.fulfill({ json: watchStatus() })
    if (path === '/api/watch/children') return route.fulfill({ json: watchChildren() })
    if (path === '/api/inventory/directories') return route.fulfill({ json: directoryListing() })
    if (path === '/api/origins') return route.fulfill({ json: empty ? [] : broken ? brokenOrigins() : origins() })
    if (path === '/api/depots/movies-depot') return route.fulfill({ json: depotDetail() })
    if (path === '/api/depots') return route.fulfill({ json: empty ? [] : depots() })
    if (path === '/api/organize/sessions') return route.fulfill({ json: organizeSessions(sessionOptions()) })
    if (path.endsWith('/detail')) return route.fulfill({ json: sourceFileDetail(renamed) })
    if (path === '/api/transfer/jobs') {
      return route.fulfill({
        json: [
          ...(transferJobState !== 'idle' ? [transferJob('job-running', transferJobState)] : []),
          transferJob('job-failed', 'failed'),
          transferJob('job-complete', 'succeeded'),
        ],
      })
    }
    if (path === '/api/activity/events') return route.fulfill({ json: activityEntries() })
    if (path === '/api/rules/organize') return route.fulfill({ json: [organizeRule()] })
    if (path === '/api/rules/transfer') return route.fulfill({ json: [transferRule()] })
    if (path === '/api/settings/providers') return route.fulfill({ json: providerStatus() })
    if (path === '/api/settings/organize') {
      return route.fulfill({ json: { extensions: { video: ['.mkv'], subtitle: ['.srt'], sidecar: ['.nfo'] }, min_non_subtitle_file_size_mb: 50 } })
    }
    if (path === '/api/settings/watch-runtime') return route.fulfill({ json: { poll_interval_seconds: 2, stability_debounce_seconds: 5 } })

    return route.fulfill({ json: [] })
  })
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

function providerStatus() {
  return {
    tmdb_configured: true,
    tmdb_base_url: 'https://api.themoviedb.org/3',
    tmdb_rate_limit: 4,
    tmdb_proxy: null,
    llm_configured: false,
    llm_base_url: 'https://api.openai.com/v1/',
    llm_model: null,
    llm_batch_size: 50,
    llm_rate_limit: 2,
    llm_proxy: null,
  }
}

function watchSettings() {
  return { id: 'root', path: 'D:/media/incoming', enabled: true }
}

function watchStatus() {
  return { id: 'watch', label: 'Watch worker', running: true, state: 'running', last_event: 'auto-movies organized', last_error: null, updated_at: '2026-05-02T04:00:00Z' }
}

function watchChildren() {
  return [
    { name: 'auto-movies', path: 'D:/media/incoming/auto-movies', status: 'configured', origin_id: 'auto-movies', media_type: 'movie', candidate_count: 2, unknown_count: 1 },
    { name: 'dropbox', path: 'D:/media/incoming/dropbox', status: 'unconfigured', origin_id: null, media_type: null, candidate_count: 0, unknown_count: 0 },
  ]
}

function origins() {
  return [
    { id: 'manual-movies', name: 'manual-movies', path: 'D:/media/manual/movies', media_type: 'movie', trigger: 'manual', enabled: true, candidate_count: 1, file_count: 1, unknown_count: 0, policy: { target_depot_id: 'movies-depot', organize_rule_id: 'movie-first-char' } },
    { id: 'auto-movies', name: 'auto-movies', path: 'D:/media/incoming/auto-movies', media_type: 'movie', trigger: 'watch', enabled: true, candidate_count: 2, file_count: 2, unknown_count: 1, policy: { target_depot_id: 'movies-depot', organize_rule_id: 'movie-first-char' } },
  ]
}

function brokenOrigins() {
  return [
    ...origins(),
    { id: 'broken-origin', name: 'broken-origin', path: 'D:/media/manual/broken', media_type: 'movie', trigger: 'manual', enabled: true, candidate_count: 0, file_count: 0, unknown_count: 0, policy: { target_depot_id: 'D:/missing/depot', organize_rule_id: 'movie-first-char' } },
  ]
}

function depots() {
  return [
    { id: 'movies-depot', name: 'movies-depot', path: 'D:/media/depot/movies', media_type: 'movie', enabled: true, pending_count: 2, policy: { target_library_path: 'D:/media/library/movies', trigger: 'manual', transfer_rule_id: 'library-decade', schedule: null }, last_failed_transfer: transferJob('job-failed', 'failed') },
    { id: 'tv-depot', name: 'tv-depot', path: 'D:/media/depot/tv', media_type: 'tv', enabled: true, pending_count: 0, policy: { target_library_path: 'D:/media/library/tv', trigger: 'scheduled', transfer_rule_id: null, schedule: '0 4 * * *' } },
  ]
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
          { id: 'depot-file-1', path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}/Avatar (2009).mkv', relative_path: 'Avatar (2009) {tmdb-19995}/Avatar (2009).mkv', candidate_relative_path: 'Avatar (2009).mkv', display_name: 'Avatar (2009).mkv', size_bytes: 4096, modified_time: 1777675200, extension: '.mkv', is_media: true, blocked_reason: null },
          { id: 'depot-file-2', path: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}/Avatar.nfo', relative_path: 'Avatar (2009) {tmdb-19995}/Avatar.nfo', candidate_relative_path: 'Avatar.nfo', display_name: 'Avatar.nfo', size_bytes: 512, modified_time: 1777675200, extension: '.nfo', is_media: false, blocked_reason: null },
        ],
        tree: {},
        blocked_reason: null,
      },
    ],
  }
}

function organizeSessions({ state = 'identified', overridden = false, renamed = false, selectionDecision = 'ignore', planDecision = null }: { state?: 'scanned' | 'identified'; overridden?: boolean; renamed?: boolean; selectionDecision?: 'accept' | 'ignore'; planDecision?: 'accept' | 'ignore' | null } = {}) {
  return [
    {
      id: 'session-1',
      kind: 'origin',
      path: 'D:/media/manual/movies',
      media_type: 'movie',
      state,
      policy: { target_depot_id: 'movies-depot', organize_rule_id: 'movie-first-char' },
      created_at: '2026-05-02T04:00:00Z',
      last_active_at: '2026-05-02T04:00:00Z',
      expires_at: '2026-05-02T05:00:00Z',
      idle_timeout_seconds: 3600,
      review_candidates: [sourceCandidate({ identified: state === 'identified', overridden, renamed, selectionDecision, planDecision })],
      last_source_action_outcome: null,
    },
  ]
}

function sourceCandidate({ identified = true, overridden = false, renamed = false, selectionDecision = 'ignore', planDecision = null }: { identified?: boolean; overridden?: boolean; renamed?: boolean; selectionDecision?: 'accept' | 'ignore'; planDecision?: 'accept' | 'ignore' | null } = {}) {
  const title = overridden ? 'Override Movie' : 'Avatar'
  const tmdbId = overridden ? 2 : 19995
  const year = overridden ? 2022 : 2009
  const movieName = renamed ? 'Avatar.Renamed.mkv' : 'Avatar.mkv'
  return {
    id: 'source-candidate-1',
    media_type: 'movie',
    source_root: 'D:/media/manual/movies',
    source_path: `D:/media/manual/movies/${movieName}`,
    display_name: 'Avatar',
    structure: 'movie_file',
    kind: 'movie_file',
    status: 'active',
    selection_decision: selectionDecision,
    file_count: 1,
    active_file_count: 1,
    total_size: 4096,
    active_total_size: 4096,
    files: [{ id: 'source-file-1', path: `D:/media/manual/movies/${movieName}`, relative_path: movieName, extension: '.mkv', classification: 'video', status: 'active', size_bytes: 4096, modified_time: 1777675200, planned_item_ids: identified ? ['plan-item-1'] : [], plan_status: identified ? 'planned_primary' : 'unplanned_extra_video' }],
    match: identified ? { source_candidate_id: 'source-candidate-1', confidence: 'high', metadata: { title, year, tmdb_id: tmdbId }, metadata_source: overridden ? 'manual_override' : 'auto', manual_override_tmdb_id: overridden ? String(tmdbId) : null, acceptance: { can_accept: true, blockers: [] }, evidence: {} } : null,
    plan_items: identified ? [planItem({ overridden, renamed, decision: planDecision })] : [],
    warnings: [],
  }
}

function planItem({ overridden = false, renamed = false, decision = null }: { overridden?: boolean; renamed?: boolean; decision?: 'accept' | 'ignore' | null } = {}) {
  const title = overridden ? 'Override Movie' : 'Avatar'
  const tmdbId = overridden ? 2 : 19995
  const year = overridden ? 2022 : 2009
  return { id: 'plan-item-1', source_candidate_id: 'source-candidate-1', source_file_id: 'source-file-1', source_path: renamed ? 'D:/media/manual/movies/Avatar.Renamed.mkv' : 'D:/media/manual/movies/Avatar.mkv', source_size: 4096, source_mtime: 1777675200, confidence: 'high', metadata: { title, year, tmdb_id: tmdbId }, metadata_source: overridden ? 'manual_override' : 'auto', manual_override_tmdb_id: overridden ? String(tmdbId) : null, evidence: {}, preview: { preview_bucket: 'A', matched_category: null, proposed_relative_path: `${title} (${year}) {tmdb-${tmdbId}}/${title} (${year}).mkv`, render_warnings: [] }, acceptance: { can_accept: true, blockers: [] }, user_decision: decision }
}

function sourceFileDetail(renamed = false) {
  const movieName = renamed ? 'Avatar.Renamed.mkv' : 'Avatar.mkv'
  return { path: `D:/media/manual/movies/${movieName}`, exists: true, file_type: 'regular_file', size_bytes: 4096, created_time: 1777671600, modified_time: 1777675200, classification: 'video', source_candidate_id: 'source-candidate-1', source_candidate_display_name: 'Avatar', source_file_id: 'source-file-1', relative_path: movieName, blocked_reason: null }
}

function tmdbSearchResponse() {
  return { page: 1, total_pages: 1, total_results: 1, results: [{ tmdb_id: 2, media_type: 'movie', title: 'Override Movie', original_title: 'Override Movie Original', year: 2022, overview: 'A precise manual match.', poster_url: 'https://image.tmdb.org/t/p/w154/poster.jpg', vote_average: 8.2, popularity: 42, confidence: 'high', score: 9000, reason: 'exact_title_year_match' }] }
}

function transferJob(id: string, status: string) {
  return { id, depot_id: 'movies-depot', status, requested_by: 'web-ui', error_code: null, created_at: '2026-05-02T04:00:00Z', started_at: '2026-05-02T04:00:05Z', finished_at: status === 'running' ? null : '2026-05-02T04:01:00Z', message: status === 'failed' ? 'Destination busy' : 'Transfer complete' }
}

function activityEntries() {
  return {
    items: [
      activityEvent({
        id: 'activity-1',
        time: '2026-05-02T04:00:00Z',
        area: 'manual_organize',
        action: 'move_to_depot',
        status: 'succeeded',
        summary: 'Movie moved to Depot',
        entity_type: 'file',
        entity_source: 'D:/media/manual/movies/Avatar.mkv',
        entity_target: 'D:/media/depot/movies/Avatar (2009) {tmdb-19995}/Avatar (2009).mkv',
      }),
      activityEvent({
        id: 'activity-2',
        time: '2026-05-02T04:02:00Z',
        area: 'manual_transfer',
        action: 'transfer',
        status: 'failed',
        reason: 'destination_exists',
        summary: 'Overwrite blocked',
        entity_type: 'transfer_job',
        entity_source: 'D:/media/depot/movies/Avatar.mkv',
        entity_target: 'D:/media/library/movies/Avatar.mkv',
      }),
    ],
    limit: 250,
    offset: 0,
    has_more: false,
  }
}

function activityEvent(overrides: Record<string, unknown>) {
  return {
    id: 'activity',
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
    media_type: 'movie',
    tmdb_id: '19995',
    origin_id: 'manual-movies',
    origin_name: 'manual-movies',
    origin_path: 'D:/media/manual/movies',
    depot_id: 'movies-depot',
    depot_name: 'movie',
    depot_path: 'D:/media/depot/movies',
    library_path: 'D:/media/library/movies',
    rule_id: null,
    rule_name: null,
    context: {},
    ...overrides,
  }
}

function organizeRule() {
  return { id: 'movie-first-char', name: 'Movie first-character buckets', description: null, fallback_bucket: '{first_char}', categories: [{ name: 'animation', bucket: 'Animation', conditions: [{ field: 'tmdb.genre_ids', op: 'contains', value: 16 }] }] }
}

function transferRule() {
  return { id: 'library-decade', name: 'Library decade buckets', description: null, fallback_bucket: '{decade}', categories: [] }
}
