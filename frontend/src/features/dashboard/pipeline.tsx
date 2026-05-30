import { useState } from 'react'
import { ChevronDown, ChevronUp, Workflow } from 'lucide-react'
import { mediaTypeLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge, badgeColorForMediaType } from '@/components/common/Badge'
import { IconButton } from '@/components/common/IconButton'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIs2xl } from '@/lib/useMediaQuery'
import type { PipelineRow } from './types'
import { NamePath, OverviewDetailLine } from './shared'

export function PipelineOverviewCard({ rows }: { rows: PipelineRow[] }) {
  const { t } = useI18n()
  const is2xl = useIs2xl()
  const [tableOpen, setTableOpen] = useState(false)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Workflow />
          {t('pipelineOverviewTitle')}
        </CardTitle>
        <CardAction>
          <IconButton
            aria-controls="pipeline-overview-table"
            aria-expanded={tableOpen}
            label={tableOpen ? t('collapseLabel', { label: t('pipelineTable') }) : t('expandLabel', { label: t('pipelineTable') })}
            type="button"
            onClick={() => setTableOpen((current) => !current)}
          >
            {tableOpen ? <ChevronUp /> : <ChevronDown />}
          </IconButton>
        </CardAction>
        <CardDescription>{t('pipelineOverviewDescription')}</CardDescription>
      </CardHeader>
      {tableOpen ? (
        <CardContent className="overflow-hidden">
          <div id="pipeline-overview-table" className="max-h-[34rem] overflow-auto pr-1">
            {is2xl ? (
            <Table className="table-fixed">
              <colgroup>
                <col className="w-[23%]" />
                <col className="w-[6%]" />
                <col className="w-[8%]" />
                <col className="w-[6%]" />
                <col className="w-[20%]" />
                <col className="w-[6%]" />
                <col className="w-[8%]" />
                <col className="w-[23%]" />
              </colgroup>
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead>{t('origin')}</TableHead>
                  <TableHead>{t('organizeType')}</TableHead>
                  <TableHead>{t('organizeRule')}</TableHead>
                  <TableHead>{t('mediaType')}</TableHead>
                  <TableHead>{t('depot')}</TableHead>
                  <TableHead>{t('transferType')}</TableHead>
                  <TableHead>{t('transferRule')}</TableHead>
                  <TableHead>{t('library')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <NamePath name={row.originName} path={row.originPath} />
                    </TableCell>
                    <TableCell><Badge>{row.organizeType}</Badge></TableCell>
                    <TableCell className="max-w-[220px] truncate">{row.organizeRuleName}</TableCell>
                    <TableCell>
                      {row.depotMediaType ? (
                        <Badge color={badgeColorForMediaType(row.depotMediaType)}>
                          {mediaTypeLabel(t, row.depotMediaType)}
                        </Badge>
                      ) : <span className="text-muted-foreground">-</span>}
                    </TableCell>
                    <TableCell>
                      <NamePath
                        name={row.depotName}
                        path={row.depotPath}
                        suffix={row.depotIsIncremental ? <Badge className="border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">{t('resolveModeIncremental')}</Badge> : null}
                      />
                    </TableCell>
                    <TableCell><Badge>{row.transferType}</Badge></TableCell>
                    <TableCell className="max-w-[220px] truncate">{row.transferRuleName}</TableCell>
                    <TableCell className="truncate" title={row.libraryPath}>{row.libraryPath}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-muted-foreground">
                      {t('noPipelinesConfigured')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
            ) : (
            <div className="flex flex-col gap-3">
              {rows.map((row) => (
                <div key={row.id} className="relative rounded-lg border bg-muted/20 p-3">
                  {row.depotMediaType ? (
                    <Badge className="absolute right-3 top-3" color={badgeColorForMediaType(row.depotMediaType)}>
                      {mediaTypeLabel(t, row.depotMediaType)}
                    </Badge>
                  ) : null}
                  <div className="min-w-0 pr-16">
                    <NamePath
                      name={`${row.originName} -> ${row.depotName}`}
                      path={row.originPath}
                      suffix={row.depotIsIncremental ? <Badge className="border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">{t('resolveModeIncremental')}</Badge> : null}
                    />
                  </div>
                  <div className="mt-3 grid gap-2 text-sm">
                    <div className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-2">
                      <span className="text-muted-foreground">{t('depot')}</span>
                      <span className="min-w-0 truncate font-medium text-muted-foreground" title={row.depotPath}>{row.depotPath}</span>
                      <Badge>{row.organizeType}</Badge>
                    </div>
                    <div className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-2">
                      <span className="text-muted-foreground">{t('library')}</span>
                      <span className="min-w-0 truncate font-medium text-muted-foreground" title={row.libraryPath}>{row.libraryPath}</span>
                      <Badge>{row.transferType}</Badge>
                    </div>
                    <div className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)_4.5rem_minmax(0,1fr)] items-center gap-2">
                      <span className="text-muted-foreground">{t('organizeRule')}</span>
                      <span className="min-w-0 truncate font-medium text-muted-foreground" title={row.organizeRuleName}>{row.organizeRuleName}</span>
                      <span className="text-muted-foreground">{t('transferRule')}</span>
                      <span className="min-w-0 truncate font-medium text-muted-foreground" title={row.transferRuleName}>{row.transferRuleName}</span>
                    </div>
                  </div>
                </div>
              ))}
              {rows.length === 0 ? <div className="text-muted-foreground">{t('noPipelinesConfigured')}</div> : null}
            </div>
            )}
          </div>
        </CardContent>
      ) : null}
    </Card>
  )
}
