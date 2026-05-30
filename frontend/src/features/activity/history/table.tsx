import { Fragment, type KeyboardEvent } from 'react'
import type { TFunction } from '@/app/i18n/labels'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIs2xl } from '@/lib/useMediaQuery'
import { formatDateTime } from '@/lib/valueFormat'
import { activityStatusBadgeClass, areaBadgeClass, type HistoryItem } from './rows'

export function HistoryTable({
  items,
  selectedId,
  locale,
  loading,
  error,
  hasMore,
  fetching,
  onSelect,
  onLoadMore,
  t,
}: {
  items: HistoryItem[]
  selectedId: string | null
  locale: string
  loading: boolean
  error: unknown
  hasMore: boolean
  fetching: boolean
  onSelect: (itemId: string) => void
  onLoadMore: () => void
  t: TFunction
}) {
  const is2xl = useIs2xl()
  const selectOnKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, itemId: string) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    onSelect(itemId)
  }

  return (
    <AsyncFrame loading={loading} error={error}>
      <Card className="min-h-0 min-w-0">
        <CardContent className="min-h-0 flex-1 overflow-auto p-0">
          <Table className="table-fixed">
            <colgroup>
              <col className="w-28" />
              <col className="w-24" />
              <col className="w-52" />
              <col className="w-24" />
              {is2xl ? (
                <>
                  <col />
                  <col />
                </>
              ) : null}
            </colgroup>
            <TableHeader>
              <TableRow>
                <TableHead>{t('when')}</TableHead>
                <TableHead>{t('area')}</TableHead>
                <TableHead>{t('event')}</TableHead>
                <TableHead>{t('status')}</TableHead>
                {is2xl ? (
                  <>
                    <TableHead>{t('source')}</TableHead>
                    <TableHead>{t('target')}</TableHead>
                  </>
                ) : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <Fragment key={item.id}>
                  <TableRow
                    role="button"
                    tabIndex={0}
                    aria-label={t('openHistoryDetailsFor', { label: item.event })}
                    data-state={item.id === selectedId ? 'selected' : undefined}
                    className="h-11 cursor-pointer border-b-0 bg-muted/20 outline-none hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset 2xl:border-b 2xl:bg-transparent"
                    onClick={() => onSelect(item.id)}
                    onKeyDown={(event) => selectOnKeyDown(event, item.id)}
                  >
                    <TableCell className="whitespace-nowrap">{formatDateTime(item.occurredAt, locale)}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <div className="flex flex-nowrap gap-1">
                        <Badge className={areaBadgeClass(item.raw.area)}>{item.area}</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="truncate whitespace-nowrap">{item.event}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge className={activityStatusBadgeClass(item.tone)}>{item.result}</Badge>
                    </TableCell>
                    {is2xl ? (
                      <>
                        <TableCell className="truncate whitespace-nowrap" title={item.sourceTitle}>
                          {item.source}
                        </TableCell>
                        <TableCell className="truncate whitespace-nowrap" title={item.targetTitle}>
                          {item.target}
                        </TableCell>
                      </>
                    ) : null}
                  </TableRow>
                  {!is2xl ? (
                    <TableRow
                      data-state={item.id === selectedId ? 'selected' : undefined}
                      className="cursor-pointer hover:bg-transparent"
                      onClick={() => onSelect(item.id)}
                    >
                      <TableCell colSpan={4} className="pt-1 pb-3 whitespace-normal">
                        <div className="grid w-[calc(100vw-4rem)] max-w-full gap-2 text-xs text-muted-foreground sm:w-auto sm:gap-1">
                          <div className="grid min-w-0 grid-cols-1 gap-0.5 sm:grid-cols-[2.75rem_minmax(0,1fr)] sm:gap-1">
                            <span className="text-[0.7rem] leading-none sm:text-xs sm:leading-normal">{t('source')}</span>
                            <span className="omedia-activity-path-value text-muted-foreground" title={item.sourceTitle}>
                              {item.source}
                            </span>
                          </div>
                          <div className="grid min-w-0 grid-cols-1 gap-0.5 sm:grid-cols-[2.75rem_minmax(0,1fr)] sm:gap-1">
                            <span className="text-[0.7rem] leading-none sm:text-xs sm:leading-normal">{t('target')}</span>
                            <span className="omedia-activity-path-value text-muted-foreground" title={item.targetTitle}>
                              {item.target}
                            </span>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </Fragment>
              ))}
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={is2xl ? 6 : 4} className="text-muted-foreground">
                    {t('noHistoryMatches')}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
        {hasMore ? (
          <CardContent className="border-t py-3">
            <Button variant="outline" onClick={onLoadMore} disabled={fetching}>
              {t('loadMore')}
            </Button>
          </CardContent>
        ) : null}
      </Card>
    </AsyncFrame>
  )
}
