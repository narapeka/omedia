import type { OrganizeSession, OriginSummary, SourceCandidate } from '@/api/types'
import { sourceDisplayName } from '../display'

export function organizeAcceptedSummary(reviewCandidates: SourceCandidate[]) {
  const acceptedSourceIds = new Set<string>()
  const acceptedFiles = new Map<string, number>()
  let acceptedPlanItemCount = 0

  for (const sourceCandidate of reviewCandidates) {
    const fileSizeById = new Map(sourceCandidate.files.map((file) => [file.id, file.size_bytes ?? 0]))
    for (const planItem of sourceCandidate.plan_items) {
      if (planItem.user_decision !== 'accept') continue

      acceptedPlanItemCount += 1
      acceptedSourceIds.add(sourceCandidate.id)
      if (!acceptedFiles.has(planItem.source_file_id)) {
        acceptedFiles.set(planItem.source_file_id, planItem.source_size ?? fileSizeById.get(planItem.source_file_id) ?? 0)
      }
    }
  }

  return {
    sources: acceptedSourceIds.size,
    files: acceptedFiles.size,
    size: Array.from(acceptedFiles.values()).reduce((sum, size) => sum + size, 0),
    planItems: acceptedPlanItemCount,
  }
}

export function scannedSelectionSummary(reviewCandidates: SourceCandidate[]) {
  const acceptedCandidates = reviewCandidates.filter(
    (sourceCandidate) =>
      sourceCandidate.status === 'active' && sourceCandidate.selection_decision === 'accept',
  )
  return {
    sources: acceptedCandidates.length,
    files: acceptedCandidates.reduce((sum, sourceCandidate) => sum + sourceCandidate.active_file_count, 0),
    size: acceptedCandidates.reduce((sum, sourceCandidate) => sum + (sourceCandidate.active_total_size ?? 0), 0),
    planItems: 0,
  }
}

export function originSessionTitle(session: OrganizeSession, origins: OriginSummary[]) {
  const origin = origins.find(
    (item) =>
      item.path === session.path &&
      item.media_type === session.media_type,
  )
  return origin?.name?.trim() || sourceDisplayName(session.path)
}

