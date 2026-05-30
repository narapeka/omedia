import { File, FileText, Film, Info, RotateCcw } from 'lucide-react'
import type { DepotCandidateFile, DepotCandidate } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { PathArrow } from '@/components/filesystem/PathRoute'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { useIs2xl } from '@/lib/useMediaQuery'
import { DepotCandidateDecisionSwitcher } from './decision'
import { formatDepotBytes } from './model'

export function DepotCandidateInventoryTable({
  candidate,
  inheritedAccepted,
  onFileDetails,
  onFileReturn,
  fileReturnDisabled,
  getTargetPath,
}: {
  candidate: DepotCandidate
  inheritedAccepted?: boolean
  onFileDetails: (file: DepotCandidateFile) => void
  onFileReturn?: (file: DepotCandidateFile) => void
  fileReturnDisabled?: (file: DepotCandidateFile) => boolean
  getTargetPath?: (file: DepotCandidateFile) => string | null
}) {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  const files = candidate.files ?? []
  if (!files.length) {
    return <div className="border-t bg-muted/20 px-4 py-3 text-sm text-muted-foreground">{t('emptyFolder')}</div>
  }

  return (
    <>
      {!is2xl ? (
      <div className="border-t bg-background">
        {files.map((file, index) => {
          const targetPath = getTargetPath?.(file) ?? null
          return (
            <div key={file.id} className="grid gap-2 border-b p-3 last:border-b-0">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <TreeIndentGuide isLast={index === files.length - 1} />
                  <DepotFileIcon file={file} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium" title={file.candidate_relative_path}>
                      {file.candidate_relative_path}
                    </div>
                    {file.blocked_reason ? <div className="mt-1 text-xs text-destructive">{file.blocked_reason}</div> : null}
                  </div>
                </div>
                <Badge className="shrink-0 whitespace-nowrap">{formatDepotBytes(file.size_bytes)}</Badge>
              </div>
              {getTargetPath ? (
                <div className="ml-9 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                  <PathArrow className="size-3.5" />
                  <span className="truncate" title={targetPath ?? undefined}>
                    {targetPath ?? t('noTransferTarget')}
                  </span>
                </div>
              ) : null}
              <div className="ml-9 flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap gap-2">
                  {onFileReturn ? (
                    <Button
                      className="whitespace-nowrap"
                      size="sm"
                      variant="outline"
                      onClick={() => onFileReturn(file)}
                      disabled={fileReturnDisabled?.(file) || Boolean(file.blocked_reason)}
                      aria-label={t('sendBackLabel', { label: file.display_name })}
                    >
                      <RotateCcw data-icon="inline-start" />
                      {t('sendBack')}
                    </Button>
                  ) : null}
                  <Button className="whitespace-nowrap" size="sm" variant="outline" onClick={() => onFileDetails(file)} aria-label={t('detailsLabel', { label: file.display_name })}>
                    <Info data-icon="inline-start" />
                    {t('details')}
                  </Button>
                </div>
                {inheritedAccepted === undefined ? null : (
                  <DepotCandidateDecisionSwitcher accepted={inheritedAccepted} inherited target={file.display_name} />
                )}
              </div>
            </div>
          )
        })}
      </div>
      ) : null}
      {is2xl ? (
      <div className="overflow-x-auto border-t bg-background">
        <Table className="min-w-[980px] table-fixed">
        <colgroup>
          <col style={{ width: getTargetPath ? '50%' : '62%' }} />
          <col style={{ width: '5.75rem' }} />
          {getTargetPath ? <col /> : null}
          <col style={{ width: inheritedAccepted === undefined ? '15rem' : '21rem' }} />
        </colgroup>
        <TableBody>
          {files.map((file, index) => {
            const targetPath = getTargetPath?.(file) ?? null
            return (
              <TableRow key={file.id}>
                <TableCell className="whitespace-nowrap py-3 pl-3 pr-3 align-middle">
                  <div className="flex min-w-0 items-center gap-2">
                    <TreeIndentGuide isLast={index === files.length - 1} />
                    <DepotFileIcon file={file} />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium" title={file.candidate_relative_path}>
                        {file.candidate_relative_path}
                      </div>
                      {file.blocked_reason ? <div className="mt-1 text-xs text-destructive">{file.blocked_reason}</div> : null}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="whitespace-nowrap py-3 pr-3 text-right align-middle">
                  <div className="flex justify-end">
                    <Badge className="whitespace-nowrap">{formatDepotBytes(file.size_bytes)}</Badge>
                  </div>
                </TableCell>
                {getTargetPath ? (
                  <TableCell className="whitespace-nowrap py-3 pl-3 pr-3 align-middle">
                    <div className="flex min-w-0 items-center gap-3">
                      <PathArrow className="size-4" />
                      <span className="truncate text-sm" title={targetPath ?? undefined}>
                        {targetPath ?? t('noTransferTarget')}
                      </span>
                    </div>
                  </TableCell>
                ) : null}
                <TableCell className="py-3 pr-3 align-middle">
                  <div className="flex flex-nowrap justify-end gap-2">
                    {onFileReturn ? (
                      <Button
                        className="whitespace-nowrap"
                        size="sm"
                        variant="outline"
                        onClick={() => onFileReturn(file)}
                        disabled={fileReturnDisabled?.(file) || Boolean(file.blocked_reason)}
                        aria-label={t('sendBackLabel', { label: file.display_name })}
                      >
                        <RotateCcw data-icon="inline-start" />
                        {t('sendBack')}
                      </Button>
                    ) : null}
                    <Button className="whitespace-nowrap" size="sm" variant="outline" onClick={() => onFileDetails(file)} aria-label={t('detailsLabel', { label: file.display_name })}>
                      <Info data-icon="inline-start" />
                      {t('details')}
                    </Button>
                    {inheritedAccepted === undefined ? null : (
                      <DepotCandidateDecisionSwitcher accepted={inheritedAccepted} inherited target={file.display_name} />
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
        </Table>
      </div>
      ) : null}
    </>
  )
}

function TreeIndentGuide({ isLast }: { isLast: boolean }) {
  return (
    <span aria-hidden="true" className="relative min-h-5 w-7 shrink-0 self-stretch">
      <span className={`absolute left-3 w-px bg-border ${isLast ? 'top-0 h-1/2' : 'inset-y-0'}`} />
      <span className="absolute left-3 top-1/2 h-px w-4 bg-border" />
    </span>
  )
}

function DepotFileIcon({ file }: { file: DepotCandidateFile }) {
  const { t } = useI18n()
  const Icon = file.is_media ? Film : file.extension === '.srt' || file.extension === '.ass' || file.extension === '.ssa' ? FileText : File
  const tone = file.blocked_reason ? 'text-destructive' : file.is_media ? 'text-primary' : file.extension === '.srt' ? 'text-sky-500' : 'text-muted-foreground'
  const label = file.extension ?? t('file')
  return (
    <span className={`inline-flex size-5 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 ${tone}`} title={label}>
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}</span>
    </span>
  )
}
