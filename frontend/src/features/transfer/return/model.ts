import type { DepotCandidateFile, DepotCandidate } from '@/api/types'

export type ReturnTarget =
  | { type: 'candidate'; candidate: DepotCandidate }
  | { type: 'file'; candidate: DepotCandidate; file: DepotCandidateFile }

export function returnRequestForTarget(target: ReturnTarget, destinationRoot: string) {
  return target.type === 'candidate'
    ? { candidate_ids: [target.candidate.id], relative_paths: [], destination_root: destinationRoot }
    : { candidate_ids: [], relative_paths: [target.file.relative_path], destination_root: destinationRoot }
}

export function parentPath(path: string) {
  const trimmed = path.replace(/[\\/]+$/, '')
  const separator = trimmed.includes('\\') ? '\\' : '/'
  const index = trimmed.lastIndexOf(separator)
  if (index <= 0) return trimmed
  return trimmed.slice(0, index)
}

