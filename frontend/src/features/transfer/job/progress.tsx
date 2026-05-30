import type { TransferJob } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'

export function TransferProgressLine({ status }: { status: TransferJob['status'] }) {
  const { t } = useI18n()
  const label = status === 'cancelling' ? t('cancellingTransferProgress') : t('transferProgress')

  return (
    <div
      aria-label={label}
      aria-valuetext={t('inProgress')}
      className="h-1 overflow-hidden bg-muted/40"
      role="progressbar"
    >
      <div className="omedia-indeterminate-progress h-full w-[44%] rounded-full bg-primary" />
    </div>
  )
}

