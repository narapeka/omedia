import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { useI18n } from '@/app/providers/I18nProvider'
import type { IdentifySearchResult, SourceCandidate } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { InfoTooltip } from '@/components/common/InfoTooltip'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { notifyError } from '@/lib/notifications'
import { useSessionActions } from '../api'
import { buildSearchSignature, formatOriginCountries, formatPeople, parseYear, searchSeed, uniqueTextParts } from './model'

type TmdbSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId: string
  mediaType: 'movie' | 'tv'
  sourceCandidate: SourceCandidate
}

export function TmdbSearchDialog({ open, onOpenChange, sessionId, mediaType, sourceCandidate }: TmdbSearchDialogProps) {
  const { t } = useI18n()
  const actions = useSessionActions()
  const [query, setQuery] = useState('')
  const [year, setYear] = useState('')
  const [showPrefilledYearChip, setShowPrefilledYearChip] = useState(false)
  const [selectedTmdbId, setSelectedTmdbId] = useState<number | null>(null)
  const [lastSearchSignature, setLastSearchSignature] = useState<string | null>(null)

  const seed = useMemo(() => searchSeed(sourceCandidate), [sourceCandidate])
  const response = actions.searchTmdb.data
  const results = response?.results ?? []
  const currentPage = response?.page ?? 1
  const totalPages = response?.total_pages ?? 0
  const canPageBack = currentPage > 1
  const canPageForward = totalPages > currentPage
  const title = mediaType === 'tv' ? t('changeShow') : t('changeMovie')
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))
  const searchSignature = buildSearchSignature(query, year)
  const showSearchAction = !response || searchSignature !== lastSearchSignature

  useEffect(() => {
    if (!open) return
    setQuery(seed.query)
    setYear(seed.year)
    setShowPrefilledYearChip(Boolean(seed.year))
    setSelectedTmdbId(null)
    setLastSearchSignature(null)
    actions.searchTmdb.reset()
    actions.applySourceCandidateTmdbOverride.reset()
  }, [open, seed])

  const runSearch = (page = 1) => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) return
    actions.searchTmdb.mutate(
      {
        sessionId,
        data: {
          source_candidate_id: sourceCandidate.id,
          query: trimmedQuery,
          year: parseYear(year),
          language: null,
          page,
        },
      },
      {
        onSuccess: () => {
          setLastSearchSignature(buildSearchSignature(trimmedQuery, year))
          setSelectedTmdbId(null)
        },
        onError: onActionError,
      },
    )
  }

  const applySelected = () => {
    if (!selectedTmdbId) return
    actions.applySourceCandidateTmdbOverride.mutate(
      {
        sessionId,
        candidateId: sourceCandidate.id,
        data: { tmdb_id: selectedTmdbId },
      },
      {
        onSuccess: () => onOpenChange(false),
        onError: onActionError,
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[min(860px,calc(100vh-1rem))] grid-rows-[auto_auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-[840px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{sourceCandidate.display_name}</DialogDescription>
        </DialogHeader>

        <FieldGroup>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_120px]">
            <Field>
              <div className="flex w-fit items-center gap-1.5">
                <FieldLabel htmlFor="tmdb-search-query">{t('searchLabel')}</FieldLabel>
                <InfoTooltip label={t('tmdbSearchHelpLabel')}>{t('tmdbSearchHelp')}</InfoTooltip>
              </div>
              <Input
                id="tmdb-search-query"
                aria-label={t('searchLabel')}
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') runSearch(1)
                }}
              />
            </Field>
            <Field>
              <FieldLabel>{t('year')}</FieldLabel>
              <YearInput
                value={year}
                showChip={showPrefilledYearChip}
                onChange={(value) => setYear(value)}
                onClearChip={() => {
                  setYear('')
                  setShowPrefilledYearChip(false)
                }}
              />
            </Field>
          </div>
        </FieldGroup>

        <div className="min-h-0 overflow-y-auto p-1">
          <div className="flex flex-col gap-3">
            {results.map((result) => (
              <TmdbResultCard
                key={`${result.media_type}-${result.tmdb_id}`}
                result={result}
                selected={selectedTmdbId === result.tmdb_id}
                onSelect={() => setSelectedTmdbId(result.tmdb_id)}
              />
            ))}
            {actions.searchTmdb.isPending ? <div className="py-8 text-center text-sm text-muted-foreground">{t('searching')}</div> : null}
            {!actions.searchTmdb.isPending && response && results.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">{t('noTmdbResults')}</div>
            ) : null}
          </div>

          {response && (canPageBack || canPageForward) ? (
            <div className="mt-3 flex items-center justify-between gap-3 text-sm text-muted-foreground">
              <span>
                {t('pageOf', { page: currentPage, total: totalPages || currentPage })}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => runSearch(currentPage - 1)} disabled={!canPageBack || actions.searchTmdb.isPending}>
                  <ChevronLeft data-icon="inline-start" />
                  {t('previous')}
                </Button>
                <Button variant="outline" onClick={() => runSearch(currentPage + 1)} disabled={!canPageForward || actions.searchTmdb.isPending}>
                  {t('next')}
                  <ChevronRight data-icon="inline-end" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          {showSearchAction ? (
            <Button variant="primary" className="min-w-28" onClick={() => runSearch(1)} disabled={actions.searchTmdb.isPending || !query.trim()}>
              <Search data-icon="inline-start" />
              {t('searchLabel')}
            </Button>
          ) : (
            <Button variant="primary" className="min-w-28" onClick={applySelected} disabled={!selectedTmdbId || actions.applySourceCandidateTmdbOverride.isPending}>
              <Check data-icon="inline-start" />
              {t('applySelected')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function YearInput({
  value,
  showChip,
  onChange,
  onClearChip,
}: {
  value: string
  showChip: boolean
  onChange: (value: string) => void
  onClearChip: () => void
}) {
  const { t } = useI18n()
  if (showChip && value) {
    return (
      <div
        role="group"
        aria-label={t('year')}
        className="flex h-8 w-full items-center rounded-lg border border-input bg-transparent px-2.5 dark:bg-input/30"
      >
        <span className="inline-flex max-w-full items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-sm text-foreground">
          <span className="truncate">{value}</span>
          <button
            type="button"
            aria-label={t('clearYear')}
            className="rounded-sm text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
            onClick={onClearChip}
          >
            <X className="size-3.5" />
          </button>
        </span>
      </div>
    )
  }
  return <Input aria-label={t('year')} value={value} inputMode="numeric" onChange={(event) => onChange(event.target.value)} />
}

function TmdbResultCard({
  result,
  selected,
  onSelect,
}: {
  result: IdentifySearchResult
  selected: boolean
  onSelect: () => void
}) {
  const { locale, t } = useI18n()
  const originCountries = formatOriginCountries(result.origin_country, locale)
  const directors = formatPeople(result.directors)
  const cast = formatPeople(result.cast, 4)
  const secondaryParts = uniqueTextParts([
    result.original_title && result.original_title !== result.title ? result.original_title : undefined,
    originCountries,
  ])
  return (
    <Card
      size="sm"
      className={selected ? 'bg-primary/15 ring-2 ring-inset ring-primary/70' : 'transition-colors hover:bg-muted/30'}
    >
      <CardContent>
        <button
          type="button"
          className="grid w-full gap-4 text-left sm:grid-cols-[auto_minmax(0,1fr)] sm:items-stretch"
          aria-pressed={selected}
          onClick={onSelect}
        >
          <Poster result={result} />
          <div className="min-w-0">
            <div className="flex min-w-0 items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="truncate font-medium">{result.title}</span>
                  {result.year ? <span className="shrink-0 text-sm text-muted-foreground">{result.year}</span> : null}
                </div>
              </div>
              {result.vote_average != null || result.popularity != null ? (
                <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                  {result.vote_average != null ? <Badge>{t('voteValue', { value: result.vote_average.toFixed(1) })}</Badge> : null}
                  {result.popularity != null ? <Badge>{t('popularityValue', { value: Math.round(result.popularity) })}</Badge> : null}
                </div>
              ) : null}
            </div>
            {secondaryParts.length ? <div className="mt-1 truncate text-sm text-muted-foreground">{secondaryParts.join(' · ')}</div> : null}
            {result.overview ? <div className="mt-3 line-clamp-4 text-sm leading-relaxed text-muted-foreground">{result.overview}</div> : null}
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>{t('tmdbIdWithValue', { id: result.tmdb_id })}</span>
              {directors ? <span>{t('directorValue', { value: directors })}</span> : null}
              {cast ? <span>{t('castValue', { value: cast })}</span> : null}
            </div>
          </div>
        </button>
      </CardContent>
    </Card>
  )
}

function Poster({ result }: { result: IdentifySearchResult }) {
  const { t } = useI18n()
  if (result.poster_url) {
    return (
      <div className="flex aspect-[2/3] h-full min-h-36 max-h-44 items-center justify-center overflow-hidden rounded-md bg-muted">
        <img src={result.poster_url} alt="" className="h-full w-full object-contain" />
      </div>
    )
  }
  return (
    <div className="flex aspect-[2/3] h-full min-h-36 max-h-44 items-center justify-center rounded-md bg-muted text-xs text-muted-foreground">
      {t('noPoster')}
    </div>
  )
}
