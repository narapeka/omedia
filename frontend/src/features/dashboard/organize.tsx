import { useState } from 'react'
import { ChevronDown, ChevronUp, FolderInput } from 'lucide-react'
import type { TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForStatus, type BadgeColor } from '@/components/common/Badge'
import { IconButton } from '@/components/common/IconButton'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIs2xl } from '@/lib/useMediaQuery'
import { formatDateTime } from '@/lib/valueFormat'
import type { OrganizeOverview } from './types'
import { OverviewDetailLine, OverviewStats } from './shared'

export function OrganizeOverviewCard({ overview }: { overview: OrganizeOverview }) {
  const { locale, t } = useI18n()
  const is2xl = useIs2xl()
  const [tableOpen, setTableOpen] = useState(false)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderInput />
          {t('organizeOverviewTitle')}
        </CardTitle>
        <CardAction>
          <IconButton
            aria-controls="organize-overview-activity-table"
            aria-expanded={tableOpen}
            label={tableOpen ? t('collapseLabel', { label: t('organizeActivityTable') }) : t('expandLabel', { label: t('organizeActivityTable') })}
            type="button"
            onClick={() => setTableOpen((current) => !current)}
          >
            {tableOpen ? <ChevronUp /> : <ChevronDown />}
          </IconButton>
        </CardAction>
        <CardDescription>{t('organizeOverviewDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <OverviewStats
          stats={[
            { label: t('organized'), value: overview.moved, to: '/activity', search: { group: 'organize' }, ariaLabel: t('openOrganizedHistory') },
            { label: t('unmatched'), value: overview.unknown, tone: overview.unknown ? 'warning' : undefined, to: '/activity', search: { focus: 'unmatched' }, ariaLabel: t('openUnmatchedHistory') },
            { label: t('failed'), value: overview.failed, tone: overview.failed ? 'danger' : undefined, to: '/activity', search: { group: 'organize', focus: 'failed' }, ariaLabel: t('openOrganizeFailedHistory') },
            { label: t('ongoing'), value: overview.manualActionCount, tone: overview.manualActionCount ? 'warning' : undefined, to: '/organize', ariaLabel: t('openOngoingOrganizeSessions') },
          ]}
        />
        {tableOpen ? (
          <div id="organize-overview-activity-table" className="max-h-[34rem] overflow-auto pr-1">
            {is2xl ? (
            <Table className="table-fixed">
              <colgroup>
                <col className="w-[42%]" />
                <col className="w-[5.5rem]" />
                <col className="w-[6rem]" />
                <col className="w-[35%]" />
                <col className="w-[6rem]" />
              </colgroup>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('source')}</TableHead>
                  <TableHead className="px-1.5">{t('type')}</TableHead>
                  <TableHead className="px-1.5">{t('result')}</TableHead>
                  <TableHead>{t('destination')}</TableHead>
                  <TableHead>{t('updated')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {overview.rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="truncate" title={row.sourceTitle}>{row.source}</TableCell>
                    <TableCell className="px-1.5"><Badge color={triggerBadgeColor(row.type, t)}>{row.type}</Badge></TableCell>
                    <TableCell className="px-1.5"><Badge color={badgeColorForStatus(row.statusValue, row.tone)}>{row.result}</Badge></TableCell>
                    <TableCell className="truncate" title={row.destinationTitle}>{row.destination}</TableCell>
                    <TableCell>{formatDateTime(row.updatedAt, locale)}</TableCell>
                  </TableRow>
                ))}
                {overview.rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-muted-foreground">
                      {t('noRecentOrganizeActivity')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
            ) : (
            <div className="flex flex-col gap-3">
              {overview.rows.map((row) => (
                <div key={row.id} className="rounded-lg border bg-muted/20 p-3">
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Badge color={triggerBadgeColor(row.type, t)}>{row.type}</Badge>
                      <Badge color={badgeColorForStatus(row.statusValue, row.tone)}>{row.result}</Badge>
                    </div>
                    <time className="shrink-0 text-sm text-muted-foreground">{formatDateTime(row.updatedAt, locale)}</time>
                  </div>
                  <div className="mt-3 grid gap-1.5">
                    <OverviewDetailLine
                      className="grid-cols-[2.5rem_minmax(0,1fr)] gap-1 text-xs sm:grid-cols-[2.75rem_minmax(0,1fr)] sm:text-sm"
                      label={t('source')}
                      title={row.sourceTitle}
                      value={row.source}
                      valueClassName="omedia-activity-path-value font-medium leading-5"
                    />
                    <OverviewDetailLine
                      className="grid-cols-[2.5rem_minmax(0,1fr)] gap-1 text-xs sm:grid-cols-[2.75rem_minmax(0,1fr)] sm:text-sm"
                      label={t('target')}
                      title={row.destinationTitle}
                      value={row.destination}
                      valueClassName="omedia-activity-path-value font-medium leading-5"
                    />
                  </div>
                </div>
              ))}
              {overview.rows.length === 0 ? <div className="text-muted-foreground">{t('noRecentOrganizeActivity')}</div> : null}
            </div>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function triggerBadgeColor(label: string, t: TFunction): BadgeColor | undefined {
  if (label === t('triggerWatch')) return 'cyan'
  if (label === t('triggerManual')) return 'purple'
  if (label === t('triggerScheduled')) return 'pink'
  return undefined
}
