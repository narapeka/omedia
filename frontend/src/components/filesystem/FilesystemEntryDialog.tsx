import { useEffect, useMemo, useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { knownDisplayLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'

export type FilesystemEntryKind = 'file' | 'folder'

export type FilesystemEntryDetail = {
  name: string
  path: string
  exists?: boolean | null
  fileType?: string | null
  status?: string | null
  sizeBytes?: number | null
  fileCount?: number | null
  createdTime?: number | null
  modifiedTime?: number | null
  blockedReason?: string | null
}

export function FilesystemEntryDialog({
  open,
  title,
  detail,
  loading,
  error,
  renamePending = false,
  deletePending = false,
  onRename,
  onDelete,
  onOpenChange,
}: {
  open: boolean
  title: string
  entryKind: FilesystemEntryKind
  detail: FilesystemEntryDetail | null
  loading: boolean
  error: unknown
  renamePending?: boolean
  deletePending?: boolean
  onRename?: (newName: string) => void
  onDelete?: () => void
  onOpenChange: (open: boolean) => void
}) {
  const { locale, t } = useI18n()
  const [newName, setNewName] = useState('')
  const actionDisabled = !detail || loading || renamePending || deletePending
  const renameDisabled = actionDisabled || !onRename || !newName.trim() || newName.trim() === detail?.name
  const showNameActions = Boolean(onRename || onDelete)
  const facts = useMemo(() => detailFacts(detail, t, locale), [detail, locale, t])

  useEffect(() => {
    if (!open) {
      setNewName('')
      return
    }
    setNewName(detail?.name ?? '')
  }, [open, detail?.name])

  const submitRename = () => {
    const name = newName.trim()
    if (!name || !onRename || renameDisabled) return
    onRename(name)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">{detail?.path ?? t('loadingDetails')}</DialogDescription>
        </DialogHeader>

        {loading ? <div className="py-6 text-sm text-muted-foreground">{t('loadingDetails')}</div> : null}
        {error ? <div className="text-sm text-destructive">{errorMessage(error)}</div> : null}

        {detail ? (
          <div className="flex flex-col gap-4">
            <PathBlock path={detail.path} />

            {facts.length ? (
              <div className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
                {facts.map((fact) => (
                  <DetailFact key={fact.label} label={fact.label} value={fact.value} />
                ))}
              </div>
            ) : null}

            {showNameActions ? (
              <>
                <Separator />

                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="filesystem-entry-new-name">{t('name')}</FieldLabel>
                    <Input
                      id="filesystem-entry-new-name"
                      value={newName}
                      onChange={(event) => setNewName(event.target.value)}
                      disabled={actionDisabled || !onRename}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') submitRename()
                      }}
                    />
                    <div className="flex justify-end gap-2">
                      {onRename ? (
                        <Button onClick={submitRename} disabled={renameDisabled}>
                          <Pencil data-icon="inline-start" />
                          {renamePending ? t('renaming') : t('rename')}
                        </Button>
                      ) : null}
                      {onDelete ? (
                        <Button variant="danger" onClick={onDelete} disabled={actionDisabled}>
                          <Trash2 data-icon="inline-start" />
                          {deletePending ? t('deleting') : t('delete')}
                        </Button>
                      ) : null}
                    </div>
                  </Field>
                </FieldGroup>
              </>
            ) : null}
          </div>
        ) : null}

      </DialogContent>
    </Dialog>
  )
}

function PathBlock({ path }: { path: string }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-muted-foreground">{t('path')}</div>
      <div className="rounded-md border bg-muted/30 px-3 py-2 font-mono text-sm break-all text-foreground">
        {path}
      </div>
    </div>
  )
}

function DetailFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 grid-cols-[6rem_minmax(0,1fr)] gap-2">
      <div className="font-medium text-muted-foreground">{label}</div>
      <div className="min-w-0 break-all">{value}</div>
    </div>
  )
}

function detailFacts(detail: FilesystemEntryDetail | null, t: ReturnType<typeof useI18n>['t'], locale: string) {
  if (!detail) return []
  return [
    detail.status && detail.status !== 'active' ? { label: t('status'), value: knownDisplayLabel(t, detail.status) } : null,
    detail.fileType ? { label: t('type'), value: knownDisplayLabel(t, detail.fileType) } : null,
    detail.sizeBytes !== undefined && detail.sizeBytes !== null ? { label: t('size'), value: formatBytes(detail.sizeBytes) } : null,
    detail.createdTime ? { label: t('created'), value: formatUnixSeconds(detail.createdTime, locale) } : null,
    detail.modifiedTime ? { label: t('modified'), value: formatUnixSeconds(detail.modifiedTime, locale) } : null,
    detail.fileCount !== undefined && detail.fileCount !== null ? { label: t('files'), value: String(detail.fileCount) } : null,
    detail.blockedReason ? { label: t('blocked'), value: detail.blockedReason } : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>
}

function formatBytes(value: number | null | undefined) {
  if (value === null || value === undefined) return '-'
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let current = value / 1024
  let unit = 0
  while (current >= 1024 && unit < units.length - 1) {
    current /= 1024
    unit += 1
  }
  return `${current.toFixed(current >= 10 ? 1 : 2)} ${units[unit]}`
}

function formatUnixSeconds(value: number | null | undefined, locale: string) {
  if (!value) return '-'
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value * 1000))
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (error && typeof error === 'object') {
    const nested = (error as { error?: { message?: unknown }; message?: unknown }).error?.message
    if (typeof nested === 'string') return nested
    const message = (error as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  return String(error)
}
