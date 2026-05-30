import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, renderApp, resetAppTest, transferActivity } from './appHarness'

describe('activity workflow', () => {
  beforeEach(() => {
    resetAppTest()
  })

  it('keeps activity rows visible when refreshing the current page', async () => {
    mockApi({
      activityEntries: [
        transferActivity('activity-transfer-complete', 'succeeded', 'moved=1 skipped=0 failed=0 timed_out=0'),
      ],
    })
    renderApp('/activity')

    expect(await screen.findByText('Manual transfer')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    expect(screen.getByText('Manual transfer')).toBeInTheDocument()
  })
})
