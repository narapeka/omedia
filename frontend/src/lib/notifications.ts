import { toast, type ExternalToast } from 'sonner'
import { messages, type MessageKey } from '@/app/i18n/messages'

type ToastDescription = ExternalToast['description']
type Locale = keyof typeof messages
type MessageValues = Record<string, number | string | null | undefined>
type ErrorDetails = Record<string, unknown>
type ErrorInfo = {
  code?: string
  message?: string
  details?: unknown
}
type NotificationContent = {
  title: string
  description?: string
}

export function notifyError(error: unknown, fallback: string) {
  const content = notificationContent(error, fallback)
  toast.error(content.title, content.description ? { description: content.description } : undefined)
}

export function notifyWarning(message: string, description?: ToastDescription) {
  toast.warning(message, description ? { description } : undefined)
}

export function notifySuccess(message: string, description?: ToastDescription) {
  toast.success(message, description ? { description } : undefined)
}

export function errorMessage(error: unknown, fallback: string) {
  const content = notificationContent(error, fallback)
  return content.description ? `${content.title} ${content.description}` : content.title
}

export function notificationMessage(message: unknown, fallback = '') {
  return notificationContent(message, fallback).title
}

export function notificationContent(error: unknown, fallback = ''): NotificationContent {
  const info = errorInfo(error)
  const coded = info?.code ? translateErrorCode(info.code, objectDetails(info.details), fallback) : null
  if (coded) return coded
  const raw = typeof info?.message === 'string' && info.message.trim() ? info.message.trim() : rawText(error, fallback)
  return { title: raw }
}

