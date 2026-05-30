import { fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, mockMatchMedia, renderApp, resetAppTest, transferActivity } from './appHarness'

beforeEach(() => {
  resetAppTest()
  mockMatchMedia({ '(min-width: 1536px)': true })
})

describe('Dashboard workflow', () => {
  it('shows backend Transfer job state on the Dashboard', async () => {
    mockApi({
      activityEntries: [
        transferActivity('activity-transfer-complete', 'succeeded', 'Transfer completed'),
        {
          ...transferActivity('activity-transfer-job', 'queued', 'Transfer queued for movie Depot'),
          entity_type: 'transfer_job',
          entity_source: null,
          entity_target: null,
        },
      ],
    })
    renderApp('/dashboard')

    expect(await screen.findByRole('link', { name: 'Open Configured Origins' })).toHaveTextContent('3')
    expect(screen.getByRole('link', { name: 'Open Configured Depots' })).toHaveTextContent('1')
    expect(screen.getByRole('link', { name: 'Open Configured Rules' })).toHaveTextContent('0')
    expect(screen.getByRole('link', { name: 'Open Watched Folders' })).toHaveTextContent('1')
    expect(screen.getByRole('link', { name: 'Open Scheduled Transfers' })).toHaveTextContent('0')
    expect(await screen.findByText('Pipelines Overview')).toBeInTheDocument()
    expect(screen.queryByText('Depot health')).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Organize type' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand pipeline table' }))
    expect(await screen.findByRole('columnheader', { name: 'Organize type' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Transfer type' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse pipeline table' }))
    expect(screen.queryByRole('columnheader', { name: 'Organize type' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand pipeline table' }))
    expect(await screen.findByRole('columnheader', { name: 'Organize type' })).toBeInTheDocument()
    expect(await screen.findByText('Organize Overview')).toBeInTheDocument()
    expect(await screen.findByText('Transfer Overview')).toBeInTheDocument()
    expect(screen.queryByText('Organize attention')).not.toBeInTheDocument()
    expect(screen.queryByText('Transfer queue')).not.toBeInTheDocument()
    expect(screen.queryByText('Recent receipts')).not.toBeInTheDocument()
    expect(screen.queryByText('Recent transfer exceptions')).not.toBeInTheDocument()
    expect(screen.queryByText('Overwrite blocked')).not.toBeInTheDocument()
    expect(screen.queryByText('No recent organize activity.')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand organize activity table' }))
    expect(await screen.findByText('No recent organize activity.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse organize activity table' }))
    expect(screen.getByText('Organized')).toBeInTheDocument()
    expect(screen.getByText('Unmatched')).toBeInTheDocument()
    expect(screen.queryByText('No recent organize activity.')).not.toBeInTheDocument()

    const transferTable = within(document.getElementById('transfer-overview-activity-table') as HTMLElement)
    expect(await transferTable.findByRole('columnheader', { name: 'Depot' })).toBeInTheDocument()
    expect(transferTable.getByRole('columnheader', { name: 'Library' })).toBeInTheDocument()
    expect((await screen.findAllByText('Completed')).length).toBeGreaterThan(0)
    expect(screen.getByText('D:/media/depot/movies/Avatar.mkv')).toBeInTheDocument()
    expect(screen.getByText('D:/media/library/movies/Avatar.mkv')).toBeInTheDocument()
    expect(transferTable.queryByText('Queued')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse transfer activity table' }))
    expect(screen.queryByText('D:/media/library/movies/Avatar.mkv')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand transfer activity table' }))
    expect(await screen.findByText('D:/media/library/movies/Avatar.mkv')).toBeInTheDocument()
  })

  it('summarizes scheduled transfers on the Dashboard overview cards', async () => {
    mockApi({ includeScheduledDepot: true, scheduledTransferJobStatus: 'queued' })
    renderApp('/dashboard')

    expect(await screen.findByText('Transfer Overview')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Scheduled Transfers' })).toHaveTextContent('1')
    expect(screen.queryByText(/enabled,/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Scheduled Transfers' })).toHaveTextContent(/queued\s*1/)
    const transferTable = within(document.getElementById('transfer-overview-activity-table') as HTMLElement)
    expect(transferTable.getByText('No recent transfer activity.')).toBeInTheDocument()
    expect(transferTable.queryByText('tv-depot')).not.toBeInTheDocument()
    expect(transferTable.queryByText('Waiting')).not.toBeInTheDocument()
    expect(screen.queryByText('Daily at 04:00')).not.toBeInTheDocument()
  })

  it('does not mix active Transfer jobs into recent Transfer activity', async () => {
    mockApi({ transferJobStatus: 'running' })
    renderApp('/dashboard')

    expect(await screen.findByText('Transfer Overview')).toBeInTheDocument()

    const transferTable = within(document.getElementById('transfer-overview-activity-table') as HTMLElement)
    expect(transferTable.getByText('No recent transfer activity.')).toBeInTheDocument()
    expect(transferTable.queryByText('Moving files')).not.toBeInTheDocument()
  })
})
