import { useState } from 'react'
import { AlertTriangle, MousePointer2 } from 'lucide-react'
import { confidenceLabel } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import type { CandidateMatch } from '@/api/types'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { isRecord, metadataTitle, metadataYear, stringValue } from '../display'

export function TmdbIdentityLink({
  match,
  mediaType,
}: {
  match: CandidateMatch
  mediaType: 'movie' | 'tv'
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const tmdbId = tmdbIdFromMatch(match)
  const title = metadataTitle(match.metadata)
  const year = metadataYear(match.metadata)
  const titleWithYear = year ? `${title} (${year})` : title
  const label = tmdbId ? `${titleWithYear} {tmdb-${tmdbId}}` : titleWithYear
  if (!tmdbId) return <Badge>{label}</Badge>
  const tmdbUrl = `https://www.themoviedb.org/${mediaType === 'tv' ? 'tv' : 'movie'}/${tmdbId}`

  return (
    <>
      <button
        type="button"
        aria-label={t('tmdbDetailsFor', { label })}
        className="inline-flex h-5 min-w-0 max-w-[min(24rem,100%)] items-center justify-center gap-1 overflow-hidden truncate rounded-4xl border border-border px-2 py-0.5 text-xs font-medium whitespace-nowrap text-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        title={label}
        onClick={() => setOpen(true)}
      >
        <span className="truncate">{label}</span>
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[840px]">
          <DialogHeader>
            <DialogTitle>{t('tmdbDetails')}</DialogTitle>
            <DialogDescription>{label}</DialogDescription>
          </DialogHeader>
          <TmdbIdentitySummary match={match} tmdbId={tmdbId} />
          <DialogFooter>
            <Button variant="primary" asChild>
              <a
                href={tmdbUrl}
                rel="noreferrer"
                target="_blank"
              >
                <MousePointer2 data-icon="inline-start" />
                {t('visitTmdb')}
              </a>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function TmdbIdentitySummary({
  match,
  tmdbId,
}: {
  match: CandidateMatch
  tmdbId: string
}) {
  const { t } = useI18n()
  const title = metadataTitle(match.metadata)
  const year = metadataYear(match.metadata)
  const originalTitle = metadataText(match.metadata, 'original_title') ?? metadataText(match.metadata, 'original_name')
  const overview = metadataText(match.metadata, 'overview')
  const posterUrl = metadataText(match.metadata, 'poster_url')
  const voteAverage = metadataNumber(match.metadata, 'vote_average')
  const popularity = metadataNumber(match.metadata, 'popularity')
  const secondaryParts = [
    originalTitle && originalTitle !== title ? originalTitle : undefined,
  ].filter(Boolean)

  return (
    <Card size="sm">
      <CardContent>
        <div className="grid w-full gap-4 text-left sm:grid-cols-[auto_minmax(0,1fr)] sm:items-stretch">
          {posterUrl ? (
            <div className="flex aspect-[2/3] h-full min-h-36 max-h-44 items-center justify-center overflow-hidden rounded-md bg-muted">
              <img src={posterUrl} alt="" className="h-full w-full object-contain" />
            </div>
          ) : (
            <div className="flex aspect-[2/3] h-full min-h-36 max-h-44 items-center justify-center rounded-md bg-muted text-xs text-muted-foreground">
              {t('noPoster')}
            </div>
          )}
          <div className="min-w-0">
            <div className="flex min-w-0 items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="truncate font-medium">{title}</span>
                  {year ? <span className="shrink-0 text-sm text-muted-foreground">{year}</span> : null}
                </div>
              </div>
              {voteAverage != null || popularity != null ? (
                <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                  {voteAverage != null ? <Badge>{t('voteValue', { value: voteAverage.toFixed(1) })}</Badge> : null}
                  {popularity != null ? <Badge>{t('popularityValue', { value: Math.round(popularity) })}</Badge> : null}
                </div>
              ) : null}
            </div>
            {secondaryParts.length ? <div className="mt-1 truncate text-sm text-muted-foreground">{secondaryParts.join(' · ')}</div> : null}
            {overview ? <div className="mt-3 line-clamp-4 text-sm leading-relaxed text-muted-foreground">{overview}</div> : null}
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>{t('tmdbIdWithValue', { id: tmdbId })}</span>
              <span>{match.metadata_source === 'manual_override' ? t('manualOverride') : t('automaticIdentify')}</span>
              <span>{confidenceLabel(t, match.confidence)}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function MoveReviewWarning({ count, labels }: { count: number; labels: string[] }) {
  const { t } = useI18n()
  const summary = t('moveNeedsReview', { count })
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            aria-label={summary}
            className="inline-flex size-5 items-center justify-center rounded-full text-amber-500"
            role="img"
          >
            <AlertTriangle className="size-4" />
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <span>{labels.length ? labels.slice(0, 3).join(' | ') : summary}</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function tmdbIdFromMatch(match: CandidateMatch) {
  if (isRecord(match.metadata)) {
    const direct = stringValue(match.metadata.tmdb_id)
    if (direct) return direct
    const selected = stringValue(match.metadata.selected_external_id)
    const fromExternal = selected?.match(/^tmdb:(\d+)$/)
    if (fromExternal) return fromExternal[1]
  }
  return match.manual_override_tmdb_id ?? null
}

function metadataText(metadata: unknown, key: string) {
  if (!isRecord(metadata)) return undefined
  return stringValue(metadata[key])
}

function metadataNumber(metadata: unknown, key: string) {
  if (!isRecord(metadata)) return null
  const value = metadata[key]
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}
