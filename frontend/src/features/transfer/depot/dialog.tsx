import { useEffect, useMemo } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import type {
  FileDetail,
  DepotCandidateActionOutcome,
  DepotCandidateFile,
  DepotCandidate,
} from '@/api/types'
import { FilesystemEntryDialog, type FilesystemEntryDetail } from '@/components/filesystem/FilesystemEntryDialog'
import { notifyError, notifyWarning } from '@/lib/notifications'
import { useDepotCandidateActions } from '@/features/depot/api'
import { depotOutcomeMessage } from './model'

export type DepotFilesystemEntryTarget =
  | { type: 'candidate'; candidate: DepotCandidate }
  | { type: 'file'; candidate: DepotCandidate; file: DepotCandidateFile }

export function DepotFilesystemEntryDialog({
  open,
  onOpenChange,
  depotId,
  target,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  depotId: string
  target: DepotFilesystemEntryTarget | null
}) {
  const { t } = useI18n()
  const actions = useDepotCandidateActions()
  const candidate = target?.candidate ?? null
  const file = target?.type === 'file' ? target.file : null
  const isFileTarget = Boolean(file)
  const candidateDetail = isFileTarget ? null : actions.getDepotCandidateDetail.data
  const fileDetail = isFileTarget ? actions.getDepotCandidateFileDetail.data : null
  const renameMutation = isFileTarget ? actions.renameDepotCandidateFile : actions.renameDepotCandidate
  const deleteMutation = isFileTarget ? actions.deleteDepotCandidateFile : actions.deleteDepotCandidate
  const entryKind = file || candidate?.kind === 'file' ? 'file' : 'folder'
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  useEffect(() => {
    actions.getDepotCandidateDetail.reset()
    actions.getDepotCandidateFileDetail.reset()
    if (!open || !target) return
    if (target.type === 'file') {
      actions.getDepotCandidateFileDetail.mutate({
        depotId,
        candidateId: target.candidate.id,
        fileId: target.file.id,
      })
      return
    }
    actions.getDepotCandidateDetail.mutate({ depotId, candidateId: target.candidate.id })
  }, [open, depotId, target?.type, target?.candidate.id, file?.id])

  const detail = useMemo(
    () => buildDetail(candidate, file, candidateDetail?.detail ?? fileDetail?.detail ?? null),
    [candidate, candidateDetail?.detail, file, fileDetail?.detail],
  )

  const rename = (newName: string) => {
    if (!target) return
    if (target.type === 'file') {
      actions.renameDepotCandidateFile.mutate(
        { depotId, candidateId: target.candidate.id, fileId: target.file.id, data: { new_name: newName } },
        { onSuccess: handleMutationSuccess, onError: onActionError },
      )
      return
    }
    actions.renameDepotCandidate.mutate(
      { depotId, candidateId: target.candidate.id, data: { new_name: newName } },
      { onSuccess: handleMutationSuccess, onError: onActionError },
    )
  }

  const remove = () => {
    if (!target) return
    if (target.type === 'file') {
      actions.deleteDepotCandidateFile.mutate(
        { depotId, candidateId: target.candidate.id, fileId: target.file.id },
        { onSuccess: handleMutationSuccess, onError: onActionError },
      )
      return
    }
    actions.deleteDepotCandidate.mutate(
      { depotId, candidateId: target.candidate.id },
      { onSuccess: handleMutationSuccess, onError: onActionError },
    )
  }

  const handleMutationSuccess = (response: { outcome: DepotCandidateActionOutcome }) => {
    if (response.outcome.status === 'succeeded') {
      onOpenChange(false)
      return
    }
    notifyWarning(depotOutcomeMessage(response.outcome, t))
  }

  return (
    <FilesystemEntryDialog
      open={open}
      onOpenChange={onOpenChange}
      title={file ? t('depotFile') : t('depotCandidate')}
      entryKind={entryKind}
      detail={detail}
      loading={actions.getDepotCandidateDetail.isPending || actions.getDepotCandidateFileDetail.isPending}
      error={actions.getDepotCandidateDetail.error || actions.getDepotCandidateFileDetail.error}
      renamePending={renameMutation.isPending}
      deletePending={deleteMutation.isPending}
      onRename={rename}
      onDelete={remove}
    />
  )
}

function buildDetail(
  candidate: DepotCandidate | null,
  file: DepotCandidateFile | null,
  inspected: FileDetail | null,
): FilesystemEntryDetail | null {
  if (!candidate) return null
  if (file) {
    return {
      name: file.display_name,
      path: inspected?.path ?? file.path,
      exists: inspected?.exists,
      fileType: inspected?.file_type ?? 'file',
      sizeBytes: inspected?.size_bytes ?? file.size_bytes,
      createdTime: inspected?.created_time,
      modifiedTime: inspected?.modified_time ?? file.modified_time,
      blockedReason: inspected?.blocked_reason ?? file.blocked_reason,
    }
  }
  return {
    name: candidate.display_name,
    path: inspected?.path ?? candidate.path,
    exists: inspected?.exists,
    fileType: inspected?.file_type ?? (candidate.kind === 'folder' ? 'directory' : 'file'),
    sizeBytes: candidate.size_bytes,
    fileCount: candidate.file_count,
    createdTime: inspected?.created_time,
    modifiedTime: candidate.modified_time,
    blockedReason: inspected?.blocked_reason ?? candidate.blocked_reason,
  }
}
