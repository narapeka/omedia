import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  chooseComboboxOption,
  chooseSelectOption,
  expandSession,
  expandSourceCandidate,
  mockApi,
  renderApp,
  resetAppTest,
} from './appHarness'

beforeEach(resetAppTest)

describe('Organize workflow', () => {
  it('submits an Organize candidate decision', async () => {
    const fetchMock = mockApi()
    renderApp('/organize')

    await expandSourceCandidate()
    fireEvent.click(await screen.findByRole('switch', { name: /Ignored .*click to accept/ }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/plan-items/plan-item-1/decision'),
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })

  it('searches and applies a movie TMDB result from the source candidate dialog', async () => {
    const fetchMock = mockApi()
    renderApp('/organize')

    await expandSession()
    fireEvent.click(await screen.findByRole('button', { name: 'Correct movie match' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))
    const movieResult = await within(dialog).findByRole('button', { name: /Override Movie/ })
    fireEvent.click(movieResult)
    expect(movieResult).toHaveAttribute('aria-pressed', 'true')
    expect(within(dialog).queryByText('Movie File')).not.toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Language')).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/high confidence/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/exact title/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/Score /)).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Apply to/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Use this result' })).not.toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply selected' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/search'),
        expect.objectContaining({ method: 'POST' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/candidates/source-candidate-1/override'),
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })

  it('prefills manual TMDB search with extracted CN and EN names without restoring cleared text', async () => {
    const fetchMock = mockApi({ organizeLlmTitleHints: true })
    renderApp('/organize')
    const chineseTitle = '\u963f\u51e1\u8fbe'
    const combinedTitle = `${chineseTitle} Avatar`

    await expandSession()
    fireEvent.click(await screen.findByRole('button', { name: 'Correct movie match' }))
    const dialog = await screen.findByRole('dialog')
    const searchInput = within(dialog).getByDisplayValue(combinedTitle)
    expect(searchInput).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/search'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining(`"query":"${combinedTitle}"`),
        }),
      )
    })

    fireEvent.change(searchInput, { target: { value: '' } })
    expect(searchInput).toHaveValue('')
    expect(within(dialog).queryByDisplayValue('Avatar')).not.toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Search' })).toBeDisabled()
    fireEvent.change(searchInput, { target: { value: 'Inception' } })
    expect(searchInput).toHaveValue('Inception')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/search'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"query":"Inception"'),
        }),
      )
    })
  })

  it('submits manual TMDB search with only the current query and year inputs', async () => {
    const fetchMock = mockApi()
    renderApp('/organize')

    await expandSession()
    fireEvent.click(await screen.findByRole('button', { name: 'Correct movie match' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByDisplayValue('Avatar'), { target: { value: 'Transformers' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Clear year' }))
    const yearInput = within(dialog).getByRole('textbox', { name: 'Year' })
    expect(yearInput).toHaveValue('')
    fireEvent.change(yearInput, { target: { value: '2007' } })
    expect(yearInput).toHaveValue('2007')
    fireEvent.change(yearInput, { target: { value: '' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/search'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
    const tmdbCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/identify/sessions/session-1/search'))
    const [, init] = tmdbCalls[tmdbCalls.length - 1]
    expect(JSON.parse(String(init?.body))).toEqual({
      source_candidate_id: 'source-candidate-1',
      query: 'Transformers',
      year: null,
      language: null,
      page: 1,
    })
  })

  it('keeps TV override at show group level and refreshes previews after apply', async () => {
    const fetchMock = mockApi({ organizeMediaType: 'tv', organizeCandidateCount: 2 })
    renderApp('/organize')

    await expandSession('movies')
    expect(await screen.findByRole('button', { name: 'Correct show match' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Apply TMDB override')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Correct show match' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))
    const tvResult = await within(dialog).findByRole('button', { name: /Override Show/ })
    fireEvent.click(tvResult)
    expect(tvResult).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply selected' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/candidates/source-candidate-1/override'),
        expect.objectContaining({ method: 'PUT' }),
      )
      expect(screen.getAllByText(/Override Show/).length).toBeGreaterThan(0)
    })
  })

  it('paginates manual TMDB search results', async () => {
    const fetchMock = mockApi({ tmdbTotalPages: 2 })
    renderApp('/organize')

    await expandSession()
    fireEvent.click(await screen.findByRole('button', { name: 'Correct movie match' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Search' }))
    fireEvent.click(await within(dialog).findByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1/search'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"page":2'),
        }),
      )
    })
  })

  it('shows scan inventory before Identify and posts the Identify action', async () => {
    const fetchMock = mockApi({ organizeState: 'scanned' })
    renderApp('/organize')

    expect(await screen.findByText('manual-movies')).toBeInTheDocument()
    expect(screen.queryByText('scanned')).not.toBeInTheDocument()
    const identify = await screen.findByRole('button', { name: 'Identify' })
    expect(identify).not.toBeDisabled()
    fireEvent.click(await screen.findByRole('button', { name: 'Expand manual-movies' }))

    expect(screen.queryByText('No move planned yet.')).not.toBeInTheDocument()
    await expandSourceCandidate()
    expect(await screen.findByText('No move planned yet.')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Identify' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/identify/sessions/session-1'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('scans selected manual Origins through the bulk endpoint and toasts partial failures', async () => {
    const fetchMock = mockApi({ bulkOrganizeFailure: true })
    renderApp('/organize')

    const scanSelected = await screen.findByRole('button', { name: 'Scan selected origins' })
    expect(scanSelected).toBeDisabled()
    await chooseComboboxOption('Manual origins', 'manual-movies')
    await chooseComboboxOption('Manual origins', 'manual-tv')
    await waitFor(() => expect(scanSelected).not.toBeDisabled())
    fireEvent.click(scanSelected)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/bulk'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"origin_ids":["manual-movies","manual-tv"]'),
        }),
      )
    })
    expect(await screen.findByText('manual-tv: Origin is disabled: manual-tv')).toBeInTheDocument()
  })

  it('starts an ad hoc source scan with a selected target Depot', async () => {
    const fetchMock = mockApi({ organizeSessionCount: 0 })
    renderApp('/organize')

    const adHocTab = await screen.findByRole('button', { name: 'Ad hoc source' })
    fireEvent.mouseDown(adHocTab, { button: 0, ctrlKey: false })
    fireEvent.pointerDown(adHocTab, { button: 0, ctrlKey: false, pointerType: 'mouse' })
    fireEvent.click(adHocTab)
    fireEvent.change(screen.getByLabelText('Source path'), { target: { value: 'D:/drop/Avatar.mkv' } })
    await chooseSelectOption('Target Depot', /movies-depot/)
    fireEvent.click(screen.getByRole('button', { name: 'Scan' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"source_path":"D:/drop/Avatar.mkv"'),
        }),
      )
    })
  })

  it('displays multiple active Organize sessions as independent cards', async () => {
    mockApi({ organizeSessionCount: 2 })
    renderApp('/organize')

    expect(await screen.findByText('movies-1')).toBeInTheDocument()
    expect(await screen.findByText('movies-2')).toBeInTheDocument()
    expect(await screen.findByTitle('D:/media/manual/movies-1 -> movies-depot')).toBeInTheDocument()
    expect(await screen.findByTitle('D:/media/manual/movies-2 -> movies-depot')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Identify all/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Organize all/i })).not.toBeInTheDocument()
  })

  it('summarizes accepted Organize sources in the session card header', async () => {
    mockApi({ organizeCandidateCount: 2, organizeDecision: 'accept' })
    renderApp('/organize')

    expect(await screen.findByText('manual-movies')).toBeInTheDocument()
    expect(screen.getByText('1 accepted')).toBeInTheDocument()
    expect(screen.getByText('2 files')).toBeInTheDocument()
    expect(screen.getByText('8.0 KB')).toBeInTheDocument()
    expect(screen.queryByText('1 source')).not.toBeInTheDocument()
  })

  it('opens the source entry dialog and renames/deletes file and candidate by IDs', async () => {
    const fetchMock = mockApi({ organizeState: 'scanned' })
    renderApp('/organize')

    expect(screen.queryByRole('button', { name: 'Delete file' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete source' })).not.toBeInTheDocument()

    await expandSourceCandidate()
    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar.mkv' }))
    const detailDialog = await screen.findByRole('dialog', { name: 'Source file' })
    expect(detailDialog).toBeInTheDocument()
    expect(await screen.findByText('regular file')).toBeInTheDocument()
    fireEvent.change(within(detailDialog).getByLabelText('Name'), { target: { value: 'Avatar.Renamed.mkv' } })
    fireEvent.click(within(detailDialog).getByRole('button', { name: 'Rename' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/candidates/source-candidate-1/files/source-file-1/rename'),
        expect.objectContaining({ method: 'PUT', body: expect.stringContaining('"new_name":"Avatar.Renamed.mkv"') }),
      )
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar.mkv' }))
    const deleteFileDialog = await screen.findByRole('dialog', { name: 'Source file' })
    fireEvent.click(within(deleteFileDialog).getByRole('button', { name: 'Delete' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar' }))
    const candidateDialog = await screen.findByRole('dialog', { name: 'Source candidate' })
    fireEvent.change(within(candidateDialog).getByLabelText('Name'), { target: { value: 'Avatar.Fixed.mkv' } })
    fireEvent.click(within(candidateDialog).getByRole('button', { name: 'Rename' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/candidates/source-candidate-1/rename'),
        expect.objectContaining({ method: 'PUT', body: expect.stringContaining('"new_name":"Avatar.Fixed.mkv"') }),
      )
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar' }))
    const deleteCandidateDialog = await screen.findByRole('dialog', { name: 'Source candidate' })
    fireEvent.click(within(deleteCandidateDialog).getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/candidates/source-candidate-1/files/source-file-1'),
        expect.objectContaining({ method: 'DELETE' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/candidates/source-candidate-1'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('allows candidate delete but keeps rename and file actions read-only after Identify before Organize', async () => {
    mockApi({ organizeState: 'identified' })
    renderApp('/organize')

    await expandSession()
    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar' }))
    const candidateDialog = await screen.findByRole('dialog', { name: 'Source candidate' })
    expect(within(candidateDialog).queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(within(candidateDialog).getByRole('button', { name: 'Delete' })).toBeInTheDocument()
    fireEvent.click(within(candidateDialog).getAllByRole('button', { name: 'Close' })[0])
    expect(screen.getByRole('button', { name: 'Correct movie match' })).toBeInTheDocument()

    await expandSourceCandidate()
    fireEvent.click(await screen.findByRole('button', { name: 'Details Avatar.mkv' }))
    const fileDialog = await screen.findByRole('dialog', { name: 'Source file' })
    expect(within(fileDialog).queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(within(fileDialog).queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
    fireEvent.click(within(fileDialog).getAllByRole('button', { name: 'Close' })[0])
    expect(screen.getByRole('switch', { name: 'Accept Avatar' })).toBeInTheDocument()
  })

  it('renders identifying sessions as read-only while matching runs', async () => {
    mockApi({ organizeState: 'identifying' })
    renderApp('/organize')

    expect(await screen.findByRole('progressbar', { name: 'Identifying session progress' })).toBeInTheDocument()
    expect(screen.queryByText('Identify is running. Source cleanup and move decisions are paused until matching finishes.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Correct movie match' })).not.toBeInTheDocument()
    expect(await screen.findByText('identifying')).toBeInTheDocument()
    await expandSourceCandidate()
    expect(screen.queryByRole('button', { name: 'Details' })).not.toBeInTheDocument()
  })

  it('renders scanning sessions with an indeterminate progress line', async () => {
    mockApi({ organizeState: 'scanning' })
    renderApp('/organize')

    expect(await screen.findByRole('progressbar', { name: 'Scanning session progress' })).toBeInTheDocument()
    expect(await screen.findByText('scanning')).toBeInTheDocument()
  })

  it('keeps Scan available after Identify as a restart action', async () => {
    const fetchMock = mockApi()
    renderApp('/organize')

    fireEvent.click(await screen.findByRole('button', { name: 'Scan' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/scan'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('submits Organize without rendering terminal result cards', async () => {
    const fetchMock = mockApi()
    renderApp('/organize')

    expect(await screen.findByRole('button', { name: 'Organize' })).toHaveAttribute('data-variant', 'default')
    expect(screen.getByRole('button', { name: 'Scan' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand manual-movies' }))
    expect(screen.getByRole('switch', { name: 'Accept Avatar' })).toBeInTheDocument()
    expect(screen.queryByText('identified')).not.toBeInTheDocument()
    expect(screen.queryByText(/planned move/)).not.toBeInTheDocument()
    expect(await screen.findByText('HIGH')).toBeInTheDocument()
    expect(screen.getByText('Avatar (2009) {tmdb-19995}')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'TMDB details for Avatar (2009) {tmdb-19995}' }))
    const tmdbDialog = await screen.findByRole('dialog', { name: 'TMDB details' })
    expect(within(tmdbDialog).getByRole('link', { name: 'Visit TMDB' })).toHaveAttribute('href', 'https://www.themoviedb.org/movie/19995')
    fireEvent.click(within(tmdbDialog).getAllByRole('button', { name: 'Close' })[0])
    expect(screen.queryByRole('button', { name: 'Identity evidence' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Details Avatar' })).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Accept Avatar' })).toBeInTheDocument()

    await expandSourceCandidate()
    fireEvent.click(await screen.findByRole('switch', { name: /Ignored .*click to accept/ }))
    const organize = await screen.findByRole('button', { name: 'Organize' })
    await waitFor(() => expect(organize).not.toBeDisabled())
    fireEvent.click(organize)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/organize/sessions/session-1/execute'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
    expect(screen.queryByText('Organize complete')).not.toBeInTheDocument()
    expect(screen.queryByText('Affected Depot D:/media/depot/movies')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Open Activity receipts' })).not.toBeInTheDocument()
  })
})
