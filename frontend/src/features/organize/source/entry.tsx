import { useEffect, useMemo } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { SourceCandidateDetail, SourceFileDetail, SourceFile, SourceCandidate } from '@/api/types'
import { FilesystemEntryDialog, type FilesystemEntryDetail } from '@/components/filesystem/FilesystemEntryDialog'
import { notifyError } from '@/lib/notifications'
import { useSessionActions } from '../api'

export type OrganizeSourceEntryTarget =
  | { type: 'candidate'; sourceCandidate: SourceCandidate }
  | { type: 'file'; sourceCandidate: SourceCandidate; sourceFile: SourceFile }

export function OrganizeSourceEntryDialog({
  open,
  onOpenChange,
  sessionId,
  target,
  canRename,
  canDelete,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId: string
  target: OrganizeSourceEntryTarget | null
  canRename: boolean
  canDelete: boolean
}) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const isFileTarget = target?.type === 'file'
  const sourceCandidate = target?.sourceCandidate ?? null
  const sourceFile = isFileTarget ? target.sourceFile : null
  const candidateDetail = isFileTarget ? undefined : actions.getSourceCandidateDetail.data
  const fileDetail = isFileTarget ? actions.getSourceFileDetail.data : undefined
  const entryKind = sourceFile || sourceCandidate?.kind === 'movie_file' ? 'file' : 'folder'
  const canRenameSource = canRename && sourceCandidate?.status === 'active' && (!sourceFile || sourceFile.status === 'active')
  const canDeleteSource = canDelete && sourceCandidate?.status === 'active' && (!sourceFile || sourceFile.status === 'active')
  const renameMutation = sourceFile ? actions.renameSourceFile : actions.renameSourceCandidate
  const deleteMutation = sourceFile ? actions.deleteSourceFile : actions.deleteSourceCandidate
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  useEffect(() => {
    actions.getSourceCandidateDetail.reset()
    actions.getSourceFileDetail.reset()
    if (!open || !sourceCandidate) return
    if (sourceFile) {
      actions.getSourceFileDetail.mutate({
        sessionId,
        candidateId: sourceCandidate.id,
        fileId: sourceFile.id,
      })
      return
    }
    actions.getSourceCandidateDetail.mutate({
      sessionId,
      candidateId: sourceCandidate.id,
    })
  }, [open, sessionId, sourceCandidate?.id, sourceFile?.id])

  const detail = useMemo(
    () => buildDetail(sourceCandidate, sourceFile, candidateDetail, fileDetail),
    [candidateDetail, fileDetail, sourceCandidate, sourceFile],
  )

  const rename = (newName: string) => {
    if (!target || !canRenameSource) return
    if (target.type === 'file') {
      actions.renameSourceFile.mutate(
        { sessionId, candidateId: target.sourceCandidate.id, fileId: target.sourceFile.id, data: { new_name: newName } },
        { onSuccess: () => onOpenChange(false), onError: onActionError },
      )
      return
    }
    actions.renameSourceCandidate.mutate(
      { sessionId, candidateId: target.sourceCandidate.id, data: { new_name: newName } },
      { onSuccess: () => onOpenChange(false), onError: onActionError },
    )
  }

  const remove = () => {
    if (!target || !canDeleteSource) return
    if (target.type === 'file') {
      actions.deleteSourceFile.mutate(
        { sessionId, candidateId: target.sourceCandidate.id, fileId: target.sourceFile.id },
        { onSuccess: () => onOpenChange(false), onError: onActionError },
      )
      return
    }
    actions.deleteSourceCandidate.mutate(
      { sessionId, candidateId: target.sourceCandidate.id },
      { onSuccess: () => onOpenChange(false), onError: onActionError },
    )
  }

  return (
    <FilesystemEntryDialog
      open={open}
      onOpenChange={onOpenChange}
      title={sourceFile ? t('sourceFile') : t('sourceCandidate')}
      entryKind={entryKind}
      detail={detail}
      loading={actions.getSourceCandidateDetail.isPending || actions.getSourceFileDetail.isPending}
      error={actions.getSourceCandidateDetail.error || actions.getSourceFileDetail.error}
      renamePending={renameMutation.isPending}
      deletePending={deleteMutation.isPending}
      onRename={canRenameSource ? rename : undefined}
      onDelete={canDeleteSource ? remove : undefined}
    />
  )
}

function buildDetail(
  sourceCandidate: SourceCandidate | null,
  sourceFile: SourceFile | null,
  candidateDetail: SourceCandidateDetail | undefined,
  fileDetail: SourceFileDetail | undefined,
): FilesystemEntryDetail | null {
  if (!sourceCandidate) return null
  if (sourceFile) {
    return {
      name: basename(sourceFile.relative_path),
      path: fileDetail?.path ?? sourceFile.path,
      exists: fileDetail?.exists,
      fileType: fileDetail?.file_type,
      status: sourceFile.status,
      sizeBytes: fileDetail?.size_bytes ?? sourceFile.size_bytes,
      createdTime: fileDetail?.created_time,
      modifiedTime: fileDetail?.modified_time ?? sourceFile.modified_time,
      blockedReason: fileDetail?.blocked_reason,
    }
  }
  const inspected = candidateDetail?.detail
  const candidate = candidateDetail?.candidate ?? sourceCandidate
  return {
    name: candidate.kind === 'movie_file' ? basename(candidate.source_path) : candidate.display_name,
    path: inspected?.path ?? candidate.source_path,
    exists: inspected?.exists,
    fileType: inspected?.file_type ?? (candidate.kind === 'movie_file' ? 'file' : 'directory'),
    status: candidate.status,
    sizeBytes: candidate.active_total_size ?? candidate.total_size,
    fileCount: candidate.active_file_count ?? candidate.file_count,
    createdTime: inspected?.created_time,
    modifiedTime: candidate.modified_time,
    blockedReason: inspected?.blocked_reason,
  }
}

function basename(path: string) {
  const parts = path.replace(/\\/g, '/').split('/')
  return parts[parts.length - 1] || path
}

