import type {
  OrganizeRule,
  OriginSummary,
  DepotSummary,
  ResolveMode,
  TransferJob,
  TransferRule,
  WatchSettingsChild,
  WatchSettings,
} from '@/api/types'
import { defaultT, categoryCountLabel, type TFunction } from '@/app/i18n/labels'

export type DepotHealthState = 'ready' | 'warning' | 'broken' | 'disabled'

export type OriginConfigurationView = OriginSummary & {
  watchDirectChild: boolean | null
  watchChildStatus: string | null
}

export type DepotConfigurationView = {
  id: string
  name: string
  mediaType: DepotSummary['media_type']
  resolveMode: DepotSummary['resolve_mode']
  enabled: boolean
  depot: DepotSummary
  origins: OriginConfigurationView[]
  manualOrigins: OriginConfigurationView[]
  watchOrigins: OriginConfigurationView[]
  depotPath: string
  libraryPath: string
  organizeRuleNames: string[]
  transferRuleName: string
  transferRuleSummary: string
  trigger: string
  schedule: string | null
  health: DepotHealthState
  issues: string[]
  busyTransfer: TransferJob | null
}

export type BrokenOriginView = OriginConfigurationView & {
  targetDepotId: string
  repairDepot: DepotSummary | null
}

export type DepotConfigurationModel = {
  depots: DepotConfigurationView[]
  brokenOrigins: BrokenOriginView[]
  counts: {
    configured: number
    disabled: number
    warning: number
    broken: number
    ready: number
    unlinkedDepots: number
    brokenOrigins: number
  }
}

export function buildDepotConfigurationModel({
  origins,
  depots,
  organizeRules,
  transferRules,
  watchSettings,
  watchChildren,
  t = defaultT,
  transferJobs = [],
}: {
  origins: OriginSummary[]
  depots: DepotSummary[]
  organizeRules: OrganizeRule[]
  transferRules: TransferRule[]
  watchSettings?: WatchSettings | null
  watchChildren?: WatchSettingsChild[]
  t?: TFunction
  transferJobs?: TransferJob[]
}): DepotConfigurationModel {
  const depotById = new Map(depots.map((depot) => [depot.id, depot]))
  const organizeRuleById = new Map(organizeRules.map((rule) => [rule.id, rule]))
  const transferRuleById = new Map(transferRules.map((rule) => [rule.id, rule]))
  const childByOriginId = new Map((watchChildren ?? []).filter((child) => child.origin_id).map((child) => [child.origin_id as string, child]))
  const activeJobByDepotId = new Map(transferJobs.filter(isActiveTransferJob).map((job) => [job.depot_id, job]))

  const originViews = origins.map((origin) => enrichOrigin(origin, watchSettings, childByOriginId))
  const brokenOrigins = originViews
    .filter((origin) => !depotById.has(origin.policy.target_depot_id))
    .map((origin) => ({
      ...origin,
      targetDepotId: origin.policy.target_depot_id,
      repairDepot: findRepairDepot(depots, origin),
    }))

  const depotViews = depots.map((depot) => {
    const linkedOrigins = originViews.filter((origin) => origin.policy.target_depot_id === depot.id)
    const manualOrigins = linkedOrigins.filter((origin) => origin.trigger === 'manual')
    const watchOrigins = linkedOrigins.filter((origin) => origin.trigger === 'watch')
    const issues = depotIssues(depot, linkedOrigins, t)
    const transferRule = depot.policy.transfer_rule_id ? transferRuleById.get(depot.policy.transfer_rule_id) : undefined
    const organizeRuleNames = summarizeOrganizeRules(linkedOrigins, organizeRuleById, t)
    const health = depotHealth(depot, issues, linkedOrigins)

    return {
      id: depot.id,
      name: depot.name,
      mediaType: depot.media_type,
      resolveMode: depot.resolve_mode,
      enabled: depot.enabled ?? true,
      depot,
      origins: linkedOrigins,
      manualOrigins,
      watchOrigins,
      depotPath: depot.path,
      libraryPath: depot.policy.target_library_path,
      organizeRuleNames,
      transferRuleName: transferRule?.name ?? depot.policy.transfer_rule_id ?? t('none'),
      transferRuleSummary: ruleSummary(transferRule, t),
      trigger: depot.policy.trigger ?? 'manual',
      schedule: depot.policy.schedule ?? null,
      health,
      issues,
      busyTransfer: activeJobByDepotId.get(depot.id) ?? null,
    }
  })

  return {
    depots: depotViews,
    brokenOrigins,
    counts: {
      configured: depotViews.length,
      disabled: depotViews.filter((depot) => depot.health === 'disabled').length,
      warning: depotViews.filter((depot) => depot.health === 'warning').length,
      broken: depotViews.filter((depot) => depot.health === 'broken').length,
      ready: depotViews.filter((depot) => depot.health === 'ready').length,
      unlinkedDepots: depotViews.filter((depot) => depot.origins.length === 0).length,
      brokenOrigins: brokenOrigins.length,
    },
  }
}

