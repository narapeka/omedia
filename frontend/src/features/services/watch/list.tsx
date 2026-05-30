import { statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForStatus, type BadgeColor } from '@/components/common/Badge'
import { PathRoute } from '@/components/filesystem/PathRoute'
import { useIs2xl } from '@/lib/useMediaQuery'
import { formatDateTime } from '@/lib/valueFormat'
import type { AutomationActivityItem } from './activity'

export function AutomationActivityList({ items }: { items: AutomationActivityItem[] }) {
  const { locale, t } = useI18n()
  const is2xl = useIs2xl()
  if (items.length === 0) {
    return <div className="px-4 py-6 text-sm text-muted-foreground">{t('noRecentAutomationActivity')}</div>
  }

  return (
    <div className="divide-y">
      {items.slice(0, 10).map((item) => (
        <div key={item.id} className="px-4 py-3 text-sm">
          {is2xl ? (
          <div className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2">
            <Badge color={automationSourceBadgeColor(item.source, t)}>{item.source}</Badge>
            <Badge color={badgeColorForStatus(item.status)}>{statusLabel(t, item.status)}</Badge>
            <div className="min-w-0">
              <div className="truncate font-medium" title={item.title}>{item.title}</div>
              <ActivityDetail detail={item.detail} />
            </div>
            <div className="text-xs text-muted-foreground">{formatDateTime(item.createdAt, locale)}</div>
          </div>
          ) : (
          <div>
            <div className="grid min-w-0 grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2">
              <Badge color={automationSourceBadgeColor(item.source, t)}>{item.source}</Badge>
              <Badge color={badgeColorForStatus(item.status)}>{statusLabel(t, item.status)}</Badge>
              <div className="min-w-0 truncate font-medium" title={item.title}>{item.title}</div>
              <time className="shrink-0 text-xs text-muted-foreground">{formatDateTime(item.createdAt, locale)}</time>
            </div>
            <ActivityDetailRows detail={item.detail} />
          </div>
          )}
        </div>
      ))}
    </div>
  )
}

function automationSourceBadgeColor(label: string, t: ReturnType<typeof useI18n>['t']): BadgeColor | undefined {
  if (label === t('watch')) return 'cyan'
  if (label === t('transfer')) return 'pink'
  return undefined
}

function ActivityDetailRows({ detail }: { detail: string }) {
  const { t } = useI18n()
  const separator = ' -> '
  const separatorIndex = detail.indexOf(separator)
  if (separatorIndex < 0) {
    return (
      <div className="mt-2 grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-1 text-xs">
        <span className="text-muted-foreground">{t('details')}</span>
        <span className="min-w-0 truncate text-muted-foreground" title={detail}>{detail}</span>
      </div>
    )
  }

  const source = detail.slice(0, separatorIndex)
  const target = detail.slice(separatorIndex + separator.length)
  return (
    <div className="mt-2 grid gap-1 text-xs">
      <div className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-1">
        <span className="text-muted-foreground">{t('source')}</span>
        <span className="min-w-0 truncate text-muted-foreground" title={source}>{source}</span>
      </div>
      <div className="grid min-w-0 grid-cols-[2.75rem_minmax(0,1fr)] gap-1">
        <span className="text-muted-foreground">{t('target')}</span>
        <span className="min-w-0 truncate text-muted-foreground" title={target}>{target}</span>
      </div>
    </div>
  )
}

function ActivityDetail({ detail }: { detail: string }) {
  const separator = ' -> '
  const separatorIndex = detail.indexOf(separator)
  if (separatorIndex < 0) {
    return <div className="truncate text-xs text-muted-foreground" title={detail}>{detail}</div>
  }

  return (
    <div className="min-w-0 overflow-hidden text-xs text-muted-foreground" title={detail}>
      <PathRoute
        source={detail.slice(0, separatorIndex)}
        target={detail.slice(separatorIndex + separator.length)}
        truncate
        iconClassName="size-3"
      />
    </div>
  )
}
