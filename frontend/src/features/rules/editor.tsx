import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import { Check, Copy, Download, Trash2 } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { OrganizeRule, RuleReferences, TransferRule } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { ConfirmDialog, type ConfirmDialogState } from '@/components/common/ConfirmDialog'
import { InfoTooltip } from '@/components/common/InfoTooltip'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { AddCategoryControl, CategoryEditor, FallbackBucketEditor, TransferAddCategoryPrompt } from './category'
import type { CategoryDraft, RuleDraft, RuleKind, RuleMutationPayload, RuleSelection } from './draft'
import { applyTemplateToDraft, defaultRule, emptyCategory, fromDraft, pruneBlankConditions, shiftCollapsedCategoryIndexes, toDraft, toggleCollapsedCategoryIndex, validateRuleDraft } from './draft'
import { RuleCreateMenu, RuleKindBadge, RuleListTable, buildRuleRows, firstSelectionFromRows } from './list'
import { RuleTemplateDialog, type RuleTemplate } from './template'

const fieldCaptionClassName = 'items-center gap-1.5 text-xs font-normal text-muted-foreground'

export function RuleEditor({
  ruleReferences,
  organizeRules,
  transferRules,
  organizeUsedBy,
  transferUsedBy,
  saving,
  deleting,
  onSave,
  onDelete,
}: {
  ruleReferences: RuleReferences
  organizeRules: OrganizeRule[]
  transferRules: TransferRule[]
  organizeUsedBy: (ruleId: string) => string[]
  transferUsedBy: (ruleId: string) => string[]
  saving: Record<RuleKind, boolean>
  deleting: Record<RuleKind, boolean>
  onSave: (kind: RuleKind, ruleId: string | undefined, rule: RuleMutationPayload) => void
  onDelete: (kind: RuleKind, ruleId: string) => void
}) {
  const { t } = useI18n()
  const ruleRows = useMemo(() => buildRuleRows(organizeRules, transferRules), [organizeRules, transferRules])
  const [selected, setSelected] = useState<RuleSelection>(() => firstSelectionFromRows(ruleRows))
  const selectedRule = useMemo(() => {
    if (!selected.id) return undefined
    const rules = selected.kind === 'organize' ? organizeRules : transferRules
    return rules.find((rule) => rule.id === selected.id)
  }, [organizeRules, selected.id, selected.kind, transferRules])
  const [draft, setDraft] = useState<RuleDraft>(() => toDraft(selectedRule ?? defaultRule(selected.kind, t)))
  const [error, setError] = useState('')
  const [draftActive, setDraftActive] = useState(false)
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<ConfirmDialogState | null>(null)
  const [collapsedCategories, setCollapsedCategories] = useState<Set<number>>(() => new Set())
  const [transferAddCategoryPromptOpen, setTransferAddCategoryPromptOpen] = useState(false)
  const [transferAddCategoryPromptSeen, setTransferAddCategoryPromptSeen] = useState(false)
  const kind = selected.kind
  const references = draft.id ? (kind === 'organize' ? organizeUsedBy(draft.id) : transferUsedBy(draft.id)) : []

  useEffect(() => {
    setSelected((current) => {
      if (!current.id && draftActive) return current
      if (!current.id) return current
      if (ruleRows.some((row) => row.kind === current.kind && row.rule.id === current.id)) return current
      return firstSelectionFromRows(ruleRows, current.kind)
    })
  }, [draftActive, ruleRows])

  useEffect(() => {
    if (!selectedRule && draftActive) return
    setDraft(toDraft(selectedRule ?? defaultRule(selected.kind, t)))
    setCollapsedCategories(new Set())
    setError('')
  }, [draftActive, selected.kind, selectedRule, t])

  const kindLabel = kind === 'organize' ? t('organize') : t('transfer')
  const metadataTitle = kind === 'organize' ? t('organizeRuleMetadata') : t('transferRuleMetadata')
  const metadataDescription = kind === 'organize' ? t('organizeRuleMetadataDescription') : t('transferRuleMetadataDescription')
  const showEmptyRuleState = !ruleRows.length && !draftActive
  const canImportTemplate = kind === 'organize' && draftActive && !selected.id && !draft.id

  const handleSave = () => {
    const sanitizedDraft = pruneBlankConditions(draft)
    const validation = validateRuleDraft(sanitizedDraft, kind, t)
    if (validation) {
      setError(validation)
      return
    }
    setDraft(sanitizedDraft)
    onSave(kind, sanitizedDraft.id || undefined, fromDraft(sanitizedDraft))
    setError('')
  }

  const handleDelete = () => {
    if (!draft.id) return
    const ruleId = draft.id
    setConfirmAction({
      title: t('removeRule'),
      description: t('removeRuleConfirm', { name: draft.name }),
      confirmLabel: t('remove'),
      destructive: true,
      onConfirm: () => onDelete(kind, ruleId),
    })
  }

  const handleCopy = () => {
    setDraftActive(true)
    setSelected({ kind, id: '' })
    setDraft({
      ...draft,
      id: '',
      name: `${draft.name || t('newRuleName', { kind: kindLabel })} ${t('copySuffix')}`,
    })
    setError('')
  }

  const beginNewRule = (nextKind: RuleKind) => {
    setDraftActive(true)
    setSelected({ kind: nextKind, id: '' })
    setDraft(toDraft(defaultRule(nextKind, t)))
    setCollapsedCategories(new Set())
    setError('')
  }

  const handleImportTemplate = (template: RuleTemplate) => {
    setDraft((currentDraft) => applyTemplateToDraft(currentDraft, template))
    setCollapsedCategories(new Set())
    setError('')
    setTemplateDialogOpen(false)
  }

  const addCategory = () => {
    setDraft({ ...draft, categories: [...draft.categories, emptyCategory()] })
    setCollapsedCategories(new Set())
  }

  const requestAddCategory = () => {
    if (kind === 'transfer' && !transferAddCategoryPromptSeen) {
      setTransferAddCategoryPromptSeen(true)
      setTransferAddCategoryPromptOpen(true)
      return
    }
    addCategory()
  }

  const confirmTransferAddCategory = () => {
    setTransferAddCategoryPromptOpen(false)
    addCategory()
  }

  const updateCategory = (categoryIndex: number, nextCategory: CategoryDraft) => {
    setDraft({ ...draft, categories: draft.categories.map((item, index) => (index === categoryIndex ? nextCategory : item)) })
  }

  const removeCategory = (categoryIndex: number) => {
    setDraft({ ...draft, categories: draft.categories.filter((_item, index) => index !== categoryIndex) })
    setCollapsedCategories((current) => shiftCollapsedCategoryIndexes(current, categoryIndex))
  }

  const toggleCategoryCollapsed = (categoryIndex: number) => {
    setCollapsedCategories((current) => toggleCollapsedCategoryIndex(current, categoryIndex))
  }

  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(20rem,30rem)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
        <Card className="min-w-0">
          <CardContent className="flex flex-col gap-3">
            <RuleListTable
              rows={ruleRows}
              selected={selected}
              onSelect={(nextSelection) => {
                setDraftActive(false)
                setSelected(nextSelection)
              }}
            />
            <div className="grid grid-cols-3 gap-2 border-t pt-3">
              <RuleCreateMenu onCreate={beginNewRule} />
              <Button aria-label={t('copyRule')} className="w-full" variant="secondary" onClick={handleCopy} disabled={!draft.id}>
                <Copy />
              </Button>
              <Button aria-label={t('removeRule')} className="w-full" variant="danger" onClick={handleDelete} disabled={deleting[kind] || !draft.id || references.length > 0}>
                <Trash2 />
              </Button>
            </div>
          </CardContent>
        </Card>
        {!showEmptyRuleState ? (
          <Card className="min-w-0">
            <CardContent className="flex flex-col gap-4">
              <div className="font-medium">{t('usedBy')}</div>
              {references.length ? (
                <div className="flex flex-wrap gap-1">
                  {references.map((item) => <Badge key={item}>{item}</Badge>)}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">{t('noCurrentReferences')}</div>
              )}
              {references.length ? <div className="text-xs text-muted-foreground">{t('reassignObjectsBeforeRuleRemove')}</div> : null}
            </CardContent>
          </Card>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-col gap-5">
        {showEmptyRuleState ? (
          <div className="flex min-h-28 items-center justify-center rounded-xl border bg-card text-sm text-muted-foreground">
            {t('noRulesConfigured')}
          </div>
        ) : (
          <>
            <Card className="min-w-0">
              <CardHeader className="grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <CardTitle className="flex items-center gap-2">
                    <span>{metadataTitle}</span>
                    <RuleKindBadge kind={kind} />
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">{metadataDescription}</p>
                </div>
                <CardAction className="col-start-1 row-start-auto flex w-full flex-wrap justify-start gap-2 sm:col-start-2 sm:row-span-2 sm:row-start-1 sm:w-auto sm:justify-end">
                  {canImportTemplate ? (
                    <Button data-testid="import-template-button" variant="secondary" onClick={() => setTemplateDialogOpen(true)}>
                      <Download data-icon="inline-start" />
                      {t('importTemplate')}
                    </Button>
                  ) : null}
                  <Button onClick={handleSave} disabled={saving[kind]}>
                    <Check data-icon="inline-start" />
                    {t('saveChanges')}
                  </Button>
                </CardAction>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <FieldGroup className="grid gap-4 md:grid-cols-2">
                  <TextField label={t('name')} value={draft.name} onChange={(name) => setDraft({ ...draft, name })} />
                </FieldGroup>
                <div className="flex flex-col gap-4 border-t pt-4">
                  <div className="flex flex-col gap-3">
                    {draft.categories.map((category, categoryIndex) => (
                      <CategoryEditor
                        key={categoryIndex}
                        kind={kind}
                        ruleReferences={ruleReferences}
                        category={category}
                        categoryIndex={categoryIndex}
                        expanded={!collapsedCategories.has(categoryIndex)}
                        onToggleExpanded={() => toggleCategoryCollapsed(categoryIndex)}
                        onChange={(nextCategory) => updateCategory(categoryIndex, nextCategory)}
                        onRemove={() => removeCategory(categoryIndex)}
                      />
                    ))}
                  </div>
                  <AddCategoryControl onClick={requestAddCategory} />
                  <FallbackBucketEditor
                    bucket={draft.fallback_bucket}
                    onChange={(fallback_bucket) => setDraft({ ...draft, fallback_bucket })}
                  />
                </div>
              </CardContent>
            </Card>
            {error ? <div role="alert" className="text-sm text-destructive">{error}</div> : null}
          </>
        )}
      </div>
      {canImportTemplate ? (
        <RuleTemplateDialog
          open={templateDialogOpen}
          onOpenChange={setTemplateDialogOpen}
          onImport={handleImportTemplate}
        />
      ) : null}
      <TransferAddCategoryPrompt
        open={transferAddCategoryPromptOpen}
        onOpenChange={setTransferAddCategoryPromptOpen}
        onConfirm={confirmTransferAddCategory}
      />
      <ConfirmDialog state={confirmAction} onOpenChange={(open) => { if (!open) setConfirmAction(null) }} />
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  description,
  helpText,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  description?: ReactNode
  helpText?: string | null
}) {
  const id = useId()
  const fieldDescription = description ?? null
  const infoTitle = helpText ?? null

  return (
    <Field>
      <Input id={id} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      <FieldLabel htmlFor={id} className={fieldCaptionClassName}>
        {label}
        {infoTitle ? (
          <InfoTooltip label={infoTitle} />
        ) : null}
      </FieldLabel>
      {fieldDescription ? <FieldDescription>{fieldDescription}</FieldDescription> : null}
    </Field>
  )
}
