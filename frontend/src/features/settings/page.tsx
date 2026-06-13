import { useEffect, useState } from 'react'
import { useI18n } from '@/app/providers/I18nProvider'
import { PageHeader } from '@/components/common/PageHeader'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RulesPanel } from '@/features/rules/panel'
import { FoldersPanel } from './folders/panel'
import { MaintenancePanel } from './maintenance/panel'
import { ProvidersPanel } from './providers/panel'
import { asSettingsTab, defaultSettingsTab, replaceSettingsHash, settingsTabFromHash, type SettingsTab } from './tabs'

export function SettingsPage() {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<SettingsTab>(() => settingsTabFromHash() ?? defaultSettingsTab)

  useEffect(() => {
    const syncTabFromHash = () => {
      const tab = settingsTabFromHash()
      if (!tab) return
      setActiveTab(tab)
    }
    syncTabFromHash()
    window.addEventListener('hashchange', syncTabFromHash)
    return () => window.removeEventListener('hashchange', syncTabFromHash)
  }, [])

  const changeTab = (value: string) => {
    const tab = asSettingsTab(value)
    setActiveTab(tab)
    replaceSettingsHash(tab)
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('navSettings')} />
      <Tabs value={activeTab} onValueChange={changeTab} className="flex flex-col gap-4">
        <TabsList className="!grid !h-10 !w-full grid-cols-4 gap-1 border-b pb-0 sm:!flex sm:!w-fit sm:flex-wrap sm:justify-start" variant="line">
          <TabsTrigger className="h-9 min-w-0 px-1.5 text-[0.7rem] after:bottom-0 sm:w-44 sm:flex-none sm:px-4 sm:text-sm" value="folders">{t('foldersTab')}</TabsTrigger>
          <TabsTrigger className="h-9 min-w-0 px-1.5 text-[0.7rem] after:bottom-0 sm:w-44 sm:flex-none sm:px-4 sm:text-sm" value="rules">{t('rulesTab')}</TabsTrigger>
          <TabsTrigger className="h-9 min-w-0 px-1.5 text-[0.7rem] after:bottom-0 sm:w-44 sm:flex-none sm:px-4 sm:text-sm" value="providers">{t('providersTab')}</TabsTrigger>
          <TabsTrigger className="h-9 min-w-0 px-1.5 text-[0.7rem] after:bottom-0 sm:w-44 sm:flex-none sm:px-4 sm:text-sm" value="maintenance">{t('maintenanceTab')}</TabsTrigger>
        </TabsList>
        <TabsContent value="folders">
          <FoldersPanel />
        </TabsContent>
        <TabsContent value="rules">
          <RulesPanel />
        </TabsContent>
        <TabsContent value="providers">
          <ProvidersPanel />
        </TabsContent>
        <TabsContent value="maintenance">
          <MaintenancePanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
