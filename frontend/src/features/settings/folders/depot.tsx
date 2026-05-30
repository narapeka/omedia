import { Check, FolderOpen, Info, Trash2 } from 'lucide-react'
import { useId, useState } from 'react'
import type { DepotSummary, OriginSummary, ResolveMode } from '@/api/types'
import type { TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { DirectoryPickerDialog } from '@/components/filesystem/DirectoryPickerDialog'
import { SelectControl } from '@/components/common/SelectControl'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { Input } from '@/components/ui/input'
import { FieldLabelWithInfo, TextField, fieldCaptionClassName } from '../field'
import type { DepotDraft } from './draft'
import { mediaTypeOptions } from './validate'

export function DepotRemoveButton({
  depot,
  users,
  onRemove,
  mode = 'icon',
}: {
  depot: DepotSummary
  users: OriginSummary[]
  onRemove: () => void
  mode?: 'icon' | 'button'
}) {
  const { t } = useI18n()
  const buttonContent = mode === 'button' ? (
    <>
      <Trash2 data-icon="inline-start" />
      {t('remove')}
    </>
  ) : (
    <Trash2 />
  )

  if (users.length === 0) {
    return (
      <Button className="whitespace-nowrap" size={mode === 'button' ? 'sm' : 'icon-xs'} variant="danger" aria-label={t('removeLabel', { label: depot.name })} onClick={onRemove}>
        {buttonContent}
      </Button>
    )
  }

  return (
    <HoverCard closeDelay={120} openDelay={80}>
      <HoverCardTrigger asChild>
        <span
          aria-label={t('depotUsedByOrigins', { name: depot.name })}
          className="inline-flex cursor-not-allowed"
          role="button"
          tabIndex={0}
        >
          <Button className="whitespace-nowrap" size={mode === 'button' ? 'sm' : 'icon-xs'} variant="danger" disabled>
            {buttonContent}
          </Button>
        </span>
      </HoverCardTrigger>
      <HoverCardContent align="end" className="w-72">
        <div className="flex flex-col gap-2">
          <div className="font-medium">{t('depotUsedByOriginsTitle')}</div>
          <p className="text-sm text-muted-foreground">{t('depotUsedByOriginsDescription')}</p>
          <div className="flex flex-col gap-1">
            {users.map((origin) => (
              <div key={origin.id} className="rounded-md border px-2 py-1">
                <div className="truncate font-medium" title={origin.name}>{origin.name}</div>
                <div className="truncate text-xs text-muted-foreground" title={origin.path}>{origin.path}</div>
              </div>
            ))}
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}

export function DepotDialog({
  draft,
  transferRules,
  saving,
  onChange,
  onSave,
  onClose,
}: {
  draft: DepotDraft | null
  transferRules: { id: string; name?: string | null }[]
  saving: boolean
  onChange: (draft: DepotDraft | null) => void
  onSave: () => void
  onClose: () => void
}) {
  const { t } = useI18n()
  const [directoryPickerTarget, setDirectoryPickerTarget] = useState<'depot' | 'library' | null>(null)
  const pickerPath = directoryPickerTarget === 'depot' ? draft?.path : draft?.target_library_path

  return (
    <>
      <Dialog open={Boolean(draft)} onOpenChange={(open) => { if (!open) onClose() }}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{draft?.mode === 'edit' ? t('editDepot') : t('createDepot')}</DialogTitle>
            <DialogDescription>{t('depotDialogDescription')}</DialogDescription>
          </DialogHeader>
          {draft ? (
            <FieldGroup>
              {draft.mode === 'edit' ? (
                <Alert className="border-amber-500/30 bg-amber-500/10 text-amber-950 dark:text-amber-100">
                  <Info />
                  <AlertDescription className="text-amber-950/90 dark:text-amber-100/90">
                    {t('depotPathEditWarning')}
                  </AlertDescription>
                </Alert>
              ) : null}
              {draft.mode === 'create' ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <TextField label={t('name')} value={draft.name} onChange={(name) => onChange({ ...draft, name })} />
                  <Field>
                    <SelectControl
                      value={draft.media_type}
                      onValueChange={(media_type) => {
                        const nextMediaType = media_type as DepotDraft['media_type']
                        onChange({ ...draft, media_type: nextMediaType, resolveMode: nextMediaType === 'tv' ? draft.resolveMode : 'full' })
                      }}
                      placeholder={t('selectMediaType')}
                      options={mediaTypeOptions(t)}
                    />
                    <FieldLabel className={fieldCaptionClassName}>{t('mediaType')}</FieldLabel>
                  </Field>
                </div>
              ) : (
                <TextField label={t('name')} value={draft.name} onChange={(name) => onChange({ ...draft, name })} />
              )}
              {draft.mode === 'create' && draft.media_type === 'tv' ? (
                <Field>
                  <SelectControl
                    value={draft.resolveMode}
                    onValueChange={(resolveMode) => onChange({ ...draft, resolveMode: resolveMode as ResolveMode })}
                    options={depotResolveModeOptions(t)}
                  />
                  <FieldLabelWithInfo help={<ResolveModeHelp />}>
                    {t('depotResolveMode')}
                  </FieldLabelWithInfo>
                </Field>
              ) : null}
              <DirectoryField
                label={t('depotPath')}
                help={t('depotPathHelp')}
                value={draft.path}
                onChange={(path) => onChange({ ...draft, path })}
                onSelectClick={() => setDirectoryPickerTarget('depot')}
              />
              <DirectoryField
                label={t('libraryPath')}
                help={t('libraryPathHelp')}
                value={draft.target_library_path}
                onChange={(target_library_path) => onChange({ ...draft, target_library_path })}
                onSelectClick={() => setDirectoryPickerTarget('library')}
              />
              <Field>
                <SelectControl value={draft.transfer_rule_id} onValueChange={(transfer_rule_id) => onChange({ ...draft, transfer_rule_id })} options={[{ value: '', label: t('none') }, ...transferRules.map((rule) => ({ value: rule.id, label: rule.name }))]} />
                <FieldLabelWithInfo help={t('transferRuleHelp')}>{t('transferRules')}</FieldLabelWithInfo>
              </Field>
            </FieldGroup>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>{t('cancel')}</Button>
            <Button onClick={onSave} disabled={saving || !draft?.name.trim() || !draft.media_type || !draft.path || !draft.target_library_path}>
              <Check data-icon="inline-start" />
              {t('saveDepot')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DirectoryPickerDialog
        open={Boolean(directoryPickerTarget)}
        title={directoryPickerTarget === 'library' ? t('chooseLibraryPath') : t('chooseDepotPath')}
        description={t('browseDepotFolder')}
        initialPath={pickerPath}
        confirmLabel={directoryPickerTarget === 'library' ? t('useAsLibraryPath') : t('useAsDepotPath')}
        onOpenChange={(open) => {
          if (!open) setDirectoryPickerTarget(null)
        }}
        onSelect={(path) => {
          if (!draft || !directoryPickerTarget) return
          if (directoryPickerTarget === 'depot') onChange({ ...draft, path })
          else onChange({ ...draft, target_library_path: path })
        }}
      />
    </>
  )
}

function DirectoryField({
  label,
  help,
  value,
  onChange,
  onSelectClick,
}: {
  label: string
  help?: string
  value: string
  onChange: (value: string) => void
  onSelectClick: () => void
}) {
  const { t } = useI18n()
  const id = useId()
  return (
    <Field>
      <div className="flex h-8 min-w-0 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
        <Input
          id={id}
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
      <FieldLabelWithInfo htmlFor={id} help={help}>{label}</FieldLabelWithInfo>
    </Field>
  )
}

function ResolveModeHelp() {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-2">
      <div>
        <span className="font-medium text-foreground">{t('resolveModeFull')}</span>
        <span>: {t('resolveModeFullDescription')}</span>
      </div>
      <div>
        <span className="font-medium text-foreground">{t('resolveModeIncremental')}</span>
        <span>: {t('resolveModeIncrementalDescription')}</span>
      </div>
    </div>
  )
}

export function depotResolveModeOptions(t: TFunction) {
  return [
    { value: 'full', label: t('resolveModeFull') },
    { value: 'incremental', label: t('resolveModeIncremental') },
  ]
}

export function depotResolveModeLabel(t: TFunction, mode: ResolveMode | null | undefined) {
  return mode === 'incremental' ? t('resolveModeIncremental') : t('resolveModeFull')
}

export function highConfidenceBadgeClass() {
  return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
}
