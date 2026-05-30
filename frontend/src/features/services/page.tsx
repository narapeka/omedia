import { Link } from '@tanstack/react-router'
import { Settings } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { PageHeader } from '@/components/common/PageHeader'
import { useActivity } from '@/features/activity/api'
import { useDepots } from '@/features/depot/api'
import { useOrigins } from '@/features/origin/api'
import { useOrganizeRules, useTransferRules } from '@/features/rules/api'
import { useWatchActions, useWatchChildren, useWatchSettings, useWatchStatus } from './api'
import { CollapsibleSection } from './section'
import { ScheduledTransferSection } from './schedule/section'
import { buildAutomationActivity } from './watch/activity'
import { WatchChildTable } from './watch/children'
import { WatchLauncherSection } from './watch/launcher'
import { AutomationActivityList } from './watch/list'
import { WatchSettingsDialog } from './watch/settings'

export function ServicesPage() {
  const { t } = useI18n()
  const watchSettings = useWatchSettings()
  const watchStatus = useWatchStatus()
  const watchChildren = useWatchChildren()
  const origins = useOrigins()
  const organizeRules = useOrganizeRules()
  const depots = useDepots()
  const transferRules = useTransferRules()
  const activity = useActivity({ group: 'automation', limit: 10 })
  const actions = useWatchActions()
  const [watchLauncherOpen, setWatchLauncherOpen] = useState(true)
  const [watchSettingsOpen, setWatchSettingsOpen] = useState(false)
  const [scheduledTransferOpen, setScheduledTransferOpen] = useState(true)
  const [activityOpen, setActivityOpen] = useState(true)

  useEffect(() => {
    const syncSectionFromHash = () => {
      if (window.location.hash === '#watch') setWatchLauncherOpen(true)
      if (window.location.hash === '#scheduled-transfer') setScheduledTransferOpen(true)
    }
    syncSectionFromHash()
    window.addEventListener('hashchange', syncSectionFromHash)
    return () => window.removeEventListener('hashchange', syncSectionFromHash)
  }, [])

  const recentAutomationActivity = useMemo(
    () => buildAutomationActivity(activity.data?.items ?? [], t),
    [activity.data, t],
  )

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t('navServices')}
        actions={
          <Button onClick={() => setWatchSettingsOpen(true)}>
            <Settings data-icon="inline-start" />
            {t('settings')}
          </Button>
        }
      />
      <WatchSettingsDialog open={watchSettingsOpen} onOpenChange={setWatchSettingsOpen} />

      <section id="watch">
        <WatchLauncherSection
          actions={actions}
          config={watchSettings.data}
          open={watchLauncherOpen}
          runtimeError={watchSettings.error || watchStatus.error}
          status={watchStatus.data}
          tableLoading={watchChildren.isLoading || origins.isLoading || organizeRules.isLoading || depots.isLoading}
          tableError={watchChildren.error || origins.error || organizeRules.error || depots.error}
          onOpenChange={setWatchLauncherOpen}
        >
          <WatchChildTable
            children={watchChildren.data ?? []}
            origins={origins.data ?? []}
            organizeRules={organizeRules.data ?? []}
            depots={depots.data ?? []}
            watchRunning={watchStatus.data?.state === 'running'}
          />
        </WatchLauncherSection>
      </section>

      <div className="flex flex-col gap-4">
        <AsyncFrame
          loading={depots.isLoading || transferRules.isLoading}
          error={depots.error || transferRules.error}
        >
          <section id="scheduled-transfer">
            <ScheduledTransferSection
              open={scheduledTransferOpen}
              depots={depots.data ?? []}
              transferRules={transferRules.data ?? []}
              onOpenChange={setScheduledTransferOpen}
            />
          </section>
        </AsyncFrame>

        <CollapsibleSection
          title={t('recentAutomationActivity')}
          description={t('recentAutomationActivityDescription')}
          open={activityOpen}
          onOpenChange={setActivityOpen}
          footer={
            <Button asChild variant="ghost">
              <Link to="/activity" search={{ group: 'automation' }}>
                {t('viewAutomationActivity')}
              </Link>
            </Button>
          }
        >
          <AsyncFrame loading={activity.isLoading} error={activity.error}>
            <AutomationActivityList items={recentAutomationActivity} />
          </AsyncFrame>
        </CollapsibleSection>
      </div>
    </div>
  )
}
