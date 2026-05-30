import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { chooseTab, mockApi, renderApp, resetAppTest } from './appHarness'

beforeEach(resetAppTest)

describe('Settings workflow', () => {
  it('runs Settings admin maintenance actions', async () => {
    const fetchMock = mockApi()
    renderApp('/settings')

    await chooseTab('Maintenance')
    fireEvent.click(await screen.findByRole('button', { name: 'Clear TMDB cache' }))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Clear TMDB cache' })).getByRole('button', { name: 'Clear TMDB cache' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Prune Activity and Transfer history' }))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Prune operation history' })).getByRole('button', { name: 'Prune Activity and Transfer history' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/cache/tmdb/clear'),
        expect.objectContaining({ method: 'POST' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/activity/prune'),
        expect.objectContaining({ method: 'POST' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/transfer/prune'),
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('downloads and restores Settings config backups with warning copy', async () => {
    const fetchMock = mockApi()
    const { container } = renderApp('/settings')

    await chooseTab('Maintenance')
    expect(await screen.findByText(/Restore Origins, Depots, rules, providers, and runtime settings from a YAML snapshot/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Backup config' }))
    const input = container.querySelector('input[type="file"]')
    expect(input).toBeTruthy()
    const file = new File(['format: omedia-config-backup\nversion: 1\n'], 'backup.yaml', { type: 'application/x-yaml' })
    fireEvent.change(input!, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Restore config' }))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Restore config' })).getByRole('button', { name: 'Restore config' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/backup'),
        expect.objectContaining({ method: 'GET' }),
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/restore'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('omedia-config-backup'),
        }),
      )
    })
  })
})
