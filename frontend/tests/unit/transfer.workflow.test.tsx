import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { chooseComboboxOption, mockApi, renderApp, resetAppTest, transferExceptionActivity } from './appHarness'

beforeEach(resetAppTest)

type Role = Parameters<typeof screen.getByRole>[0]
type RoleOptions = Parameters<typeof screen.getByRole>[1]

const getFirstByRole = (role: Role, options?: RoleOptions) => screen.getAllByRole(role, options)[0]
const findFirstByRole = async (role: Role, options?: RoleOptions) => (await screen.findAllByRole(role, options))[0]
const uiWait = { timeout: 5000 }
const findManualTransferEmptyState = () =>
  screen.findByText('Choose a Depot and scan to open a manual transfer card.', {}, uiWait)

describe('Transfer workflow', () => {
  it('opens selected Depots with Scan and submits accepted candidates for manual transfer', async () => {
    const fetchMock = mockApi()
    renderApp('/transfer')

    expect(await findManualTransferEmptyState()).toBeInTheDocument()
    const scan = await screen.findByRole('button', { name: 'Scan' }, uiWait)
    expect(scan).toBeDisabled()
    await chooseComboboxOption('Predefined Depots', 'movies-depot')
    await waitFor(() => expect(scan).not.toBeDisabled())
    fireEvent.click(scan)
    fireEvent.click(await screen.findByRole('button', { name: 'Expand movies-depot' }))
    expect((await screen.findAllByText('Avatar (2009) {tmdb-19995}')).length).toBeGreaterThan(0)
    expect(getFirstByRole('switch', { name: 'Accepted Avatar (2009) {tmdb-19995}; click to ignore' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Transfer' }))

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url, init]) => {
          const body = String(init?.body ?? '')
          return String(url).includes('/api/transfer/jobs')
            && init?.method === 'POST'
            && body.includes('"depot_id":"movies-depot"')
            && body.includes('"candidate_ids":["depot-candidate-folder-1","depot-candidate-file-1"]')
        }),
      ).toBe(true)
    })
  })

  it('renders Depot candidates on Transfer and submits dialog operations', async () => {
    const fetchMock = mockApi()
    renderApp('/transfer')

    expect(await findManualTransferEmptyState()).toBeInTheDocument()
    const scan = await screen.findByRole('button', { name: 'Scan' }, uiWait)
    await chooseComboboxOption('Predefined Depots', 'movies-depot')
    await waitFor(() => expect(scan).not.toBeDisabled())
    fireEvent.click(scan)
    fireEvent.click(await screen.findByRole('button', { name: 'Expand movies-depot' }))
    fireEvent.click(await findFirstByRole('button', { name: 'Expand Avatar (2009) {tmdb-19995}' }))
    expect((await screen.findAllByText('Avatar (2009).mkv')).length).toBeGreaterThan(0)

    fireEvent.click(getFirstByRole('button', { name: 'Details Avatar (2009) {tmdb-19995}' }))
    const candidateDialog = await screen.findByRole('dialog', { name: 'Depot candidate' })
    fireEvent.change(within(candidateDialog).getByLabelText('Name'), { target: { value: 'Avatar Fixed' } })
    fireEvent.click(within(candidateDialog).getByRole('button', { name: 'Rename' }))

    fireEvent.click(await findFirstByRole('button', { name: 'Details Avatar (2009).mkv' }))
    const fileDialog = await screen.findByRole('dialog', { name: 'Depot file' })
    fireEvent.click(within(fileDialog).getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/depots/movies-depot/candidates/depot-candidate-folder-1/rename'),
        expect.objectContaining({ method: 'PUT', body: expect.stringContaining('"new_name":"Avatar Fixed"') }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/depots/movies-depot/candidates/depot-candidate-folder-1/files/depot-file-1'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('renders Depot detail and submits accepted transfer and file send-back operations', async () => {
    const fetchMock = mockApi()
    renderApp('/transfer')

    expect(await screen.findByRole('heading', { name: 'Transfer' })).toBeInTheDocument()
    expect(await findManualTransferEmptyState()).toBeInTheDocument()
    const scan = await screen.findByRole('button', { name: 'Scan' }, uiWait)
    await chooseComboboxOption('Predefined Depots', 'movies-depot')
    await waitFor(() => expect(scan).not.toBeDisabled())
    fireEvent.click(scan)
    fireEvent.click(await screen.findByRole('button', { name: 'Expand movies-depot' }))
    expect((await screen.findAllByText('Avatar (2009) {tmdb-19995}')).length).toBeGreaterThan(0)
    fireEvent.click(await findFirstByRole('button', { name: 'Expand Avatar (2009) {tmdb-19995}' }))
    expect(getFirstByRole('switch', { name: 'Selected Avatar.nfo; inherited from candidate' })).toBeDisabled()

    expect(screen.queryByRole('button', { name: 'Transfer Avatar (2009) {tmdb-19995}' })).not.toBeInTheDocument()
    fireEvent.click(getFirstByRole('button', { name: 'Send back Avatar.nfo' }))
    const sendBackHere = await screen.findByRole('button', { name: 'Send back here' })
    await waitFor(() => expect(sendBackHere).not.toBeDisabled())
    fireEvent.click(sendBackHere)

    fireEvent.click(getFirstByRole('switch', { name: 'Accepted Loose.mkv; click to ignore' }))
    fireEvent.click(screen.getByRole('button', { name: /^Transfer$/ }))

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([url, init]) => {
          const body = String(init?.body ?? '')
          return String(url).includes('/api/transfer/jobs')
            && init?.method === 'POST'
            && body.includes('"depot_id":"movies-depot"')
            && body.includes('"candidate_ids":["depot-candidate-folder-1"]')
        }),
      ).toBe(true)
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/depots/movies-depot/return'),
        expect.objectContaining({ method: 'POST', body: expect.stringContaining('"relative_paths":["Avatar (2009) {tmdb-19995}/Avatar.nfo"]') }),
      )
    })
  })

  it('cancels active Transfer jobs from the Transfer card', async () => {
    const fetchMock = mockApi({ transferJobStatus: 'running' })
    renderApp('/transfer')

    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    fireEvent.click(cancel)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/transfer/jobs/job-running/cancel'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('shows failed Transfer jobs', async () => {
    mockApi({ transferJobStatus: 'failed', activityEntries: [transferExceptionActivity()] })
    renderApp('/dashboard')

    expect((await screen.findAllByText('Failed')).length).toBeGreaterThan(0)
  })
})
