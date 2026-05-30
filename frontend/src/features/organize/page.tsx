import { useMemo, useState } from 'react'
import { FolderOpen, ScanLine } from 'lucide-react'
import { mediaTypeLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { BulkSessionItemResult } from '@/api/types'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { PageHeader } from '@/components/common/PageHeader'
import { SelectControl } from '@/components/common/SelectControl'
import { DirectoryPickerDialog } from '@/components/filesystem/DirectoryPickerDialog'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useDepots } from '@/features/depot/api'
import { useOrigins } from '@/features/origin/api'
import { isManualOrigin } from '@/features/origin/model'
import { useOrganizeRules } from '@/features/rules/api'
import { notificationMessage, notifyError, notifyWarning } from '@/lib/notifications'
import { useIs2xl } from '@/lib/useMediaQuery'
import { useOrganizeSessions, useSessionActions } from './api'
import { LauncherModeButton, ManualOriginPicker, depotOptionIncrementalLabel, depotOptionLabel, depotTriggerLabel } from './launcher'
import { adHocLauncherSummary, compareOriginsForPicker, manualOriginSelectionSummary } from './model'
import { SessionCard } from './session/card'

export function OrganizePage() {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  const origins = useOrigins()
  const depots = useDepots()
  const organizeRules = useOrganizeRules()
  const sessions = useOrganizeSessions()
  const actions = useSessionActions()
  const [selectedOriginIds, setSelectedOriginIds] = useState<string[]>([])
  const [launcherMode, setLauncherMode] = useState<'origin' | 'ad-hoc'>('origin')
  const [sourcePath, setSourcePath] = useState('')
  const [sourcePathPickerOpen, setSourcePathPickerOpen] = useState(false)
  const [depotId, setDepotId] = useState('')
  const [organizeRuleId, setOrganizeRuleId] = useState('')

  const manualOrigins = useMemo(
    () => (origins.data ?? []).filter(isManualOrigin),
    [origins.data],
  )
  const sortedManualOrigins = useMemo(
    () => [...manualOrigins].sort(compareOriginsForPicker),
    [manualOrigins],
  )
  const eligibleManualOriginIds = useMemo(
    () => manualOrigins.filter((origin) => origin.enabled).map((origin) => origin.id),
    [manualOrigins],
  )
  const selectedDepot = (depots.data ?? []).find((depot) => depot.id === depotId)
  const originNameById = useMemo(
    () => new Map((origins.data ?? []).map((origin) => [origin.id, origin.name])),
    [origins.data],
  )
  const depotNameById = useMemo(
    () => new Map((depots.data ?? []).map((depot) => [depot.id, depot.name])),
    [depots.data],
  )
  const depotById = useMemo(
    () => new Map((depots.data ?? []).map((depot) => [depot.id, depot])),
    [depots.data],
  )
  const selectedManualOriginIds = selectedOriginIds.filter((id) => eligibleManualOriginIds.includes(id))
  const selectedManualOrigins = manualOrigins.filter((origin) => selectedManualOriginIds.includes(origin.id))
  const launcherSummary = launcherMode === 'origin'
    ? manualOriginSelectionSummary(selectedManualOrigins, t)
    : adHocLauncherSummary(sourcePath, selectedDepot, t)
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))
  const notifyBulkScanIssues = (results: BulkSessionItemResult[]) => {
    const issues = results.filter((result) => result.status !== 'created')
    if (!issues.length) return
    const description = issues
      .slice(0, 4)
      .map((result) => `${originNameById.get(result.origin_id) ?? t('origin')}: ${notificationMessage(result.code ? { code: result.code, message: result.message, details: result.details } : result.message ?? result.status, result.status)}`)
      .join('\n')
    notifyWarning(t('partial'), description)
  }
  const scanAdHocSource = () => {
    if (!selectedDepot) return
    actions.createSession.mutate(
      {
        source_path: sourcePath,
        media_type: selectedDepot.media_type,
        policy: { target_depot_id: selectedDepot.id, organize_rule_id: organizeRuleId || null },
      },
      { onError: onActionError },
    )
  }
  const scanManualOrigins = () => {
    actions.createSessionsBulk.mutate(
      { origin_ids: selectedManualOriginIds },
      {
        onError: onActionError,
        onSuccess: (response) => notifyBulkScanIssues(response.results ?? []),
      },
    )
  }
  const scanDisabled =
    launcherMode === 'origin'
      ? selectedManualOriginIds.length === 0 || actions.createSessionsBulk.isPending
      : !sourcePath || !selectedDepot || actions.createSession.isPending
  const scanAction = launcherMode === 'origin' ? scanManualOrigins : scanAdHocSource

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('navOrganize')} />
      <div className="flex flex-col gap-4">
        <Card>
          <CardContent>
            <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-center">
              <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between 2xl:flex-1">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <div className="inline-flex rounded-lg bg-muted/70 p-0.5" role="group" aria-label={t('organizeType')}>
                    <LauncherModeButton
                      active={launcherMode === 'origin'}
                      onClick={() => setLauncherMode('origin')}
                    >
                      {t('manualOrigins')}
                    </LauncherModeButton>
                    <LauncherModeButton
                      active={launcherMode === 'ad-hoc'}
                      onClick={() => setLauncherMode('ad-hoc')}
                    >
                      {t('adHocSource')}
                    </LauncherModeButton>
                  </div>
                  <div className="min-w-0 truncate text-sm text-muted-foreground" title={launcherSummary}>
                    {launcherSummary}
                  </div>
                </div>
                {!is2xl ? (
                  <Button
                    aria-label={launcherMode === 'origin' ? t('scanSelectedOrigins') : undefined}
                    className="w-full shrink-0 bg-sky-200 text-sky-950 hover:bg-sky-100 disabled:bg-muted disabled:text-muted-foreground sm:w-32 dark:bg-sky-200 dark:text-sky-950 dark:hover:bg-sky-100"
                    onClick={scanAction}
                    disabled={scanDisabled}
                  >
                    <ScanLine data-icon="inline-start" />
                    {t('scan')}
                  </Button>
                ) : null}
              </div>
              <div className={`grid w-full min-w-0 grid-cols-1 items-center gap-2 2xl:ml-auto 2xl:grid-cols-[minmax(0,1fr)_8rem] ${launcherMode === 'ad-hoc' ? '2xl:w-[60%]' : '2xl:w-1/2'}`}>
                {launcherMode === 'origin' ? (
                  <ManualOriginPicker
                    ariaLabel={t('manualOrigins')}
                    className="h-8 min-h-8 w-full flex-nowrap overflow-hidden"
                    origins={sortedManualOrigins}
                    selectedOriginIds={selectedManualOriginIds}
                    depotById={depotById}
                    onValueChange={setSelectedOriginIds}
                  />
                ) : (
                  <div className="grid min-w-0 grid-cols-1 items-center gap-2 2xl:grid-cols-[minmax(18rem,1.8fr)_minmax(13rem,0.9fr)_minmax(12rem,0.75fr)]">
                    <div className="min-w-0">
                      <div className="flex h-8 min-w-0 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
                        <Input
                          id="organize-ad-hoc-source-path"
                          aria-label={t('sourcePath')}
                          className="h-full min-w-0 flex-1 rounded-none border-0 bg-transparent px-3 focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent"
                          placeholder={t('sourcePath')}
                          value={sourcePath}
                          onChange={(event) => setSourcePath(event.target.value)}
                        />
                        <Button
                          type="button"
                          className="h-full w-20 rounded-none border-y-0 border-l border-r-0 border-input bg-transparent px-3 hover:bg-muted/70 focus-visible:ring-0"
                          variant="ghost"
                          onClick={() => setSourcePathPickerOpen(true)}
                        >
                          <FolderOpen data-icon="inline-start" />
                          {t('select')}
                        </Button>
                      </div>
                    </div>
                    <div className="min-w-0">
                      <SelectControl
                        id="organize-ad-hoc-target-depot"
                        value={depotId}
                        onValueChange={setDepotId}
                        placeholder={t('targetDepot')}
                        triggerAriaLabel={t('targetDepot')}
                        triggerClassName="w-full"
                        triggerLabel={selectedDepot ? depotTriggerLabel(selectedDepot, t) : undefined}
                        options={(depots.data ?? []).map((depot) => ({
                          value: depot.id,
                          label: depotOptionLabel(depot, t),
                          disabled: !depot.enabled,
                          textValue: `${mediaTypeLabel(t, depot.media_type)} ${depot.name} ${depotOptionIncrementalLabel(depot, t)} ${depot.path}`,
                        }))}
                      />
                    </div>
                    <div className="min-w-0">
                      <SelectControl
                        id="organize-ad-hoc-organize-rule"
                        value={organizeRuleId}
                        onValueChange={setOrganizeRuleId}
                        placeholder={t('organizeRules')}
                        triggerAriaLabel={t('organizeRules')}
                        triggerClassName="w-full"
                        options={[
                          { value: '', label: t('none') },
                          ...(organizeRules.data ?? []).map((rule) => ({ value: rule.id, label: rule.name })),
                        ]}
                      />
                    </div>
                  </div>
                )}
                {is2xl ? (
                  <Button
                    aria-label={launcherMode === 'origin' ? t('scanSelectedOrigins') : undefined}
                    className="w-32 bg-sky-200 text-sky-950 hover:bg-sky-100 disabled:bg-muted disabled:text-muted-foreground dark:bg-sky-200 dark:text-sky-950 dark:hover:bg-sky-100"
                    onClick={scanAction}
                    disabled={scanDisabled}
                  >
                    <ScanLine data-icon="inline-start" />
                    {t('scan')}
                  </Button>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
        <DirectoryPickerDialog
          open={sourcePathPickerOpen}
          title={t('chooseOriginSource')}
          description={t('browseOriginSource')}
          initialPath={sourcePath}
          confirmLabel={t('useAsSource')}
          onOpenChange={setSourcePathPickerOpen}
          onSelect={setSourcePath}
        />
        <AsyncFrame loading={sessions.isLoading} error={sessions.error || origins.error || depots.error || organizeRules.error}>
          <div className="flex flex-col gap-4">
            {(sessions.data ?? []).map((session) => (
              <SessionCard key={session.id} session={session} origins={origins.data ?? []} depotNameById={depotNameById} />
            ))}
            {(sessions.data ?? []).length === 0 ? (
              <Card>
                <CardContent className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {t('noActiveOrganizeSessions')}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </AsyncFrame>
      </div>
    </div>
  )
}
