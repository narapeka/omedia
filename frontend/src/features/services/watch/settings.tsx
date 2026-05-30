import { Check, FolderOpen, Info } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { DirectoryPickerDialog } from '@/components/filesystem/DirectoryPickerDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { notifyError, notifySuccess } from '@/lib/notifications'
import { useWatchActions, useWatchRuntimeSettings, useWatchSettings } from '../api'

export function WatchSettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const watchSettings = useWatchSettings()
  const runtime = useWatchRuntimeSettings()
  const actions = useWatchActions()
  const [path, setPath] = useState('')
  const [pollInterval, setPollInterval] = useState('')
  const [stabilityDebounce, setStabilityDebounce] = useState('')
  const [message, setMessage] = useState('')
  const [directoryPickerOpen, setDirectoryPickerOpen] = useState(false)
  const saving = actions.saveWatchSettings.isPending || actions.saveWatchRuntimeSettings.isPending

  useEffect(() => {
    if (!watchSettings.data) return
    setPath(watchSettings.data.path)
  }, [watchSettings.data])

  useEffect(() => {
    if (!runtime.data) return
    setPollInterval(String(runtime.data.poll_interval_seconds))
    setStabilityDebounce(String(runtime.data.stability_debounce_seconds))
  }, [runtime.data])

  useEffect(() => {
    if (open) return
    setMessage('')
    setDirectoryPickerOpen(false)
  }, [open])

  const save = async () => {
    setMessage('')
    const trimmedPath = path.trim()
    const poll = parsePositiveSeconds(pollInterval)
    const debounce = parsePositiveSeconds(stabilityDebounce)
    if (!trimmedPath) {
      setMessage(t('watchRootRequired'))
      return
    }
    if (poll === null || debounce === null) {
      setMessage(t('watchTimingRequired'))
      return
    }
    const rootChanged = normalizePath(trimmedPath) !== normalizePath(watchSettings.data?.path ?? '')
    try {
      await actions.saveWatchSettings.mutateAsync({
        id: watchSettings.data?.id ?? 'main',
        path: trimmedPath,
        enabled: rootChanged ? false : watchSettings.data?.enabled ?? false,
      })
      await actions.saveWatchRuntimeSettings.mutateAsync({ poll_interval_seconds: poll, stability_debounce_seconds: debounce })
      notifySuccess(t('watchSettingsSaved'))
      onOpenChange(false)
    } catch (error) {
      notifyError(error, t('requestFailed'))
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('watchSettings')}</DialogTitle>
            <DialogDescription>{t('watchSettingsDescription')}</DialogDescription>
          </DialogHeader>

          <AsyncFrame loading={watchSettings.isLoading || runtime.isLoading} error={watchSettings.error || runtime.error}>
            <FieldGroup>
              <Alert className="border-amber-500/30 bg-amber-500/10 text-amber-950 dark:text-amber-100">
                <Info />
                <AlertDescription className="text-amber-950/90 dark:text-amber-100/90">
                  {t('watchRootWarning')}
                </AlertDescription>
              </Alert>

              <Field>
                <FieldLabel htmlFor="watch-root-path">{t('watchRootPath')}</FieldLabel>
                <div className="flex h-8 min-w-0 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
                  <Input
                    id="watch-root-path"
                    className="h-full min-w-0 flex-1 rounded-none border-0 bg-transparent px-3 focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent"
                    value={path}
                    onChange={(event) => {
                      setPath(event.target.value)
                      setMessage('')
                    }}
                  />
                  <Button
                    type="button"
                    className="h-full w-20 rounded-none border-y-0 border-l border-r-0 border-input bg-transparent px-3 hover:bg-muted/70 focus-visible:ring-0"
                    variant="ghost"
                    onClick={() => setDirectoryPickerOpen(true)}
                  >
                    <FolderOpen data-icon="inline-start" />
                    {t('select')}
                  </Button>
                </div>
              </Field>

              <div className="grid gap-4 md:grid-cols-2">
                <NumberField
                  label={t('pollIntervalSeconds')}
                  value={pollInterval}
                  onChange={(value) => {
                    setPollInterval(value)
                    setMessage('')
                  }}
                />
                <NumberField
                  label={t('stabilityDebounceSeconds')}
                  value={stabilityDebounce}
                  onChange={(value) => {
                    setStabilityDebounce(value)
                    setMessage('')
                  }}
                />
              </div>

              {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
            </FieldGroup>
          </AsyncFrame>

          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('cancel')}
            </Button>
            <Button onClick={save} disabled={saving || watchSettings.isLoading || runtime.isLoading}>
              <Check data-icon="inline-start" />
              {t('saveSettings')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DirectoryPickerDialog
        open={directoryPickerOpen}
        title={t('chooseWatchRoot')}
        description={t('browseWatchRoot')}
        initialPath={path}
        confirmLabel={t('useAsWatchRoot')}
        onOpenChange={setDirectoryPickerOpen}
        onSelect={(selectedPath) => {
          setPath(selectedPath)
          setMessage('')
        }}
      />
    </>
  )
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input id={id} type="number" min="1" step="1" value={value} onChange={(event) => onChange(event.target.value)} />
    </Field>
  )
}

function parsePositiveSeconds(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
}
