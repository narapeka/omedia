import { useState } from 'react'
import { ArrowRight, ChevronDown, ChevronUp } from 'lucide-react'
import type { TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForStatus, type BadgeColor } from '@/components/common/Badge'
import { IconButton } from '@/components/common/IconButton'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIs2xl } from '@/lib/useMediaQuery'
import { formatDateTime } from '@/lib/valueFormat'
import type { TransferOverview } from './types'
import { OverviewDetailLine } from './shared'

export function TransferOverviewCard({ overview }: { overview: TransferOverview }) {
  const { locale, t } = useI18n()
  const is2xl = useIs2xl()
  const [tableOpen, setTableOpen] = useState(true)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ArrowRight />
          {t('transferOverviewTitle')}
        </CardTitle>
        <CardAction>
          <IconButton
            aria-controls="transfer-overview-activity-table"
            aria-expanded={tableOpen}
            label={tableOpen ? t('collapseLabel', { label: t('transferActivityTable') }) : t('expandLabel', { label: t('transferActivityTable') })}
            type="button"
            onClick={() => setTableOpen((current) => !current)}
          >
            {tableOpen ? <ChevronUp /> : <ChevronDown />}
          </IconButton>
        </CardAction>
        <CardDescription>{t('transferOverviewDescription')}</CardDescription>
      </CardHeader>
      {tableOpen ? (
        <CardContent>
          <div id="transfer-overview-activity-table" className="max-h-[34rem] overflow-auto pr-1">
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
                  <TableHead>{t('depot')}</TableHead>
                  <TableHead className="px-1.5">{t('type')}</TableHead>
                  <TableHead className="px-1.5">{t('result')}</TableHead>
                  <TableHead>{t('library')}</TableHead>
                  <TableHead>{t('updated')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {overview.rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="truncate" title={row.depot}>{row.depot}</TableCell>
                    <TableCell className="px-1.5"><Badge color={triggerBadgeColor(row.type, t)}>{row.type}</Badge></TableCell>
                    <TableCell className="px-1.5"><Badge color={badgeColorForStatus(row.statusValue, row.tone)}>{row.result}</Badge></TableCell>
                    <TableCell className="truncate" title={row.destinationTitle}>{row.destination}</TableCell>
                    <TableCell>{formatDateTime(row.updatedAt, locale)}</TableCell>
                  </TableRow>
                ))}
                {overview.rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-muted-foreground">
                      {t('noRecentTransferActivity')}
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
                      label={t('depot')}
                      title={row.depot}
                      value={row.depot}
                      valueClassName="omedia-activity-path-value font-medium leading-5"
                    />
                    <OverviewDetailLine
                      className="grid-cols-[2.5rem_minmax(0,1fr)] gap-1 text-xs sm:grid-cols-[2.75rem_minmax(0,1fr)] sm:text-sm"
                      label={t('library')}
                      title={row.destinationTitle}
                      value={row.destination}
                      valueClassName="omedia-activity-path-value font-medium leading-5"
                    />
                  </div>
                </div>
              ))}
              {overview.rows.length === 0 ? <div className="text-muted-foreground">{t('noRecentTransferActivity')}</div> : null}
            </div>
            )}
          </div>
        </CardContent>
      ) : null}
    </Card>
  )
}

function triggerBadgeColor(label: string, t: TFunction): BadgeColor | undefined {
  if (label === t('triggerWatch')) return 'cyan'
  if (label === t('triggerManual')) return 'purple'
  if (label === t('triggerScheduled')) return 'pink'
  return undefined
}
