import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { RotateCcw, RotateCw, Search, SlidersHorizontal } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { ActivityEvent, ListActivityEventHistoryParams } from '@/api/types'
import { Button } from '@/components/common/Button'
import { PageHeader } from '@/components/common/PageHeader'
import { SelectControl } from '@/components/common/SelectControl'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useDepots } from '@/features/depot/api'
import { useOrigins } from '@/features/origin/api'
import { useActivity } from './api'
import { AdvancedFilters } from './filters/panel'
import {
  activityFiltersFromSearch,
  advancedFilterCount,
  buildActivityParams,
  cleanActivitySearch,
  emptyActivityFilters,
  hasActiveFilters,
  hasAdvancedActivityFilters,
  quickFilters,
  timeFilters,
  type ActivityFilterDraft,
  type HistoryTimeRangeFilter,
} from './filters/model'
import { HistoryDetailPanel } from './history/detail'
import { appendUniqueEvents } from './history/merge'
import { buildHistoryItems } from './history/rows'
import { HistoryTable } from './history/table'

const pageSize = 100
const filterToolbarControlClass = 'w-full 2xl:w-[8.25rem]'

export function ActivityPage() {
  const { locale, t } = useI18n()
  const search = useSearch({ from: '/activity' })
  const filters = useMemo(() => activityFiltersFromSearch(search), [search])
  const navigate = useNavigate({ from: '/activity' })
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [loadedEvents, setLoadedEvents] = useState<ActivityEvent[]>([])
  const [searchDraft, setSearchDraft] = useState(filters.q)
  const origins = useOrigins()
  const depots = useDepots()
  const baseActivityParams = useMemo<ListActivityEventHistoryParams>(
    () => buildActivityParams(filters),
    [filters],
  )
  const filterKey = useMemo(() => JSON.stringify(baseActivityParams), [baseActivityParams])
  const activityParams = useMemo<ListActivityEventHistoryParams>(
    () => ({ ...baseActivityParams, limit: pageSize, offset }),
    [baseActivityParams, offset],
  )
  const activity = useActivity(activityParams)
  useEffect(() => {
    setOffset(0)
    setLoadedEvents([])
    setSelectedId(null)
  }, [filterKey])
  useEffect(() => {
    setSearchDraft(filters.q)
  }, [filters.q])
  useEffect(() => {
    if (!activity.data) return
    setLoadedEvents((current) => {
      if (offset === 0) return activity.data.items
      return appendUniqueEvents(current, activity.data.items)
    })
  }, [activity.data, offset])
  const historyItems = useMemo(
    () =>
      buildHistoryItems({
        events: loadedEvents,
        t,
      }),
    [loadedEvents, t],
  )
  const selectedItem = historyItems.find((item) => item.id === selectedId) ?? null
  const advancedActive = hasAdvancedActivityFilters(filters)
  const filtersActive = hasActiveFilters(filters)
  const quickFilterKey =
    quickFilters.find((item) => filters.group === item.patch.group && filters.focus === item.patch.focus)?.key ?? 'custom'
  const quickFilterOptions = useMemo(
    () => [
      ...quickFilters.map((item) => ({ value: item.key, label: t(item.labelKey) })),
      ...(quickFilterKey === 'custom' ? [{ value: 'custom', label: t('custom'), disabled: true }] : []),
    ],
    [quickFilterKey, t],
  )
  const timeFilterOptions = useMemo(
    () => timeFilters.map((item) => ({ value: item.value, label: t(item.labelKey) })),
    [t],
  )

  const setFilter = (patch: Partial<ActivityFilterDraft>) => {
    void navigate({ search: cleanActivitySearch({ ...filters, ...patch }) })
  }
  const resetFilters = () => {
    setSelectedId(null)
    setSearchDraft('')
    void navigate({ search: cleanActivitySearch(emptyActivityFilters) })
  }
  const submitSearch = () => {
    setFilter({ q: searchDraft.trim() })
  }
  const submitSearchOnEnter = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' || event.nativeEvent.isComposing) return
    submitSearch()
  }
  const applyQuickFilter = (patch: Pick<ActivityFilterDraft, 'group' | 'focus'>) => {
    setFilter({
      group: patch.group,
      focus: patch.focus,
      area: '',
      action: '',
      status: '',
      reason: '',
      originId: '',
      depotId: '',
      libraryPath: '',
      mediaType: '',
      tmdbId: '',
    })
  }
  const applyQuickFilterByKey = (key: string) => {
    const filter = quickFilters.find((item) => item.key === key)
    if (!filter) return
    applyQuickFilter(filter.patch)
  }
  const applyTimeFilter = (timeRange: HistoryTimeRangeFilter) => {
    setFilter({ timeRange, from: '', to: '' })
  }
  const refreshActivity = () => {
    if (offset === 0) void activity.refetch()
    else setOffset(0)
  }
  return (
    <div className="flex h-[calc(100vh-3rem)] min-h-0 flex-col gap-5 overflow-hidden max-md:h-[calc(100vh-2rem)]">
      <PageHeader
        title={t('navActivity')}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button onClick={refreshActivity} disabled={activity.isFetching}>
              <RotateCw data-icon="inline-start" />
              {t('refresh')}
            </Button>
          </div>
        }
      />

      <Card>
        <CardContent>
          <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-center">
            <div className="flex min-w-0 2xl:w-[min(42rem,50%)] 2xl:shrink-0">
              <div className="flex h-8 min-w-0 flex-1 overflow-hidden rounded-lg border border-input bg-transparent transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="history-search"
                    className="h-full rounded-none border-0 bg-transparent pr-3 pl-9 focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent"
                    value={searchDraft}
                    onChange={(event) => setSearchDraft(event.target.value)}
                    onKeyDown={submitSearchOnEnter}
                    placeholder={t('activitySearchPlaceholder')}
                  />
                </div>
                <Button
                  type="button"
                  className="h-full w-24 rounded-none border-y-0 border-l border-r-0 border-input bg-transparent px-3 hover:bg-muted/70 focus-visible:ring-0"
                  variant="ghost"
                  onClick={submitSearch}
                  disabled={searchDraft.trim() === filters.q}
                >
                  <Search data-icon="inline-start" />
                  {t('searchLabel')}
                </Button>
              </div>
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-4 2xl:ml-auto 2xl:flex 2xl:flex-wrap 2xl:items-center 2xl:justify-end">
              <SelectControl
                aria-label={t('historyFocus')}
                value={quickFilterKey}
                onValueChange={applyQuickFilterByKey}
                options={quickFilterOptions}
                contentAlign="end"
                triggerClassName={`${filterToolbarControlClass} justify-between`}
              />
              <SelectControl
                aria-label={t('historyTimeRange')}
                value={filters.timeRange}
                onValueChange={(timeRange) => applyTimeFilter(timeRange as HistoryTimeRangeFilter)}
                options={timeFilterOptions}
                contentAlign="end"
                triggerClassName={`${filterToolbarControlClass} justify-between`}
              />
              <Button
                className={filterToolbarControlClass}
                variant="outline"
                onClick={resetFilters}
                disabled={!filtersActive && searchDraft.trim() === ''}
              >
                <RotateCcw data-icon="inline-start" />
                {t('reset')}
              </Button>
              <Button
                className={filterToolbarControlClass}
                variant={advancedOpen || advancedActive ? 'secondary' : 'outline'}
                onClick={() => setAdvancedOpen((value) => !value)}
                aria-expanded={advancedOpen}
              >
                <SlidersHorizontal data-icon="inline-start" />
                {advancedActive ? t('advancedWithCount', { count: advancedFilterCount(filters) }) : t('advanced')}
              </Button>
            </div>
          </div>
        </CardContent>
        {advancedOpen ? (
          <CardContent className="border-t pt-4">
            <AdvancedFilters filters={filters} origins={origins.data ?? []} depots={depots.data ?? []} setFilter={setFilter} />
          </CardContent>
        ) : null}
      </Card>

      <div className={cn('grid min-h-0 flex-1 gap-4 overflow-hidden', selectedItem && '2xl:grid-cols-[minmax(0,1fr)_minmax(320px,440px)]')}>
        <HistoryTable
          items={historyItems}
          selectedId={selectedId}
          locale={locale}
          loading={(activity.isLoading && loadedEvents.length === 0) || origins.isLoading || depots.isLoading}
          error={activity.error || origins.error || depots.error}
          hasMore={Boolean(activity.data?.has_more)}
          fetching={activity.isFetching}
          onSelect={setSelectedId}
          onLoadMore={() => setOffset((value) => value + pageSize)}
          t={t}
        />

        <HistoryDetailPanel item={selectedItem} onClose={() => setSelectedId(null)} />
      </div>
    </div>
  )
}
