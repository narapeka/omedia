import { Link } from '@tanstack/react-router'
import { RotateCw, Settings } from 'lucide-react'
import { useMemo } from 'react'
import type { TransferJob, WatchStatus } from '@/api/types'
import { useHealth } from '@/app/health/api'
import { statusLabel, type TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useActivity } from '@/features/activity/api'
import { useDepots } from '@/features/depot/api'
import { useOrganizeSessions } from '@/features/organize/api'
import { useOrigins } from '@/features/origin/api'
import { useOrganizeRules, useTransferRules } from '@/features/rules/api'
import { useWatchStatus } from '@/features/services/api'
import { useTransferJobs } from '@/features/transfer/api'
import { buildDepotConfigurationModel } from '@/features/depot/model'
import { ConfigMetric } from './metric'
import { buildOrganizeAttention, buildOrganizeOverview, buildPipelineRows, buildTransferOverview } from './model'
import { OrganizeOverviewCard } from './organize'
import { PipelineOverviewCard } from './pipeline'
import { TransferOverviewCard } from './transfer'

type MetricBadge = { label: string; className?: string }

const METRIC_BADGE_CLASS = {
  running: 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  queued: 'border-sky-500/30 bg-sky-500/15 text-sky-700 dark:text-sky-300',
  idle: 'border-cyan-500/30 bg-cyan-500/15 text-cyan-700 dark:text-cyan-300',
  stopped: 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300',
  error: 'border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/20',
} as const

export function DashboardPage() {
  const { t } = useI18n()
  const health = useHealth()
  const origins = useOrigins()
  const depots = useDepots()
  const organizeRules = useOrganizeRules()
  const transferRules = useTransferRules()
  const sessions = useOrganizeSessions({ poll: false })
  const transferJobs = useTransferJobs()
  const watchStatus = useWatchStatus()
  const activity = useActivity()

  const depotModel = useMemo(
    () =>
      buildDepotConfigurationModel({
        origins: origins.data ?? [],
        depots: depots.data ?? [],
        organizeRules: organizeRules.data ?? [],
        transferRules: transferRules.data ?? [],
        t,
        transferJobs: transferJobs.data ?? [],
      }),
    [origins.data, organizeRules.data, depots.data, t, transferJobs.data, transferRules.data],
  )

  const organizeAttention = useMemo(() => buildOrganizeAttention(sessions.data ?? []), [sessions.data])
  const organizeOverview = useMemo(
    () => buildOrganizeOverview(activity.data?.items ?? [], organizeAttention.sessions, t),
    [activity.data, organizeAttention.sessions, t],
  )
  const pipelineRows = useMemo(
    () => buildPipelineRows(depotModel.depots, organizeRules.data ?? [], t),
    [depotModel.depots, organizeRules.data, t],
  )
  const transferOverview = useMemo(
    () => buildTransferOverview(t, activity.data?.items ?? []),
    [activity.data, t],
  )
  const configuredRules = (health.data?.organize_rules ?? 0) + (health.data?.transfer_rules ?? 0)

  const refresh = () => {
    void Promise.all([
      health.refetch(),
      origins.refetch(),
      depots.refetch(),
      organizeRules.refetch(),
      transferRules.refetch(),
      sessions.refetch(),
      transferJobs.refetch(),
      watchStatus.refetch(),
      activity.refetch(),
    ])
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t('navDashboard')}
        actions={
          <Button onClick={refresh} disabled={health.isFetching || origins.isFetching || depots.isFetching || sessions.isFetching || transferJobs.isFetching || watchStatus.isFetching}>
            <RotateCw data-icon="inline-start" />
            {t('refresh')}
          </Button>
        }
      />
      <AsyncFrame
        loading={health.isLoading || origins.isLoading || depots.isLoading || sessions.isLoading || transferJobs.isLoading || watchStatus.isLoading || activity.isLoading}
        error={health.error || origins.error || depots.error || sessions.error || transferJobs.error || watchStatus.error || activity.error}
      >
        {(health.data?.origins ?? 0) === 0 && (health.data?.depots ?? 0) === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>{t('dashboardEmptyTitle')}</CardTitle>
              <CardDescription>
                {t('dashboardEmptyDescription')}
              </CardDescription>
            </CardHeader>
            <CardFooter>
              <Button asChild>
                <Link to="/settings">
                  <Settings data-icon="inline-start" />
                  {t('openSettings')}
                </Link>
              </Button>
            </CardFooter>
          </Card>
        ) : null}

        <div className="grid grid-cols-6 gap-2 md:gap-3 2xl:grid-cols-5">
          <ConfigMetric className="col-span-2 md:col-span-2 2xl:col-span-1" label={t('metricConfiguredOrigins')} value={health.data?.origins ?? 0} to="/settings" hash="folders" />
          <ConfigMetric className="col-span-2 md:col-span-2 2xl:col-span-1" label={t('metricConfiguredDepots')} value={health.data?.depots ?? 0} to="/settings" hash="folders" />
          <ConfigMetric className="col-span-2 md:col-span-2 2xl:col-span-1" label={t('metricConfiguredRules')} value={configuredRules} to="/settings" hash="rules" />
          <ConfigMetric
            badge={watchMetricBadge(watchStatus.data, t)}
            className="col-span-3 md:col-span-3 2xl:col-span-1"
            label={t('metricWatchedFolders')}
            value={health.data?.watched_folders ?? 0}
            to="/services"
            hash="watch"
          />
          <ConfigMetric
            badge={transferMetricBadge(transferJobs.data ?? [], t)}
            className="col-span-3 md:col-span-3 2xl:col-span-1"
            label={t('metricScheduledTransfers')}
            value={health.data?.scheduled_transfers ?? 0}
            to="/services"
            hash="scheduled-transfer"
          />
        </div>

        <PipelineOverviewCard rows={pipelineRows} />

        <div className="flex min-w-0 flex-col gap-4">
          <OrganizeOverviewCard overview={organizeOverview} />
          <TransferOverviewCard overview={transferOverview} />
        </div>
      </AsyncFrame>
    </div>
  )
}

function watchMetricBadge(status: WatchStatus | undefined, t: TFunction): MetricBadge | undefined {
  if (!status?.state) return undefined
  const style = status.state === 'running' ? METRIC_BADGE_CLASS.running : status.state === 'error' ? METRIC_BADGE_CLASS.error : METRIC_BADGE_CLASS.stopped
  return {
    label: statusLabel(t, status.state) || status.state,
    className: style,
  }
}

function transferMetricBadge(jobs: TransferJob[], t: TFunction): MetricBadge {
  const running = jobs.filter((job) => job.status === 'running' || job.status === 'cancelling').length
  const queued = jobs.filter((job) => job.status === 'queued').length
  if (running > 0) {
    return {
      label: `${statusLabel(t, 'running') || 'running'} ${running}/${running + queued}`,
      className: METRIC_BADGE_CLASS.running,
    }
  }
  if (queued > 0) {
    return {
      label: `${statusLabel(t, 'queued') || 'queued'} ${queued}`,
      className: METRIC_BADGE_CLASS.queued,
    }
  }
  return {
    label: statusLabel(t, 'idle') || 'idle',
    className: METRIC_BADGE_CLASS.idle,
  }
}
