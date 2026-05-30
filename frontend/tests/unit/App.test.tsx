import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, mockMatchMedia, renderApp, resetAppTest } from './appHarness'

beforeEach(resetAppTest)

describe('OMEDIA app smoke', () => {
  it('redirects the root route to Dashboard', async () => {
    mockApi()
    renderApp('/')

    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('presents workflow navigation without depot as a primary item', async () => {
    mockApi()
    renderApp('/organize')

    expect(await screen.findByRole('link', { name: 'Organize' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Transfer' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Services' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Activity' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'depot' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Rules' })).not.toBeInTheDocument()
    expect(await screen.findByText('manual-movies')).toBeInTheDocument()
  })

  it('switches locale from the Sidebar language control and keeps the dark theme', async () => {
    mockApi()
    localStorage.setItem('omedia.theme', 'light')
    renderApp()

    expect(screen.queryByRole('button', { name: 'Preferences' })).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Chinese (zh-CN)' }))

    await waitFor(() => expect(localStorage.getItem('omedia.locale')).toBe('zh-CN'))
    expect(document.documentElement.lang).toBe('zh-CN')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('omedia.theme')).toBeNull()
  })

  it('uses a hamburger drawer for mobile navigation', async () => {
    mockApi()
    mockMatchMedia({ '(max-width: 760px)': true })
    renderApp('/dashboard')

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open Workflows' }))
    const drawer = await screen.findByRole('dialog', { name: 'Workflows' })
    fireEvent.click(within(drawer).getByRole('link', { name: 'Settings' }))

    await waitFor(() => expect(window.location.pathname).toBe('/settings'))
    expect(screen.queryByRole('dialog', { name: 'Workflows' })).not.toBeInTheDocument()
  })
})
