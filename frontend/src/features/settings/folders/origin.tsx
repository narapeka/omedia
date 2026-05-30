import { Check, FolderOpen, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { OriginSummary } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { SelectControl } from '@/components/common/SelectControl'
import { DirectoryPickerDialog } from '@/components/filesystem/DirectoryPickerDialog'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { sortOriginsByName } from '@/features/origin/model'
import type { OriginDraft } from './draft'
import { ruleName } from './validate'

export function OriginChildTable({
  origins,
  organizeRules,
  activeDraft,
  saving,
  onAdd,
  onEdit,
  onDraftChange,
  onSave,
  onCancel,
  onRemove,
}: {
  origins: OriginSummary[]
  organizeRules: { id: string; name?: string | null }[]
  activeDraft: OriginDraft | null
  saving: boolean
  onAdd: () => void
  onEdit: (origin: OriginSummary) => void
  onDraftChange: (draft: OriginDraft | null) => void
  onSave: () => void
  onCancel: () => void
  onRemove: (origin: OriginSummary) => void
}) {
  const { t } = useI18n()
  const [directoryPickerOpen, setDirectoryPickerOpen] = useState(false)
  const editingOriginId = activeDraft?.mode === 'edit' ? activeDraft.originalId : null
  const appendDraftRow = activeDraft && activeDraft.mode !== 'edit'
  const sortedOrigins = useMemo(() => sortOriginsByName(origins), [origins])

  return (
    <>
      <div className="overflow-hidden rounded-lg border bg-muted/10">
        <Table className="block sm:table sm:table-fixed">
          <colgroup>
            <col style={{ width: '26%' }} />
            <col />
            <col style={{ width: '20%' }} />
            <col style={{ width: '5.25rem' }} />
          </colgroup>
          <TableHeader className="block sm:table-header-group">
            <TableRow className="flex items-center justify-between hover:bg-transparent sm:table-row">
              <TableHead className="block h-auto px-3 py-2 text-muted-foreground sm:table-cell sm:h-10 sm:py-0">{t('originName')}</TableHead>
              <TableHead className="hidden px-3 text-muted-foreground sm:table-cell">{t('sourcePath')}</TableHead>
              <TableHead className="hidden px-3 text-muted-foreground sm:table-cell">{t('rule')}</TableHead>
              <TableHead className="block h-auto px-2 py-2 sm:table-cell sm:h-10 sm:py-0">
                <div className="flex justify-end">
                  <Button
                    size="icon-sm"
                    variant="secondary"
                    aria-label={t('createOrigin')}
                    onClick={onAdd}
                    disabled={Boolean(activeDraft) || saving}
                  >
                    <Plus />
                  </Button>
                </div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="block sm:table-row-group">
            {sortedOrigins.map((origin) => (
              editingOriginId === origin.id && activeDraft ? (
                <OriginEditTableRow
                  key={origin.id}
                  draft={activeDraft}
                  organizeRules={organizeRules}
                  saving={saving}
                  onChange={onDraftChange}
                  onSave={onSave}
                  onCancel={onCancel}
                  onSelectPath={() => setDirectoryPickerOpen(true)}
                />
              ) : (
                <OriginViewTableRow
                  key={origin.id}
                  origin={origin}
                  organizeRuleName={ruleName(organizeRules, origin.policy.organize_rule_id, t)}
                  onEdit={() => onEdit(origin)}
                  onRemove={() => onRemove(origin)}
                />
              )
            ))}
            {appendDraftRow ? (
              <OriginEditTableRow
                draft={activeDraft}
                organizeRules={organizeRules}
                saving={saving}
                onChange={onDraftChange}
                onSave={onSave}
                onCancel={onCancel}
                onSelectPath={() => setDirectoryPickerOpen(true)}
              />
            ) : null}
            {origins.length === 0 && !activeDraft ? (
              <TableRow className="block hover:bg-transparent sm:table-row">
                <TableCell colSpan={4} className="block px-3 py-4 text-center text-muted-foreground sm:table-cell">
                  {t('noOriginsFeedDepot')}
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      <DirectoryPickerDialog
        open={directoryPickerOpen && Boolean(activeDraft)}
        title={t('chooseOriginSource')}
        description={t('browseOriginSource')}
        initialPath={activeDraft?.path}
        confirmLabel={t('useAsSource')}
        onOpenChange={setDirectoryPickerOpen}
        onSelect={(path) => {
          if (activeDraft) onDraftChange({ ...activeDraft, path })
        }}
      />
    </>
  )
}

function OriginViewTableRow({
  origin,
  organizeRuleName,
  onEdit,
  onRemove,
}: {
  origin: OriginSummary
  organizeRuleName: string
  onEdit: () => void
  onRemove: () => void
}) {
  const { t } = useI18n()
  return (
    <TableRow className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 p-3 hover:bg-muted/20 sm:table-row sm:p-0">
      <TableCell className="block p-0 sm:table-cell sm:px-3 sm:py-2">
        <div className="truncate font-medium" title={origin.name}>{origin.name}</div>
      </TableCell>
      <TableCell className="block p-0 sm:table-cell sm:px-3 sm:py-2">
        <div className="flex min-w-0 gap-2 text-sm sm:block">
          <span className="shrink-0 text-muted-foreground sm:hidden">{t('sourcePath')}</span>
          <span className="min-w-0 truncate text-muted-foreground" title={origin.path}>{origin.path}</span>
        </div>
      </TableCell>
      <TableCell className="block p-0 sm:table-cell sm:px-3 sm:py-2">
        <div className="flex min-w-0 gap-2 text-sm sm:block">
          <span className="shrink-0 text-muted-foreground sm:hidden">{t('rule')}</span>
          <span className="min-w-0 truncate text-muted-foreground" title={organizeRuleName}>{organizeRuleName}</span>
        </div>
      </TableCell>
      <TableCell className="col-start-2 row-start-1 row-span-3 block p-0 sm:table-cell sm:px-2 sm:py-2">
        <div className="flex justify-end gap-1">
          <Button size="icon-sm" variant="ghost" aria-label={t('editLabel', { label: origin.name })} onClick={onEdit}>
            <Pencil />
          </Button>
          <Button size="icon-sm" variant="danger" aria-label={t('removeLabel', { label: origin.name })} onClick={onRemove}>
            <Trash2 />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

function OriginEditTableRow({
  draft,
  organizeRules,
  saving,
  onChange,
  onSave,
  onCancel,
  onSelectPath,
}: {
  draft: OriginDraft
  organizeRules: { id: string; name?: string | null }[]
  saving: boolean
  onChange: (draft: OriginDraft | null) => void
  onSave: () => void
  onCancel: () => void
  onSelectPath: () => void
}) {
  const { t } = useI18n()
  const canSave = Boolean(draft.name.trim() && draft.path.trim())

  return (
    <TableRow className="grid gap-2 bg-muted/20 p-3 hover:bg-muted/20 sm:table-row sm:p-0">
      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground sm:hidden">{t('originName')}</span>
          <Input
            aria-label={t('name')}
            className="h-8"
            value={draft.name}
            onChange={(event) => onChange({ ...draft, name: event.target.value })}
          />
        </div>
      </TableCell>
      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground sm:hidden">{t('sourcePath')}</span>
          <InlineDirectoryField
            ariaLabel={t('sourcePath')}
            value={draft.path}
            onChange={(path) => onChange({ ...draft, path })}
            onSelectClick={onSelectPath}
          />
        </div>
      </TableCell>
      <TableCell className="block p-0 whitespace-normal sm:table-cell sm:px-3 sm:py-2">
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground sm:hidden">{t('rule')}</span>
          <SelectControl
            value={draft.organize_rule_id}
            onValueChange={(organize_rule_id) => onChange({ ...draft, organize_rule_id })}
            options={[{ value: '', label: t('none') }, ...organizeRules.map((rule) => ({ value: rule.id, label: rule.name }))]}
            triggerAriaLabel={t('organizeRules')}
          />
        </div>
      </TableCell>
      <TableCell className="block p-0 sm:table-cell sm:px-2 sm:py-2">
        <div className="flex justify-end gap-1">
          <Button size="icon-sm" variant="secondary" aria-label={t('saveOrigin')} onClick={onSave} disabled={saving || !canSave}>
            <Check />
          </Button>
          <Button size="icon-sm" variant="ghost" aria-label={t('cancel')} onClick={onCancel} disabled={saving}>
            <X />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

function InlineDirectoryField({
  ariaLabel,
  value,
  onChange,
  onSelectClick,
}: {
  ariaLabel: string
  value: string
  onChange: (value: string) => void
  onSelectClick: () => void
}) {
  const { t } = useI18n()
  return (
    <div className="flex h-8 min-w-0 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
      <Input
        aria-label={ariaLabel}
        className="h-full min-w-0 flex-1 rounded-none border-0 bg-transparent px-3 focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <Button
        type="button"
        className="h-full w-20 rounded-none border-y-0 border-l border-r-0 border-input bg-transparent px-3 hover:bg-muted/70 focus-visible:ring-0"
        variant="ghost"
        onClick={onSelectClick}
      >
        <FolderOpen data-icon="inline-start" />
        {t('select')}
      </Button>
    </div>
  )
}
