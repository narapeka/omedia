import type { SourceCandidate } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { SourceCandidateSection } from './section'

export function SourceCandidateList({
  sourceCandidates,
  sessionId,
  mediaType,
  canReview,
  canSelectForIdentify,
  canInspectSource,
  canMutateSource,
  showModifiedTime,
}: {
  sourceCandidates: SourceCandidate[]
  sessionId: string
  mediaType: 'movie' | 'tv'
  canReview: boolean
  canSelectForIdentify: boolean
  canInspectSource: boolean
  canMutateSource: boolean
  showModifiedTime: boolean
}) {
  const { t } = useI18n()
  const visibleCandidates = sourceCandidates.filter((sourceCandidate) => sourceCandidate.status !== 'deleted')
  if (visibleCandidates.length === 0) {
    return <div className="py-8 text-sm text-muted-foreground">{t('noSourceCandidatesFound')}</div>
  }

  return (
    <div className="flex flex-col gap-4">
      {visibleCandidates.map((sourceCandidate) => (
        <SourceCandidateSection
          key={sourceCandidate.id}
          sourceCandidate={sourceCandidate}
          sessionId={sessionId}
          mediaType={mediaType}
          canReview={canReview}
          canSelectForIdentify={canSelectForIdentify}
          canInspectSource={canInspectSource}
          canMutateSource={canMutateSource}
          showModifiedTime={showModifiedTime}
        />
      ))}
    </div>
  )
}

