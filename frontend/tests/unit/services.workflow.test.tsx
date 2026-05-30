import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { chooseSelectOption, mockApi, mockMatchMedia, renderApp, resetAppTest } from './appHarness'

beforeEach(() => {
  resetAppTest()
  mockMatchMedia({ '(min-width: 1536px)': true })
})

describe('Services workflow', () => {
  it('edits and clears Watch child Origin configuration inline', async () => {
    const fetchMock = mockApi()
    renderApp('/services')

    expect(await screen.findByText('watching')).toBeInTheDocument()
    const targetDepot = await screen.findByRole('combobox', { name: 'auto-movies Target Depot' })
    expect(targetDepot).toHaveTextContent('movies-depot')
    expect(targetDepot).not.toHaveTextContent('(movie)')
    expect(screen.getByRole('combobox', { name: 'auto-movies Organize rule' })).toHaveTextContent('None')
    expect(screen.getByRole('combobox', { name: 'dropbox Media type' })).toHaveTextContent('-')
    const unconfiguredTargetDepot = screen.getByRole('combobox', { name: 'dropbox Target Depot' })
    expect(unconfiguredTargetDepot).toHaveTextContent('-')
    expect(unconfiguredTargetDepot).toBeDisabled()
    const unconfiguredRule = screen.getByRole('combobox', { name: 'dropbox Organize rule' })
    expect(unconfiguredRule).toHaveTextContent('-')
    expect(unconfiguredRule).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove dropbox' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Edit dropbox' }))
    await chooseSelectOption('dropbox Media type', 'Movie')
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'dropbox Organize rule' })).toHaveTextContent('None'))
    expect(screen.getByRole('combobox', { name: 'dropbox Organize rule' })).not.toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'dropbox Target Depot' })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save dropbox' })).toBeDisabled()

    await chooseSelectOption('dropbox Target Depot', 'movies-depot')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save dropbox' })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Save dropbox' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/origins'),
        expect.objectContaining({
          body: expect.stringContaining('"path":"D:/media/incoming/dropbox"'),
          method: 'POST',
        }),
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Remove auto-movies' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/origins/auto-movies'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('shows configured Watch children as configured while Watch is stopped', async () => {
    mockApi({ watchStatusState: 'stopped' })
    renderApp('/services')

    expect(await screen.findByText('configured')).toBeInTheDocument()
    expect(screen.queryByText('watching')).not.toBeInTheDocument()
  })

  it('controls Watch runtime actions', async () => {
    const fetchMock = mockApi()
    renderApp('/services')

    const stop = await screen.findByRole('button', { name: 'Stop' })
    await waitFor(() => expect(stop).not.toBeDisabled())
    fireEvent.click(stop)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/watch/stop'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('closes Watch settings and shows a success toast after saving', async () => {
    const fetchMock = mockApi()
    renderApp('/services')

    fireEvent.click(await screen.findByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('dialog', { name: 'Watch settings' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/watch/settings'),
        expect.objectContaining({ method: 'PUT' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/settings/watch-runtime'),
        expect.objectContaining({ method: 'PUT' }),
      )
    })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Watch settings' })).not.toBeInTheDocument())
    expect(await screen.findByText('Watch settings saved.')).toBeInTheDocument()
  })

  it('edits scheduled transfer plans inline and treats an empty cron as manual', async () => {
    const fetchMock = mockApi({ includeScheduledDepot: true })
    renderApp('/services')

    expect(await screen.findByText('Daily 04:00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove movies-depot' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove tv-depot' })).not.toBeDisabled()
    expect(screen.queryByRole('switch', { name: /Auto transfer/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Edit movies-depot' }))
    const emptySchedule = await screen.findByRole('textbox', { name: 'Transfer cron schedule' })
    expect(emptySchedule).toHaveValue('')
    fireEvent.focus(emptySchedule)
    expect(await screen.findByRole('button', { name: 'Daily' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel movies-depot' }))

    fireEvent.click(screen.getByRole('button', { name: 'Edit tv-depot' }))
    const schedule = await screen.findByRole('textbox', { name: 'Transfer cron schedule' })
    const save = screen.getByRole('button', { name: 'Save tv-depot' })

    fireEvent.change(schedule, { target: { value: 'bad cron' } })
    expect(save).toBeDisabled()
    expect(screen.queryByText('Use a 5-field cron expression.')).not.toBeInTheDocument()

    fireEvent.change(schedule, { target: { value: '' } })
    await waitFor(() => expect(save).not.toBeDisabled())
    fireEvent.click(save)

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).includes('/api/depots/tv-depot') && init?.method === 'PUT',
      )
      expect(putCall).toBeTruthy()
      const body = JSON.parse(String(putCall?.[1]?.body ?? '{}'))
      expect(body.policy.trigger).toBe('manual')
      expect(body.policy.schedule).toBeNull()
    })
  })

  it('clears a scheduled transfer plan from the row action', async () => {
    const fetchMock = mockApi({ includeScheduledDepot: true })
    renderApp('/services')

    fireEvent.click(await screen.findByRole('button', { name: 'Remove tv-depot' }))

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).includes('/api/depots/tv-depot') && init?.method === 'PUT',
      )
      expect(putCall).toBeTruthy()
      const body = JSON.parse(String(putCall?.[1]?.body ?? '{}'))
      expect(body.policy.trigger).toBe('manual')
      expect(body.policy.schedule).toBeNull()
    })
  })
})