function translateErrorCode(code: string, details: ErrorDetails, fallback: string): NotificationContent | null {
  const locale = currentLocale(fallback)
  const t = (key: MessageKey, values?: MessageValues) => interpolate(messages[locale][key] ?? messages['en-US'][key], values)
  const title = (key: MessageKey, values?: MessageValues): NotificationContent => ({ title: t(key, values) })
  const described = (titleKey: MessageKey, descriptionKey: MessageKey, values?: MessageValues): NotificationContent => ({
    title: t(titleKey, values),
    description: t(descriptionKey, values),
  })

  switch (code) {
    case 'request.validation':
      return title('apiErrorValidationFailed')
    case 'name.duplicate':
      return title('apiErrorNameAlreadyExists', { object: objectLabel(detailText(details, 'object'), t), name: detailText(details, 'name') })
    case 'name.required':
      return title('apiErrorNameRequired', { object: objectLabel(detailText(details, 'object'), t) })
    case 'rule.used':
      return title('apiErrorRuleStillUsed', {
        rule: objectLabel(ruleObject(details), t),
        name: detailText(details, 'rule_name'),
        object: objectLabel(detailText(details, 'object'), t),
        names: detailList(details, 'names').join(', '),
      })
    case 'path.overlap': {
      const leftLabel = objectLabel(detailText(details, 'left_label'), t)
      const rightLabel = objectLabel(detailText(details, 'right_label'), t)
      const leftPath = detailText(details, 'left_path')
      const rightPath = detailText(details, 'right_path')
      if (detailText(details, 'left_label') === 'Ad hoc source') {
        return described('apiErrorAdHocSourceManagedPathOverlap', 'apiErrorAdHocSourceManagedPathOverlapDescription', {
          label: rightLabel,
          path: rightPath,
        })
      }
      return described('apiErrorManagedPathsOverlap', 'apiErrorManagedPathsOverlapDescription', {
        leftLabel,
        leftPath,
        rightLabel,
        rightPath,
      })
    }
    case 'path.not_absolute':
      return described('apiErrorManagedPathMustBeAbsolute', 'apiErrorManagedPathMustBeAbsoluteDescription', {
        label: objectLabel(detailText(details, 'label'), t),
        path: detailText(details, 'path'),
      })
    case 'path.must_exist_directory':
      return title('apiErrorManagedPathMustExistDirectory', {
        label: objectLabel(detailText(details, 'label'), t),
        path: detailText(details, 'path'),
      })
    case 'path.reserved_unknown':
      return described('apiErrorManagedPathReservedUnknown', 'apiErrorManagedPathReservedUnknownDescription', {
        label: objectLabel(detailText(details, 'label'), t),
        path: detailText(details, 'path'),
      })
    case 'path.watch_direct_child':
      return described('apiErrorWatchOriginDirectChild', 'apiErrorWatchOriginDirectChildDescription', {
        label: objectLabel(detailText(details, 'label'), t),
      })
    case 'origin.unknown':
      return identifierMessage(title, 'apiErrorUnknownOrigin', 'apiErrorUnknownOriginNoId', 'origin', details)
    case 'origin.disabled':
      return identifierMessage(title, 'apiErrorOriginDisabled', 'apiErrorOriginDisabledNoId', 'origin', details)
    case 'origin.manual_active_session':
      return identifierMessage(title, 'apiErrorManualOriginActive', 'apiErrorManualOriginActiveNoId', 'origin', details)
    case 'origin.active_session':
      return title('removeOriginBlockedActiveSession')
    case 'origin.watch_automatic':
      return title('apiErrorWatchedFoldersAutomatic')
    case 'origin.unknown_depot':
      return title('apiErrorOriginUnknownDepotReference', {
        origin: displayIdentifier(detailText(details, 'origin_name') || detailText(details, 'origin_id'), t('origin')),
        depot: displayIdentifier(detailText(details, 'depot_name') || detailText(details, 'depot_id'), t('targetDepot')),
      })
    case 'origin.depot_media_mismatch':
      return title('apiErrorOriginDepotMediaMismatch', {
        origin: displayIdentifier(detailText(details, 'origin_name') || detailText(details, 'origin_id'), t('origin')),
        depot: displayIdentifier(detailText(details, 'depot_name') || detailText(details, 'depot_id'), t('targetDepot')),
      })
    case 'origin.unknown_organize_rule':
      return title('apiErrorOriginUnknownOrganizeRuleReference', {
        origin: displayIdentifier(detailText(details, 'origin_name') || detailText(details, 'origin_id'), t('origin')),
        rule: displayIdentifier(detailText(details, 'rule_name') || detailText(details, 'rule_id'), t('organizeRule')),
      })
    case 'depot.unknown':
      return identifierMessage(title, 'apiErrorUnknownDepot', 'apiErrorUnknownDepotNoId', 'depot', details)
    case 'depot.used_by_origin':
      return title('removeDepotBlockedOrigins', { count: detailNumber(details, 'count') ?? detailList(details, 'origins').length })
    case 'depot.active_session':
      return title('removeDepotBlockedActiveSession')
    case 'depot.active_transfer':
      return title('removeDepotBlockedActiveTransfer')
    case 'depot.unknown_transfer_rule':
      return title('apiErrorDepotUnknownTransferRuleReference', {
        depot: displayIdentifier(detailText(details, 'depot_name') || detailText(details, 'depot_id'), t('depot')),
        rule: displayIdentifier(detailText(details, 'rule_name') || detailText(details, 'rule_id'), t('transferRule')),
      })
    case 'depot.schedule_required':
      return title('apiErrorDepotScheduleRequired', {
        depot: displayIdentifier(detailText(details, 'depot_name') || detailText(details, 'depot_id'), t('depot')),
      })
    case 'depot.no_target':
      return title('apiErrorNoDepotForTarget', { target: detailText(details, 'target') })
    case 'depot_candidate.child_requires_folder':
      return title('apiErrorDepotCandidateChildRequiresFolder')
    case 'depot_candidate.unknown':
      return unknownObject(title, t, 'Depot candidate', detailText(details, 'candidate_id') || detailList(details, 'candidate_ids').join(', '))
    case 'depot_candidate_file.unknown':
      return unknownObject(title, t, 'Depot candidate file', detailText(details, 'file_id'))
    case 'watch.not_configured':
      return title('apiErrorWatchNotConfigured')
    case 'watch.restart_requires_running':
      return title('apiErrorWatchRestartRequiresRunning')
    case 'watch.root_missing':
      return title('apiErrorWatchRootMissingForChild', { path: detailText(details, 'path') })
    case 'watch.origin_create_failed':
      return title('apiErrorWatchOriginCreateFolderFailed', { path: detailText(details, 'path') })
    case 'watch.origin_not_directory':
      return title('apiErrorWatchOriginNotDirectory', { path: detailText(details, 'path') })
    case 'organize.ad_hoc_active':
      return title('apiErrorAdHocSessionActive')
    case 'organize_session.unknown':
      return unknownObject(title, t, 'OrganizeSession', detailText(details, 'session_id'))
    case 'source_candidate.unknown':
      return unknownObject(title, t, 'source candidate', detailText(details, 'source_candidate_id'))
    case 'source_file.unknown':
      return unknownObject(title, t, 'source file', detailText(details, 'source_file_id'))
    case 'source_candidate.missing':
      return title('apiErrorSourceCandidateMissing')
    case 'source_file.missing':
      return title('apiErrorSourceFileMissing')
    case 'source_candidate.rename_blocked':
      return title('apiErrorSourceCandidateRenameBlocked')
    case 'source_file.rename_blocked':
    case 'source_file.not_editable':
      return title('apiErrorSourceFileRenameBlocked')
    case 'plan_item.unknown':
      return unknownObject(title, t, 'plan item', detailText(details, 'plan_item_id'))
    case 'conflict_review.unknown':
      return unknownObject(title, t, 'conflict review', detailText(details, 'identity_key'))
    case 'provider.identify_required':
      return title('apiErrorProvidersRequired')
    case 'provider.tmdb_required':
      return title('apiErrorTmdbProviderRequired')
    case 'provider.llm_required':
      return title('apiErrorLlmProviderRequired')
    case 'transfer.busy':
      return title('apiErrorTransferWorkerBusy')
    default:
      return null
  }
}

