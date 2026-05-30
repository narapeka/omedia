import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ScanLine } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent } from '@/components/ui/card'
import { depotKeys, useDepots } from '@/features/depot/api'
import { useTransferRules } from '@/features/rules/api'
import { useTransferJobs } from './api'
import { DepotTransferCard } from './depot/card'
import { TransferDepotMultiSelect } from './depot/picker'
import { buildDepotGroups, compareDepotsForPicker, manualDepotSelectionSummary, type DepotGroupView } from './depot/model'
import { AUTO_REMOVE_STATUSES, isActiveTransfer, mergeUnique } from './job/model'

export function TransferPage() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const jobs = useTransferJobs()
  const depots = useDepots()
  const transferRules = useTransferRules()
  const [selectedDepotIds, setSelectedDepotIds] = useState<string[]>([])
  const [visibleDepotIds, setVisibleDepotIds] = useState<string[]>([])
  const trackedJobByDepot = useRef(new Map<string, string>())

  const depotGroups = useMemo(
    () => buildDepotGroups({ depots: depots.data ?? [], jobs: jobs.data ?? [], t, transferRules: transferRules.data ?? [] }),
    [jobs.data, depots.data, t, transferRules.data],
  )
  const sortedDepotGroups = useMemo(
    () => [...depotGroups].sort(compareDepotsForPicker),
    [depotGroups],
  )
  const depotIdsKey = depotGroups.map((depot) => depot.id).join('|')
  const depotById = useMemo(() => new Map(depotGroups.map((depot) => [depot.id, depot])), [depotGroups])
  const selectedDepots = selectedDepotIds.map((id) => depotById.get(id)).filter(Boolean) as DepotGroupView[]
  const visibleDepots = visibleDepotIds.map((id) => depotById.get(id)).filter(Boolean) as DepotGroupView[]
  const transferRuleById = useMemo(() => new Map((transferRules.data ?? []).map((rule) => [rule.id, rule])), [transferRules.data])
  const selectedDepotSummary = manualDepotSelectionSummary(selectedDepots, t)

  const activeJobsKey = useMemo(
    () => (jobs.data ?? []).filter(isActiveTransfer).map((job) => `${job.id}:${job.depot_id}:${job.status}`).join('|'),
    [jobs.data],
  )
  const jobsStatusKey = useMemo(
    () => (jobs.data ?? []).map((job) => `${job.id}:${job.depot_id}:${job.status}`).join('|'),
    [jobs.data],
  )

  useEffect(() => {
    const validIds = new Set(depotGroups.map((depot) => depot.id))
    setSelectedDepotIds((current) => current.filter((id) => validIds.has(id)))
    setVisibleDepotIds((current) => current.filter((id) => validIds.has(id)))
  }, [depotIdsKey])

  useEffect(() => {
    const activeJobs = (jobs.data ?? []).filter(isActiveTransfer)
    if (!activeJobs.length) return
    const activeDepotIds = activeJobs.map((job) => {
      trackedJobByDepot.current.set(job.depot_id, job.id)
      return job.depot_id
    })
    setVisibleDepotIds((current) => mergeUnique(current, activeDepotIds))
    setSelectedDepotIds((current) => mergeUnique(current, activeDepotIds))
  }, [activeJobsKey, jobs.data])

  useEffect(() => {
    const jobsById = new Map((jobs.data ?? []).map((job) => [job.id, job]))
    const removeDepotIds = new Set<string>()

    trackedJobByDepot.current.forEach((jobId, depotId) => {
      const job = jobsById.get(jobId)
      if (!job || isActiveTransfer(job)) return
      void queryClient.invalidateQueries({ queryKey: depotKeys.detail(depotId) })
      void queryClient.invalidateQueries({ queryKey: depotKeys.all })
      trackedJobByDepot.current.delete(depotId)
      if (AUTO_REMOVE_STATUSES.has(job.status)) {
        removeDepotIds.add(depotId)
      }
    })

    if (removeDepotIds.size) {
      setVisibleDepotIds((current) => current.filter((id) => !removeDepotIds.has(id)))
    }
  }, [jobsStatusKey, jobs.data, queryClient])

  const scanSelectedDepots = () => {
    setVisibleDepotIds((current) => mergeUnique(current, selectedDepotIds))
  }
  const setDepotSelected = (depotId: string, selected: boolean) => {
    setSelectedDepotIds((current) => {
      if (selected) return current.includes(depotId) ? current : [...current, depotId]
      return current.filter((id) => id !== depotId)
    })
  }

  const removeDepotCard = (depotId: string) => {
    trackedJobByDepot.current.delete(depotId)
    setVisibleDepotIds((current) => current.filter((id) => id !== depotId))
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('navTransfer')} />
      <div className="flex flex-col gap-4">
        <Card>
          <CardContent>
            <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <div className="inline-flex shrink-0 rounded-lg bg-muted/70 p-0.5">
                    <span className="h-7 rounded-md bg-background px-2.5 py-1 text-sm font-medium whitespace-nowrap text-foreground shadow-sm ring-1 ring-border">
                      {t('manualDepots')}
                    </span>
                  </div>
                  <div className="min-w-0 truncate text-sm text-muted-foreground" title={selectedDepotSummary}>
                    {selectedDepotSummary}
                  </div>
                </div>
              </div>
              <div className="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_8rem] items-center gap-2 2xl:ml-auto 2xl:w-1/2">
                <TransferDepotMultiSelect
                  ariaLabel={t('manualDepots')}
                  className="h-8 min-h-8 w-full flex-nowrap overflow-hidden"
                  emptyLabel={t('noDepotsFound')}
                  depots={sortedDepotGroups}
                  placeholder={t('scanSelectedDepots')}
                  selectedDepotIds={selectedDepotIds}
                  onDepotSelected={setDepotSelected}
                />
                <Button
                  className="w-32 bg-sky-200 text-sky-950 hover:bg-sky-100 disabled:bg-muted disabled:text-muted-foreground dark:bg-sky-200 dark:text-sky-950 dark:hover:bg-sky-100"
                  onClick={scanSelectedDepots}
                  disabled={selectedDepotIds.length === 0}
                >
                  <ScanLine data-icon="inline-start" />
                  {t('scan')}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <AsyncFrame loading={jobs.isLoading || depots.isLoading || transferRules.isLoading} error={jobs.error || depots.error || transferRules.error}>
          <div className="flex flex-col gap-4">
            {visibleDepots.map((depot) => (
              <DepotTransferCard
                key={depot.id}
                depot={depot}
                jobs={jobs.data ?? []}
                transferRule={depot.transferRuleId ? transferRuleById.get(depot.transferRuleId) ?? null : null}
                onRemove={removeDepotCard}
              />
            ))}
            {visibleDepots.length === 0 ? (
              <Card>
                <CardContent className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {t('chooseDepotScanDescription')}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </AsyncFrame>
      </div>
    </div>
  )
}
