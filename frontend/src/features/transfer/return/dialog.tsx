import { DirectoryPickerDialog } from '@/components/filesystem/DirectoryPickerDialog'

export function ReturnDialog({
  open,
  title,
  initialPath,
  confirmLabel,
  onOpenChange,
  onSelect,
}: {
  open: boolean
  title: string
  initialPath: string
  confirmLabel: string
  onOpenChange: (open: boolean) => void
  onSelect: (path: string) => void
}) {
  return (
    <DirectoryPickerDialog
      open={open}
      title={title}
      description={null}
      initialPath={initialPath}
      confirmLabel={confirmLabel}
      onOpenChange={onOpenChange}
      onSelect={onSelect}
    />
  )
}
