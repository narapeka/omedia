import { ChevronDown, ChevronRight, File, Folder, Info, RotateCcw } from 'lucide-react'
import type { DepotCandidateFile, DepotCandidate } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'
import { useIs2xl } from '@/lib/useMediaQuery'
import { DepotCandidateDecisionSwitcher } from './decision'
import { DepotCandidateInventoryTable } from './table'
import { depotCandidateCountSummary, depotCandidateKindLabel, formatDepotBytes, formatDepotModifiedTime } from './model'

type CandidateSelectionMode = 'checkbox' | 'decision'

export function DepotCandidateSection({
  candidate,
  selected,
  expanded,
  selectionMode = 'checkbox',
  selectionDisabled,
  onSelectedChange,
  onToggleExpanded,
  onCandidateDetails,
  onFileDetails,
  onCandidateReturn,
  onFileReturn,
  candidateReturnDisabled,
  fileReturnDisabled,
  showCandidateIcon = true,
  getFileTargetPath,
}: {
  candidate: DepotCandidate
  selected: boolean
  expanded: boolean
  selectionMode?: CandidateSelectionMode
  selectionDisabled?: boolean
  onSelectedChange: (checked: boolean) => void
  onToggleExpanded: () => void
  onCandidateDetails: () => void
  onFileDetails: (file: DepotCandidateFile) => void
  onCandidateReturn?: () => void
  onFileReturn?: (file: DepotCandidateFile) => void
  candidateReturnDisabled?: boolean
  fileReturnDisabled?: (file: DepotCandidateFile) => boolean
  showCandidateIcon?: boolean
  getFileTargetPath?: (file: DepotCandidateFile) => string | null
}) {
  const { locale, t } = useI18n()
  const isFolder = candidate.kind === 'folder'
  const usesDecisionSwitch = selectionMode === 'decision'
  const textIndentClass = showCandidateIcon ? 'ml-[4.25rem]' : 'ml-9'
  const is2xl = useIs2xl()

  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      {!is2xl ? (
      <div className="grid gap-3 border-b bg-muted/30 p-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0 pr-0 sm:pr-3">
            <div className="flex min-w-0 items-center gap-2">
              {!usesDecisionSwitch ? (
                <Checkbox
                  checked={selected}
                  disabled={selectionDisabled}
                  onCheckedChange={(checked) => onSelectedChange(Boolean(checked))}
                  aria-label={t('selectLabel', { label: candidate.display_name })}
                />
              ) : null}
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={onToggleExpanded}
                disabled={!isFolder}
                aria-label={isFolder ? (expanded ? t('collapseLabel', { label: candidate.display_name }) : t('expandLabel', { label: candidate.display_name })) : t('detailsLabel', { label: candidate.display_name })}
                aria-expanded={isFolder ? expanded : undefined}
              >
                {isFolder ? expanded ? <ChevronDown /> : <ChevronRight /> : <File />}
              </Button>
              {showCandidateIcon ? (
                isFolder ? <Folder className="size-4 shrink-0 text-muted-foreground" /> : <File className="size-4 shrink-0 text-muted-foreground" />
              ) : null}
              <span className="min-w-0 truncate font-medium" title={candidate.display_name}>
                {candidate.display_name}
              </span>
              {!usesDecisionSwitch ? <Badge className="shrink-0 whitespace-nowrap">{depotCandidateKindLabel(candidate.kind, t)}</Badge> : null}
              {candidate.blocked_reason ? <Badge tone="danger" className="shrink-0 whitespace-nowrap">{candidate.blocked_reason}</Badge> : null}
            </div>
            <div className={cn('mt-1 truncate text-xs text-muted-foreground', textIndentClass)} title={candidate.relative_path}>
              {candidate.relative_path}
            </div>
          </div>

          <div className={cn('flex w-auto flex-row flex-wrap items-center justify-start gap-2 pt-0 sm:w-40 sm:shrink-0 sm:flex-col sm:items-end sm:gap-1 sm:pt-1', textIndentClass)}>
            <div className="flex flex-wrap items-center justify-start gap-2 sm:justify-end">
              <Badge className="shrink-0 whitespace-nowrap border-border/80 bg-muted/60 text-foreground">{formatDepotBytes(candidate.size_bytes)}</Badge>
              <Badge className="shrink-0 whitespace-nowrap border-border/80 bg-muted/60 text-foreground">{depotCandidateCountSummary(candidate, t)}</Badge>
            </div>
            <span className="min-w-0 truncate text-xs text-muted-foreground sm:w-full sm:pr-2 sm:text-right">{formatDepotModifiedTime(candidate.modified_time, locale)}</span>
          </div>
        </div>

        <div className={cn('flex flex-wrap items-center justify-between gap-2', textIndentClass)}>
          <div className="flex flex-wrap gap-2">
            {onCandidateReturn ? (
              <Button
                className="whitespace-nowrap"
                size="sm"
                variant="outline"
                onClick={onCandidateReturn}
                disabled={candidateReturnDisabled || Boolean(candidate.blocked_reason)}
                aria-label={t('sendBackLabel', { label: candidate.display_name })}
              >
                <RotateCcw data-icon="inline-start" />
                {t('sendBack')}
              </Button>
            ) : null}
            <Button className="whitespace-nowrap" size="sm" variant="outline" onClick={onCandidateDetails} aria-label={t('detailsLabel', { label: candidate.display_name })}>
              <Info data-icon="inline-start" />
              {t('details')}
            </Button>
          </div>
          {usesDecisionSwitch ? (
            <DepotCandidateDecisionSwitcher
              accepted={selected}
              disabled={selectionDisabled}
              target={candidate.display_name}
              onAcceptedChange={onSelectedChange}
            />
          ) : null}
        </div>
      </div>
      ) : null}

      {is2xl ? (
      <div className="grid grid-cols-[50%_5.75rem_5.75rem_minmax(0,1fr)_auto] items-center gap-y-3 gap-x-0 border-b bg-muted/30 p-3">
        <div className="min-w-0 pr-3">
          <div className="flex min-w-0 items-center gap-2">
            {!usesDecisionSwitch ? (
              <Checkbox
                checked={selected}
                disabled={selectionDisabled}
                onCheckedChange={(checked) => onSelectedChange(Boolean(checked))}
                aria-label={t('selectLabel', { label: candidate.display_name })}
              />
            ) : null}
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={onToggleExpanded}
              disabled={!isFolder}
              aria-label={isFolder ? (expanded ? t('collapseLabel', { label: candidate.display_name }) : t('expandLabel', { label: candidate.display_name })) : t('detailsLabel', { label: candidate.display_name })}
              aria-expanded={isFolder ? expanded : undefined}
            >
              {isFolder ? expanded ? <ChevronDown /> : <ChevronRight /> : <File />}
            </Button>
            {showCandidateIcon ? (
              isFolder ? <Folder className="size-4 shrink-0 text-muted-foreground" /> : <File className="size-4 shrink-0 text-muted-foreground" />
            ) : null}
            <span className="min-w-0 truncate font-medium" title={candidate.display_name}>
              {candidate.display_name}
            </span>
          </div>
          <div className={cn('mt-1 truncate text-xs text-muted-foreground', textIndentClass)} title={candidate.relative_path}>
            {candidate.relative_path}
          </div>
        </div>

        <div className="contents">
          <div className="flex min-w-0 justify-end pr-3">
            <Badge className="whitespace-nowrap">{formatDepotBytes(candidate.size_bytes)}</Badge>
          </div>
          <div className="flex min-w-0 justify-start pl-3">
            <Badge className="whitespace-nowrap">{depotCandidateCountSummary(candidate, t)}</Badge>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap items-center gap-2 pl-3">
          {!usesDecisionSwitch ? <Badge>{depotCandidateKindLabel(candidate.kind, t)}</Badge> : null}
          {candidate.blocked_reason ? <Badge tone="danger">{candidate.blocked_reason}</Badge> : null}
          <span className="text-xs text-muted-foreground">{formatDepotModifiedTime(candidate.modified_time, locale)}</span>
        </div>

        <div className="flex flex-wrap items-center justify-end justify-self-end gap-2 pl-3">
          <div className="flex flex-wrap gap-2">
            {onCandidateReturn ? (
              <Button
                className="whitespace-nowrap"
                size="sm"
                variant="outline"
                onClick={onCandidateReturn}
                disabled={candidateReturnDisabled || Boolean(candidate.blocked_reason)}
                aria-label={t('sendBackLabel', { label: candidate.display_name })}
              >
                <RotateCcw data-icon="inline-start" />
                {t('sendBack')}
              </Button>
            ) : null}
            <Button className="whitespace-nowrap" size="sm" variant="outline" onClick={onCandidateDetails} aria-label={t('detailsLabel', { label: candidate.display_name })}>
              <Info data-icon="inline-start" />
              {t('details')}
            </Button>
          </div>
          {usesDecisionSwitch ? (
            <DepotCandidateDecisionSwitcher
              accepted={selected}
              disabled={selectionDisabled}
              target={candidate.display_name}
              onAcceptedChange={onSelectedChange}
            />
          ) : null}
        </div>
      </div>
      ) : null}

      {isFolder && expanded ? (
        <DepotCandidateInventoryTable
          candidate={candidate}
          onFileDetails={onFileDetails}
          onFileReturn={onFileReturn}
          fileReturnDisabled={fileReturnDisabled}
          getTargetPath={getFileTargetPath}
          inheritedAccepted={usesDecisionSwitch ? selected : undefined}
        />
      ) : null}
    </section>
  )
}
