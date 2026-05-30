import type { BadgeTone } from '@/components/common/Badge'

export type PipelineRow = {
  id: string
  originName: string
  originPath: string
  organizeType: string
  organizeRuleName: string
  depotName: string
  depotPath: string
  depotMediaType: string | null | undefined
  depotIsIncremental: boolean
  transferType: string
  transferRuleName: string
  libraryPath: string
}

export type OrganizeOverview = {
  rows: OrganizeActivityRow[]
  moved: number
  unknown: number
  failed: number
  manualActionCount: number
}

export type OrganizeActivityRow = {
  id: string
  source: string
  sourceTitle: string
  type: string
  result: string
  statusValue: string
  tone?: BadgeTone
  destination: string
  destinationTitle: string
  updatedAt: string
}

export type TransferOverview = {
  rows: TransferOverviewRow[]
}

export type TransferOverviewRow = {
  id: string
  depot: string
  type: string
  statusValue: string
  tone?: BadgeTone
  result: string
  destination: string
  destinationTitle: string
  updatedAt: string
}
