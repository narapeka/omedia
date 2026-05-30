import { X } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { formatDateTime } from '@/lib/valueFormat'
import { activityStatusBadgeClass, areaBadgeClass, type HistoryContextRow, type HistoryItem } from './rows'

export function HistoryDetailPanel({ item, onClose }: { item: HistoryItem | null; onClose: () => void }) {
  const { locale, t } = useI18n()
  if (!item) return null

  return (
    <aside
      aria-label={t('historyDetails')}
      className="min-h-0 min-w-0 overflow-y-auto rounded-xl border bg-card text-card-foreground"
    >
      <div className="flex items-start justify-between gap-3 border-b p-4">
        <div className="min-w-0">
          <h2 className="truncate font-heading text-base leading-snug font-medium">{item.event}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {item.area} - {item.result} - {formatDateTime(item.occurredAt, locale)}
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={t('closeHistoryDetails')}>
          <X />
        </Button>
      </div>
      <div className="flex flex-col gap-5 p-4">
        <div className="flex flex-wrap gap-2">
          <Badge className={areaBadgeClass(item.raw.area)}>{item.area}</Badge>
          <Badge className={activityStatusBadgeClass(item.tone)}>{item.result}</Badge>
        </div>
        <DetailSection title={t('summary')} rows={[
          { label: t('source'), value: item.sourceTitle },
          { label: t('target'), value: item.targetTitle },
          { label: t('summary'), value: item.summary },
          { label: t('status'), value: item.result },
        ]} />
        <DetailSection title={t('detailsTitle')} rows={formatDetailRows(item.contextRows, locale)} />
      </div>
    </aside>
  )
}

function DetailSection({ title, rows }: { title: string; rows: HistoryContextRow[] }) {
  const visibleRows = rows.filter((row) => row.value)
  if (!visibleRows.length) return null
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-medium">{title}</h2>
      <dl className="grid gap-2 text-sm">
        {visibleRows.map((row) => (
          <div key={`${row.label}:${row.value}`} className="grid gap-1 rounded-md border bg-muted/20 p-2">
            <dt className="text-xs text-muted-foreground">{row.label}</dt>
            <dd className="break-all">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function formatDetailRows(rows: HistoryContextRow[], locale: string) {
  return rows.map((row) => ({
    ...row,
    value: isIsoDate(row.value) ? formatDateTime(row.value, locale) : row.value,
  }))
}

function isIsoDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}T/.test(value)
}