export function isWatchDirectChild(rootPath: string | null | undefined, originPath: string) {
  if (!rootPath) return false
  const normalizedRoot = normalizePath(rootPath)
  const normalizedOrigin = normalizePath(originPath)
  if (!normalizedOrigin.startsWith(`${normalizedRoot}/`)) return false
  const remainder = normalizedOrigin.slice(normalizedRoot.length + 1)
  return Boolean(remainder) && !remainder.includes('/')
}

export function ruleSummary(rule: OrganizeRule | TransferRule | undefined, t: TFunction) {
  if (!rule) return t('none')
  const categoryCount = rule.categories?.length ?? 0
  const fallback = rule.fallback_bucket ? `, ${t('fallback').toLocaleLowerCase()} ${rule.fallback_bucket}` : ''
  return `${categoryCountLabel(t, categoryCount)}${fallback}`
}

export function depotResolveMode(depot: Pick<DepotSummary, 'media_type' | 'resolve_mode'>): ResolveMode {
  return depot.media_type === 'tv' ? depot.resolve_mode ?? 'full' : 'full'
}

export function depotIsIncremental(depot: Pick<DepotSummary, 'media_type' | 'resolve_mode'>) {
  return depotResolveMode(depot) === 'incremental'
}

export function isActiveTransferJob(job: TransferJob) {
  return job.status === 'queued' || job.status === 'running' || job.status === 'cancelling'
}

function enrichOrigin(
  origin: OriginSummary,
  watchSettings: WatchSettings | null | undefined,
  childByOriginId: Map<string, WatchSettingsChild>,
): OriginConfigurationView {
  const child = childByOriginId.get(origin.id)
  return {
    ...origin,
    watchDirectChild: origin.trigger === 'watch' ? Boolean(child) || isWatchDirectChild(watchSettings?.path, origin.path) : null,
    watchChildStatus: child?.status ?? null,
  }
}

function depotIssues(depot: DepotSummary, origins: OriginConfigurationView[], t: TFunction) {
  const issues: string[] = []
  if (!depot.path) issues.push(t('depotPathMissing'))
  if (!depot.policy.target_library_path) issues.push(t('libraryTargetMissing'))
  if (origins.length === 0) issues.push(t('noOriginsFeedDepot'))
  const mediaMismatch = origins.filter((origin) => origin.media_type !== depot.media_type)
  if (mediaMismatch.length) issues.push(t('originDepotMediaTypeMismatch'))
  const watchInvalid = origins.filter((origin) => origin.trigger === 'watch' && origin.watchDirectChild === false)
  if (watchInvalid.length) issues.push(t('watchOriginNotDirectChild'))
  const disabledOrigins = origins.filter((origin) => origin.enabled === false)
  if (disabledOrigins.length) issues.push(t('oneOrMoreOriginsDisabled'))
  return issues
}

function depotHealth(depot: DepotSummary, issues: string[], origins: OriginConfigurationView[]): DepotHealthState {
  if (depot.enabled === false) return 'disabled'
  if (!depot.path || !depot.policy.target_library_path || origins.some((origin) => origin.media_type !== depot.media_type)) return 'broken'
  if (issues.length) return 'warning'
  return 'ready'
}

function summarizeOrganizeRules(
  origins: OriginConfigurationView[],
  organizeRuleById: Map<string, OrganizeRule>,
  t: TFunction,
) {
  const names = new Set<string>()
  origins.forEach((origin) => {
    const ruleId = origin.policy.organize_rule_id
    if (!ruleId) {
      names.add(t('none'))
      return
    }
    names.add(organizeRuleById.get(ruleId)?.name ?? ruleId)
  })
  return Array.from(names)
}

function findRepairDepot(depots: DepotSummary[], origin: OriginSummary) {
  return depots.find((depot) => depot.media_type === origin.media_type) ?? depots[0] ?? null
}

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
}
