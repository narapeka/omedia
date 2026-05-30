import { Database, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function PruneOperationsCard({
  clearing,
  pruning,
  onClearTmdbCache,
  onPruneHistory,
}: {
  clearing: boolean
  pruning: boolean
  onClearTmdbCache: () => void
  onPruneHistory: () => void
}) {
  const { t } = useI18n()
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>{t('systemOperations')}</CardTitle>
        <CardDescription>{t('systemOperationsDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="flex h-full flex-col gap-4">
        <MaintenanceActionBlock title={t('clearTmdbCache')} description={t('clearTmdbCacheDescription')}>
          <Button className="w-full" variant="danger" onClick={onClearTmdbCache} disabled={clearing}>
            <Trash2 data-icon="inline-start" />
            {t('clearTmdbCache')}
          </Button>
        </MaintenanceActionBlock>
        <MaintenanceActionBlock title={t('pruneOperationHistory')} description={t('pruneOperationHistoryDescription')}>
          <Button className="w-full" variant="danger" onClick={onPruneHistory} disabled={pruning}>
            <Database data-icon="inline-start" />
            {t('pruneHistoryAction')}
          </Button>
        </MaintenanceActionBlock>
      </CardContent>
    </Card>
  )
}

export function MaintenanceActionBlock({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 p-4">
      <div className="space-y-1">
        <h3 className="font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  )
}