function errorInfo(error: unknown): ErrorInfo | null {
  if (!error || typeof error !== 'object') return typeof error === 'string' ? { message: error } : null
  const nested = (error as { error?: ErrorInfo }).error
  if (nested && typeof nested === 'object') return nested
  const code = (error as { code?: unknown }).code
  const message = (error as { message?: unknown }).message
  const details = (error as { details?: unknown }).details
  if (typeof code === 'string' || typeof message === 'string') {
    return {
      code: typeof code === 'string' ? code : undefined,
      message: typeof message === 'string' ? message : undefined,
      details,
    }
  }
  return null
}

function rawText(value: unknown, fallback: string) {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (value instanceof Error && value.message) return value.message
  const nested = value && typeof value === 'object' ? (value as { error?: { message?: unknown }; message?: unknown }).error?.message : undefined
  if (typeof nested === 'string' && nested.trim()) return nested.trim()
  const message = value && typeof value === 'object' ? (value as { message?: unknown }).message : undefined
  if (typeof message === 'string' && message.trim()) return message.trim()
  return fallback
}

function currentLocale(fallback: string): Locale {
  if (fallback === messages['zh-CN'].requestFailed) return 'zh-CN'
  if (fallback === messages['en-US'].requestFailed) return 'en-US'
  if (typeof document === 'undefined') return 'en-US'
  const locale = document.documentElement.lang || document.body.dataset.locale
  return locale === 'zh-CN' ? 'zh-CN' : 'en-US'
}

function objectLabel(label: string, t: (key: MessageKey, values?: MessageValues) => string) {
  const keyByLabel: Record<string, MessageKey> = {
    'Ad hoc source': 'originPath',
    'Organize rule': 'organizeRule',
    'Transfer rule': 'transferRule',
    OrganizeSession: 'organizeSession',
    TransferJob: 'transferJob',
    Origin: 'origin',
    Depot: 'depot',
    'source candidate': 'sourceCandidate',
    'source file': 'sourceFile',
    'plan item': 'planItem',
    'conflict review': 'conflictReview',
    'Depot candidate': 'depotCandidate',
    'Depot candidate(s)': 'depotCandidate',
    'Depot candidate file': 'depotCandidateFile',
    WatchSettings: 'watchRootPath',
  }
  if (label.startsWith('Origin ')) return t('originPath')
  if (label.startsWith('Depot ') && label.endsWith(' Library')) return t('libraryPath')
  if (label.startsWith('Depot ')) return t('depotPath')
  const key = keyByLabel[label]
  return key ? t(key) : label
}

function ruleObject(details: ErrorDetails) {
  const kind = detailText(details, 'rule_kind')
  return kind === 'transfer' ? 'Transfer rule' : 'Organize rule'
}

function identifierMessage(
  title: (key: MessageKey, values?: MessageValues) => NotificationContent,
  key: MessageKey,
  noIdKey: MessageKey,
  detailPrefix: string,
  details: ErrorDetails,
) {
  const id = displayIdentifier(detailText(details, `${detailPrefix}_name`) || detailText(details, `${detailPrefix}_id`))
  return id ? title(key, { [detailPrefix]: id }) : title(noIdKey)
}

function unknownObject(
  title: (key: MessageKey, values?: MessageValues) => NotificationContent,
  t: (key: MessageKey, values?: MessageValues) => string,
  object: string,
  rawId: string,
) {
  const id = displayIdentifier(rawId)
  return id
    ? title('apiErrorUnknownObject', { object: objectLabel(object, t), id })
    : title('apiErrorUnknownObjectNoId', { object: objectLabel(object, t) })
}

function displayIdentifier(value: string, fallback = '') {
  const trimmed = value.trim()
  if (!trimmed) return fallback
  return isInternalIdentifier(trimmed) ? fallback : trimmed
}

function isInternalIdentifier(value: string) {
  return (
    /^[0-9a-f]{32,64}$/i.test(value)
    || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
    || /^(?:origin|depot|rule|source|source-candidate|source-file|depot-candidate|depot-candidate-file|plan-item|conflict-review|candidate|file|activity|file-action)_[0-9a-f]{12,}$/i.test(value)
    || /^(?:file|plan)_[A-Za-z0-9_-]{12,}$/i.test(value)
    || /^(?:depot-candidate|depot-candidate-file|depot-candidate-group)-[A-Za-z0-9_-]{12,}$/i.test(value)
    || /^(?:organize-session|transfer|activity|file-action|watch-dispatch)-[0-9a-f-]{12,}$/i.test(value)
    || /^transfer-\d+-[0-9a-f]{12,}$/i.test(value)
  )
}

function objectDetails(details: unknown): ErrorDetails {
  return details && typeof details === 'object' && !Array.isArray(details) ? details as ErrorDetails : {}
}

function detailText(details: ErrorDetails, key: string) {
  const value = details[key]
  return value === null || value === undefined ? '' : String(value)
}

function detailNumber(details: ErrorDetails, key: string) {
  const value = details[key]
  return typeof value === 'number' ? value : null
}

function detailList(details: ErrorDetails, key: string) {
  const value = details[key]
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item)).filter(Boolean)
}

function interpolate(template: string, values?: MessageValues) {
  if (!values) return template
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    const value = values[key]
    return value === null || value === undefined ? match : String(value)
  })
}
