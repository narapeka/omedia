import type { ReactNode } from 'react'
import { ChevronDown, ChevronUp, Play, RotateCw, Square } from 'lucide-react'
import type { WatchSettings, WatchStatus } from '@/api/types'
import { statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage, notifyError } from '@/lib/notifications'
import { useWatchActions } from '../api'

type WatchActions = ReturnType<typeof useWatchActions>

export function WatchLauncherSection({
  actions,
  children,
  config,
  open,
  runtimeError,
  status,
  tableError,
  tableLoading,
  onOpenChange,
}: {
  actions: WatchActions
  children: ReactNode
  config?: WatchSettings | null
  open: boolean
  runtimeError?: unknown
  status?: WatchStatus
  tableError?: unknown
  tableLoading?: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const watchState = status?.state ?? 'stopped'
  const watchRunning = status?.state === 'running'
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  return (
    <Card className="overflow-visible">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              <CardTitle className="min-w-0 shrink-0 leading-7">{t('autoOrganize')}</CardTitle>
              <StatusBadge state={watchState} />
            </div>
            <CardDescription>
              {t('autoOrganizeDescription')}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center justify-start gap-2 xl:justify-end">
            <Button
              className="w-28 border-emerald-500/40 bg-emerald-500 text-emerald-950 hover:bg-emerald-400 disabled:border-border disabled:bg-muted disabled:text-muted-foreground dark:border-emerald-400/50 dark:bg-emerald-400 dark:text-emerald-950 dark:hover:bg-emerald-300"
              onClick={() => actions.startWatch.mutate(undefined, { onError: onActionError })}
              disabled={!config || watchRunning || actions.startWatch.isPending}
              variant="primary"
            >
              <Play data-icon="inline-start" />
              {t('start')}
            </Button>
            <Button
              className="w-28 border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20 disabled:border-border disabled:bg-muted disabled:text-muted-foreground"
              onClick={() => actions.stopWatch.mutate(undefined, { onError: onActionError })}
              disabled={!config || !watchRunning || actions.stopWatch.isPending}
              variant="outline"
            >
              <Square data-icon="inline-start" />
              {t('stop')}
            </Button>
            <Button
              className="w-28 border-amber-500/40 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 disabled:border-border disabled:bg-muted disabled:text-muted-foreground dark:text-amber-300"
              onClick={() => actions.restartWatch.mutate(undefined, { onError: onActionError })}
              disabled={!config || !watchRunning || actions.restartWatch.isPending}
              variant="outline"
            >
              <RotateCw data-icon="inline-start" />
              {t('restart')}
            </Button>
            <Button
              aria-expanded={open}
              aria-label={open ? t('collapseAutoOrganize') : t('expandAutoOrganize')}
              size="icon-sm"
              variant="ghost"
              onClick={() => onOpenChange(!open)}
            >
              {open ? <ChevronUp /> : <ChevronDown />}
            </Button>
          </div>
        </div>
        {runtimeError ? <div className="rounded-lg border border-destructive/30 px-3 py-2 text-sm text-destructive">{errorMessage(runtimeError, t('requestFailed'))}</div> : null}
      </CardHeader>
      {open ? (
        <CardContent className="p-0">
          {tableLoading ? (
            <div className="flex min-h-32 items-center justify-center gap-2 px-4 py-8 text-sm text-muted-foreground">
              <Spinner />
              <span>{t('loadingFoldersShort')}</span>
            </div>
          ) : tableError ? (
            <div className="px-4 py-6 text-sm text-destructive">{errorMessage(tableError, t('requestFailed'))}</div>
          ) : (
            children
          )}
        </CardContent>
      ) : null}
    </Card>
  )
}

function StatusBadge({ state }: { state: string }) {
  const { t } = useI18n()
  return (
    <Badge className={`h-[1.375rem] px-2.5 text-sm font-normal leading-none ${watchStatusClassName(state)}`}>
      {statusLabel(t, state) || state.toUpperCase()}
    </Badge>
  )
}

function watchStatusClassName(state: string) {
  if (state === 'running') return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
  if (state === 'error') return 'border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/20'
  return 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300'
}
