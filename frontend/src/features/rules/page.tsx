import { useI18n } from '@/app/providers/I18nProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { RulesPanel } from './panel'

export function RulesPage() {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('rulesTitle')} />
      <RulesPanel />
    </div>
  )
}

