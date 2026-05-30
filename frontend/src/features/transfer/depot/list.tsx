import { Layers2, RotateCw } from 'lucide-react'
import type { DepotCandidateFile, DepotCandidate } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { cn } from '@/lib/utils'
import { isDisplayOnlyEmptyRootGroupCandidate } from './model'
import { DepotCandidateSection } from './section'

type CandidateGroupBlock = {
  type: 'group'
  key: string
  label: string
  candidates: DepotCandidate[]
}

type CandidateBlock = {
  type: 'candidate'
  key: string
  candidate: DepotCandidate
}

type EmptyRootGroupBlock = {
  type: 'empty-root-group'
  key: string
  label: string
}

type CandidateListBlock = CandidateGroupBlock | CandidateBlock | EmptyRootGroupBlock

export function DepotCandidateList({
  candidates,
  pendingCount,
  selectedIds,
  expandedIds,
  fetching,
  selectionMode,
  selectionDisabled,
  onRefresh,
  onToggleSelected,
  onToggleExpanded,
  onCandidateDetails,
  onFileDetails,
  onCandidateReturn,
  onFileReturn,
  candidateReturnDisabled,
  fileReturnDisabled,
  title,
  emptyLabel,
  showHeader = true,
  showCandidateIcon,
  candidateListClassName,
  getFileTargetPath,
}: {
  candidates: DepotCandidate[]
  pendingCount: number
  selectedIds: Set<string>
  expandedIds: Set<string>
  fetching: boolean
  selectionMode?: 'checkbox' | 'decision'
  selectionDisabled?: (candidate: DepotCandidate) => boolean
  onRefresh: () => void
  onToggleSelected: (candidateId: string, checked: boolean) => void
  onToggleExpanded: (candidateId: string) => void
  onCandidateDetails: (candidate: DepotCandidate) => void
  onFileDetails: (candidate: DepotCandidate, file: DepotCandidateFile) => void
  onCandidateReturn?: (candidate: DepotCandidate) => void
  onFileReturn?: (candidate: DepotCandidate, file: DepotCandidateFile) => void
  candidateReturnDisabled?: (candidate: DepotCandidate) => boolean
  fileReturnDisabled?: (candidate: DepotCandidate, file: DepotCandidateFile) => boolean
  title?: string
  emptyLabel?: string
  showHeader?: boolean
  showCandidateIcon?: boolean
  candidateListClassName?: string
  getFileTargetPath?: (candidate: DepotCandidate, file: DepotCandidateFile) => string | null
}) {
  const { t } = useI18n()
  const displayTitle = title ?? t('depotCandidates')
  const displayEmptyLabel = emptyLabel ?? t('noDepotCandidates')
  const blocks = buildCandidateBlocks(candidates)
  return (
    <div className="flex flex-col gap-3">
      {showHeader ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{displayTitle}</h2>
            <Badge tone={pendingCount > 0 ? 'warning' : undefined}>{t('countPending', { count: pendingCount })}</Badge>
          </div>
          <Button onClick={onRefresh} disabled={fetching}>
            <RotateCw data-icon="inline-start" />
            {t('refresh')}
          </Button>
        </div>
      ) : null}

      {candidates.length ? (
        <div className={cn('flex flex-col gap-3', candidateListClassName)}>
          {blocks.map((block) =>
            block.type === 'empty-root-group' ? (
              <div key={block.key} className="flex flex-col gap-3">
                <DepotCandidateGroupHeader label={block.label} />
                <DepotCandidateEmptyFolder />
              </div>
            ) : block.type === 'candidate' ? (
              <DepotCandidateListItem
                key={block.key}
                candidate={block.candidate}
                selectedIds={selectedIds}
                expandedIds={expandedIds}
                selectionMode={selectionMode}
                selectionDisabled={selectionDisabled}
                onToggleSelected={onToggleSelected}
                onToggleExpanded={onToggleExpanded}
                onCandidateDetails={onCandidateDetails}
                onFileDetails={onFileDetails}
                onCandidateReturn={onCandidateReturn}
                onFileReturn={onFileReturn}
                candidateReturnDisabled={candidateReturnDisabled}
                fileReturnDisabled={fileReturnDisabled}
                showCandidateIcon={showCandidateIcon}
                getFileTargetPath={getFileTargetPath}
              />
            ) : (
              <div key={block.key} className="flex flex-col gap-3">
                <DepotCandidateGroupHeader label={block.label} />
                {block.candidates.map((candidate) => (
                  <DepotCandidateListItem
                    key={candidate.id}
                    candidate={candidate}
                    selectedIds={selectedIds}
                    expandedIds={expandedIds}
                    selectionMode={selectionMode}
                    selectionDisabled={selectionDisabled}
                    onToggleSelected={onToggleSelected}
                    onToggleExpanded={onToggleExpanded}
                    onCandidateDetails={onCandidateDetails}
                    onFileDetails={onFileDetails}
                    onCandidateReturn={onCandidateReturn}
                    onFileReturn={onFileReturn}
                    candidateReturnDisabled={candidateReturnDisabled}
                    fileReturnDisabled={fileReturnDisabled}
                    showCandidateIcon={showCandidateIcon}
                    getFileTargetPath={getFileTargetPath}
                  />
                ))}
              </div>
            )
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">{displayEmptyLabel}</div>
      )}
    </div>
  )
}

function DepotCandidateListItem({
  candidate,
  selectedIds,
  expandedIds,
  selectionMode,
  selectionDisabled,
  onToggleSelected,
  onToggleExpanded,
  onCandidateDetails,
  onFileDetails,
  onCandidateReturn,
  onFileReturn,
  candidateReturnDisabled,
  fileReturnDisabled,
  showCandidateIcon,
  getFileTargetPath,
}: {
  candidate: DepotCandidate
  selectedIds: Set<string>
  expandedIds: Set<string>
  selectionMode?: 'checkbox' | 'decision'
  selectionDisabled?: (candidate: DepotCandidate) => boolean
  onToggleSelected: (candidateId: string, checked: boolean) => void
  onToggleExpanded: (candidateId: string) => void
  onCandidateDetails: (candidate: DepotCandidate) => void
  onFileDetails: (candidate: DepotCandidate, file: DepotCandidateFile) => void
  onCandidateReturn?: (candidate: DepotCandidate) => void
  onFileReturn?: (candidate: DepotCandidate, file: DepotCandidateFile) => void
  candidateReturnDisabled?: (candidate: DepotCandidate) => boolean
  fileReturnDisabled?: (candidate: DepotCandidate, file: DepotCandidateFile) => boolean
  showCandidateIcon?: boolean
  getFileTargetPath?: (candidate: DepotCandidate, file: DepotCandidateFile) => string | null
}) {
  return (
    <DepotCandidateSection
      candidate={candidate}
      selected={selectedIds.has(candidate.id)}
      expanded={expandedIds.has(candidate.id)}
      selectionMode={selectionMode}
      selectionDisabled={selectionDisabled?.(candidate)}
      onSelectedChange={(checked) => onToggleSelected(candidate.id, checked)}
      onToggleExpanded={() => onToggleExpanded(candidate.id)}
      onCandidateDetails={() => onCandidateDetails(candidate)}
      onFileDetails={(file) => onFileDetails(candidate, file)}
      onCandidateReturn={onCandidateReturn ? () => onCandidateReturn(candidate) : undefined}
      onFileReturn={onFileReturn ? (file) => onFileReturn(candidate, file) : undefined}
      candidateReturnDisabled={candidateReturnDisabled?.(candidate)}
      fileReturnDisabled={fileReturnDisabled ? (file) => fileReturnDisabled(candidate, file) : undefined}
      showCandidateIcon={showCandidateIcon}
      getFileTargetPath={getFileTargetPath ? (file) => getFileTargetPath(candidate, file) : undefined}
    />
  )
}

function buildCandidateBlocks(candidates: DepotCandidate[]): CandidateListBlock[] {
  const blocks: CandidateListBlock[] = []
  const byKey = new Map<string, CandidateGroupBlock>()
  for (const candidate of candidates) {
    if (isDisplayOnlyEmptyRootGroupCandidate(candidate)) {
      blocks.push({ type: 'empty-root-group', key: `empty-root:${candidate.id}`, label: candidate.display_name })
      continue
    }

    if (!candidate.group) {
      blocks.push({ type: 'candidate', key: `candidate:${candidate.id}`, candidate })
      continue
    }

    const key = candidate.group.key
    const label = candidate.group.display_name
    let group = byKey.get(key)
    if (!group) {
      group = { type: 'group', key, label, candidates: [] }
      byKey.set(key, group)
      blocks.push(group)
    }
    group.candidates.push(candidate)
  }
  return blocks
}

function DepotCandidateEmptyFolder() {
  const { t } = useI18n()
  return <div className="px-4 py-2 text-sm text-muted-foreground">{t('emptyFolder')}</div>
}

function DepotCandidateGroupHeader({ label }: { label: string }) {
  return (
    <div className="relative flex min-h-9 min-w-0 items-center gap-2.5 overflow-hidden border-y border-border/70 bg-muted/40 px-3 py-2 pl-4">
      <span className="omedia-metal-accent absolute inset-y-0 left-0 w-1.5" aria-hidden="true" />
      <Layers2 className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="min-w-0 truncate text-[13px] font-semibold text-foreground" title={label}>
        {label}
      </div>
    </div>
  )
}

