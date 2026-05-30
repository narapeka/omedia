import { useMemo } from 'react'
import { mediaTypeLabel, reasonLabel, statusLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { SelectControl } from '@/components/common/SelectControl'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import type { ActivityFilterDraft, HistoryTimeRangeFilter } from './model'
import { actionOptionLabel, activityActions, activityAreaOptions, activityReasons, activityStatuses, timeFilters } from './model'

export function AdvancedFilters({
  filters,
  origins,
  setFilter,
  depots,
}: {
  filters: ActivityFilterDraft
  origins: Array<{ id: string; name?: string | null }>
  depots: Array<{ id: string; name?: string | null }>
  setFilter: (patch: Partial<ActivityFilterDraft>) => void
}) {
  const { t } = useI18n()
  const timeFilterOptions = useMemo(
    () => [
      ...timeFilters.map((item) => ({ value: item.value, label: t(item.labelKey) })),
      { value: 'custom', label: t('customRange') },
    ],
    [t],
  )

  return (
    <FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Field>
        <FieldLabel>{t('area')}</FieldLabel>
        <SelectControl
          value={filters.area}
          onValueChange={(area) => setFilter({ area, group: '' })}
          options={activityAreaOptions(t)}
        />
      </Field>
      <Field>
        <FieldLabel>{t('actions')}</FieldLabel>
        <SelectControl
          value={filters.action}
          onValueChange={(action) => setFilter({ action })}
          options={activityActions.map((value) => ({ value, label: value ? actionOptionLabel(t, value) : t('any') }))}
        />
      </Field>
      <Field>
        <FieldLabel>{t('status')}</FieldLabel>
        <SelectControl
          value={filters.status}
          onValueChange={(status) => setFilter({ status })}
          options={activityStatuses.map((value) => ({ value, label: value ? statusLabel(t, value) : t('any') }))}
        />
      </Field>
      <Field>
        <FieldLabel>{t('reason')}</FieldLabel>
        <SelectControl
          value={filters.reason}
          onValueChange={(reason) => setFilter({ reason })}
          options={activityReasons.map((value) => ({ value, label: value ? reasonLabel(t, value) : t('any') }))}
        />
      </Field>
      <Field>
        <FieldLabel>{t('historyTimeRange')}</FieldLabel>
        <SelectControl
          value={filters.timeRange}
          onValueChange={(timeRange) => setFilter({ timeRange: timeRange as HistoryTimeRangeFilter })}
          options={timeFilterOptions}
        />
      </Field>
      {filters.timeRange === 'custom' ? (
        <>
          <Field>
            <FieldLabel htmlFor="history-from">{t('from')}</FieldLabel>
            <Input id="history-from" type="date" value={filters.from} onChange={(event) => setFilter({ from: event.target.value, timeRange: 'custom' })} />
          </Field>
          <Field>
            <FieldLabel htmlFor="history-to">{t('to')}</FieldLabel>
            <Input id="history-to" type="date" value={filters.to} onChange={(event) => setFilter({ to: event.target.value, timeRange: 'custom' })} />
          </Field>
        </>
      ) : null}
      <Field>
        <FieldLabel>{t('origin')}</FieldLabel>
        <SelectControl
          value={filters.originId}
          onValueChange={(originId) => setFilter({ originId })}
          options={[
            { value: '', label: t('any') },
            ...origins.map((origin) => ({ value: origin.id, label: origin.name })),
          ]}
        />
      </Field>
      <Field>
        <FieldLabel>{t('depot')}</FieldLabel>
        <SelectControl
          value={filters.depotId}
          onValueChange={(depotId) => setFilter({ depotId })}
          options={[
            { value: '', label: t('any') },
            ...depots.map((depot) => ({ value: depot.id, label: depot.name })),
          ]}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="activity-library-path">{t('libraryPath')}</FieldLabel>
        <Input id="activity-library-path" value={filters.libraryPath} onChange={(event) => setFilter({ libraryPath: event.target.value })} />
      </Field>
      <Field>
        <FieldLabel>{t('mediaType')}</FieldLabel>
        <SelectControl
          value={filters.mediaType}
          onValueChange={(mediaType) => setFilter({ mediaType })}
          options={[
            { value: '', label: t('any') },
            { value: 'movie', label: mediaTypeLabel(t, 'movie') },
            { value: 'tv', label: mediaTypeLabel(t, 'tv') },
          ]}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="activity-tmdb-id">{t('tmdbId')}</FieldLabel>
        <Input id="activity-tmdb-id" value={filters.tmdbId} onChange={(event) => setFilter({ tmdbId: event.target.value })} />
      </Field>
    </FieldGroup>
  )
}
