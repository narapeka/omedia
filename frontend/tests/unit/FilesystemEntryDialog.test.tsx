import type { ReactElement } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { I18nProvider } from '@/app/providers/I18nProvider'
import { LocaleProvider } from '@/app/providers/LocaleProvider'
import { FilesystemEntryDialog } from '@/components/filesystem/FilesystemEntryDialog'

const detail = {
  name: 'Avatar.mkv',
  path: 'D:/media/manual/movies/Avatar.mkv',
  relativePath: 'Avatar.mkv',
  exists: true,
  fileType: 'regular_file',
  status: 'active',
  classification: 'video',
  sourceLabel: 'Avatar',
  sourceKind: 'movie_file',
  sizeBytes: 4096,
  modifiedTime: 1777675200,
  extra: [{ label: 'Source file ID', value: 'source-file-1' }],
}

describe('FilesystemEntryDialog', () => {
  it('renders details and calls inline rename and delete actions', () => {
    const onRename = vi.fn()
    const onDelete = vi.fn()
    renderDialog(
      <FilesystemEntryDialog
        open
        title="Source file"
        entryKind="file"
        detail={detail}
        loading={false}
        error={null}
        onRename={onRename}
        onDelete={onDelete}
        onOpenChange={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Source file' })
    expect(within(dialog).getAllByText('D:/media/manual/movies/Avatar.mkv')).toHaveLength(2)
    expect(within(dialog).queryByText('Relative path')).not.toBeInTheDocument()
    expect(within(dialog).queryByText('Source')).not.toBeInTheDocument()
    expect(within(dialog).queryByText('Kind')).not.toBeInTheDocument()
    expect(within(dialog).queryByText('Exists')).not.toBeInTheDocument()
    expect(within(dialog).queryByText('Source file ID')).not.toBeInTheDocument()
    expect(within(dialog).getByText('regular file')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('button', { name: 'Close' })).toHaveLength(1)
    expect(within(dialog).getByRole('button', { name: 'Rename' })).toBeDisabled()
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Avatar.2009.mkv' } })
    expect(within(dialog).getByRole('button', { name: 'Rename' })).toBeEnabled()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Rename' }))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))

    expect(onRename).toHaveBeenCalledWith('Avatar.2009.mkv')
    expect(onDelete).toHaveBeenCalled()
  })

  it('shows loading, pending, and error states inside the same dialog', () => {
    renderDialog(
      <FilesystemEntryDialog
        open
        title="Source folder"
        entryKind="folder"
        detail={{ ...detail, name: 'Avatar', path: 'D:/media/manual/movies/Avatar', fileCount: 2, sizeBytes: 8192 }}
        loading
        error={new Error('target exists')}
        renamePending
        deletePending
        onRename={vi.fn()}
        onDelete={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Source folder' })
    expect(within(dialog).getByText('Loading details...')).toBeInTheDocument()
    expect(within(dialog).getByText('target exists')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Renaming...' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: 'Deleting...' })).toBeDisabled()
    expect(within(dialog).queryByRole('dialog', { name: /delete/i })).not.toBeInTheDocument()
  })
})

function renderDialog(ui: ReactElement) {
  localStorage.setItem('omedia.locale', 'en-US')
  return render(
    <LocaleProvider>
      <I18nProvider>{ui}</I18nProvider>
    </LocaleProvider>,
  )
}
