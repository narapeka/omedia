import { useState } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { ConfirmDialog, type ConfirmDialogState } from '@/components/common/ConfirmDialog'
import { notifyError } from '@/lib/notifications'
import { useMaintenanceActions } from '../api'
import { BackupRestoreCard, downloadYaml } from './backup'
import { PruneOperationsCard } from './prune'

export function MaintenancePanel() {
  const { t } = useI18n()
  const actions = useMaintenanceActions()
  const [message, setMessage] = useState('')
  const [restoreFile, setRestoreFile] = useState<File | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmDialogState | null>(null)
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  const clearTmdbCache = async () => {
    try {
      const result = await actions.clearTmdbCache.mutateAsync()
      setMessage(t('clearTmdbCacheResult', { count: result.deleted_entries }))
    } catch (error) {
      onActionError(error)
    }
  }

  const pruneOperationHistory = async () => {
    try {
      const result = await actions.pruneOperationHistory.mutateAsync(undefined)
      setMessage(t('pruneHistoryResult', { activityCount: result.activity.deleted_events, transferCount: result.transfer.deleted_jobs }))
    } catch (error) {
      onActionError(error)
    }
  }

  const restoreConfig = async () => {
    if (!restoreFile) return
    try {
      const content = await restoreFile.text()
      const result = await actions.restoreConfig.mutateAsync(content)
      setMessage(
        t('restoreResult', {
          origins: result.restored.origins,
          depots: result.restored.depots,
          organizeRules: result.restored.organize_rules,
          transferRules: result.restored.transfer_rules,
        }),
      )
    } catch (error) {
      onActionError(error)
    }
  }

  const backupConfig = async () => {
    try {
      const content = await actions.backupConfig.mutateAsync()
      downloadYaml(content, 'omedia-config-backup.yaml')
      setMessage(t('backupDownloaded'))
    } catch (error) {
      onActionError(error)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <PruneOperationsCard
          clearing={actions.clearTmdbCache.isPending}
          pruning={actions.pruneOperationHistory.isPending}
          onClearTmdbCache={() => {
            setConfirmAction({
              title: t('clearTmdbCache'),
              description: t('clearTmdbCacheConfirm'),
              confirmLabel: t('clearTmdbCache'),
              destructive: true,
              onConfirm: clearTmdbCache,
            })
          }}
          onPruneHistory={() => {
            setConfirmAction({
              title: t('pruneOperationHistory'),
              description: t('pruneHistoryConfirm'),
              confirmLabel: t('pruneHistoryAction'),
              destructive: true,
              onConfirm: pruneOperationHistory,
            })
          }}
        />
        <BackupRestoreCard
          restoreFile={restoreFile}
          backingUp={actions.backupConfig.isPending}
          restoring={actions.restoreConfig.isPending}
          onRestoreFileChange={setRestoreFile}
          onBackup={() => void backupConfig()}
          onRestore={() => {
            if (!restoreFile) return
            setConfirmAction({
              title: t('restoreConfig'),
              description: t('restoreConfirm'),
              confirmLabel: t('restoreConfig'),
              destructive: true,
              onConfirm: restoreConfig,
            })
          }}
        />
      </div>
      {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
      <ConfirmDialog state={confirmAction} onOpenChange={(open) => { if (!open) setConfirmAction(null) }} />
    </div>
  )
}

