import { useI18n } from '@/app/providers/I18nProvider'

export function SessionProgressLine({ state }: { state: 'scanning' | 'identifying' | 'organizing' }) {
  const { t } = useI18n()
  const label =
    state === 'scanning'
      ? t('scanningSessionProgress')
      : state === 'identifying'
        ? t('identifyingSessionProgress')
        : t('organizingSessionProgress')

  return (
    <div
      aria-label={label}
      aria-valuetext={t('inProgress')}
      className="h-1 overflow-hidden rounded-full bg-muted/40"
      role="progressbar"
    >
      <div className="omedia-indeterminate-progress h-full w-[44%] rounded-full bg-primary" />
    </div>
  )
}

