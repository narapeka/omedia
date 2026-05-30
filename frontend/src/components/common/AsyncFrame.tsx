import type { ReactNode } from 'react'
import { Spinner } from '@/components/ui/spinner'
import { useI18n } from '@/app/providers/I18nProvider'
import { EmptyState } from './EmptyState'
import { errorMessage } from '@/lib/notifications'

export function AsyncFrame({ loading, error, children }: { loading?: boolean; error?: unknown; children: ReactNode }) {
  const { t } = useI18n()
  if (loading) {
    return (
      <div className="flex min-h-40 items-center justify-center gap-2 rounded-xl border bg-card p-8 text-sm text-muted-foreground">
        <Spinner />
        <span>{t('loading')}</span>
      </div>
    )
  }
  if (error) return <EmptyState label={errorMessage(error, t('requestFailed'))} />
  return <>{children}</>
}
