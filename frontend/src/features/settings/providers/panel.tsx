import { BrainCircuit, Check, Search, Settings2, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useId, useState } from 'react'
import type { ProviderSettingsUpdate } from '@/api/types'
import type { TFunction } from '@/app/i18n/labels'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { Button } from '@/components/common/Button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { notifyError } from '@/lib/notifications'
import { useOrganizeSettings, useProviderStatus, useSettingsActions } from '../api'
import { FieldLabelWithInfo, TextField } from '../field'

type OrganizeMediaDraft = {
  video: string
  subtitle: string
  sidecar: string
  sizeMb: string
}

const MIN_NON_SUBTITLE_FILE_SIZE_MAX_MB = 300
const LLM_BATCH_SIZE_MAX = 100
const LLM_RATE_LIMIT_MAX = 5
const TMDB_RATE_LIMIT_MAX = 30

export function ProvidersPanel() {
  const { t, locale } = useI18n()
  const providers = useProviderStatus()
  const organizeSettings = useOrganizeSettings()
  const actions = useSettingsActions()
  const copy = mediaSettingsCopy(locale)
  const [draft, setDraft] = useState<ProviderSettingsUpdate | null>(null)
  const [organizeDraft, setOrganizeDraft] = useState<OrganizeMediaDraft | null>(null)
  const [message, setMessage] = useState('')
  const sidecarInputId = useId()
  const minSizeInputId = useId()
  const providerData = providers.data
  const onActionError = (error: unknown) => notifyError(error, t('requestFailed'))

  useEffect(() => {
    if (!providerData) return
    setDraft({
      tmdb_api_key: providerData.tmdb_api_key ?? '',
      tmdb_base_url: providerData.tmdb_base_url,
      tmdb_rate_limit: clampIntegerAtMost(providerData.tmdb_rate_limit, TMDB_RATE_LIMIT_MAX),
      tmdb_proxy: providerData.tmdb_proxy ?? '',
      llm_api_key: providerData.llm_api_key ?? '',
      llm_base_url: providerData.llm_base_url ?? '',
      llm_model: providerData.llm_model ?? '',
      llm_batch_size: clampIntegerAtMost(providerData.llm_batch_size, LLM_BATCH_SIZE_MAX),
      llm_rate_limit: clampIntegerAtMost(providerData.llm_rate_limit, LLM_RATE_LIMIT_MAX),
      llm_proxy: providerData.llm_proxy ?? '',
    })
  }, [providerData])

  useEffect(() => {
    const settings = organizeSettings.data
    if (!settings) return
    setOrganizeDraft({
      video: settings.extensions.video.join(', '),
      subtitle: settings.extensions.subtitle.join(', '),
      sidecar: settings.extensions.sidecar.join(', '),
      sizeMb: formatMinNonSubtitleSize(settings.min_non_subtitle_file_size_mb ?? 0),
    })
  }, [organizeSettings.data])

  if (!draft || !organizeDraft) {
    return <AsyncFrame loading={providers.isLoading || organizeSettings.isLoading} error={providers.error || organizeSettings.error}><div /></AsyncFrame>
  }

  const saving = actions.saveOrganizeSettings.isPending || actions.saveProviderSettings.isPending
  const updateLimitedProviderNumber = (field: 'llm_batch_size' | 'llm_rate_limit' | 'tmdb_rate_limit', value: string, max: number) => {
    if (!isAllowedIntegerAtMost(value, max)) return
    setDraft({ ...draft, [field]: Number(value) })
  }

  const saveMediaSettings = async () => {
    const nextVideo = parseExtensionGroup(organizeDraft.video, t('videoExtensions'), t)
    const nextSubtitle = parseExtensionGroup(organizeDraft.subtitle, t('subtitleExtensions'), t)
    const nextSidecar = parseExtensionGroup(organizeDraft.sidecar, t('sidecarExtensions'), t)
    const error = nextVideo.error || nextSubtitle.error || nextSidecar.error
    if (error) {
      setMessage(error)
      return
    }
    const nextSizeMb = organizeDraft.sizeMb.trim()
    if (!/^\d+$/.test(nextSizeMb)) {
      setMessage(t('organizeSettingsInvalid'))
      return
    }
    if (Number(nextSizeMb) > MIN_NON_SUBTITLE_FILE_SIZE_MAX_MB) return

    try {
      const providerResult = await actions.saveProviderSettings.mutateAsync({
        ...draft,
        tmdb_api_key: draft.tmdb_api_key?.trim() ?? '',
        tmdb_proxy: draft.tmdb_proxy || null,
        llm_api_key: draft.llm_api_key?.trim() ?? '',
        llm_base_url: draft.llm_base_url || null,
        llm_model: draft.llm_model || null,
        llm_proxy: draft.llm_proxy || null,
      })
      await actions.saveOrganizeSettings.mutateAsync({
        extensions: {
          video: nextVideo.extensions,
          subtitle: nextSubtitle.extensions,
          sidecar: nextSidecar.extensions,
        },
        min_non_subtitle_file_size_mb: Number(nextSizeMb),
      })
      setDraft((current) => current
        ? {
            ...current,
            tmdb_api_key: providerResult.tmdb_api_key ?? '',
            llm_api_key: providerResult.llm_api_key ?? '',
          }
        : current)
      setMessage(copy.saved)
    } catch (error) {
      onActionError(error)
    }
  }

  return (
    <AsyncFrame loading={providers.isLoading || organizeSettings.isLoading} error={providers.error || organizeSettings.error}>
      <Card className="gap-0">
        <CardHeader className="border-b pb-4">
          <div className="min-w-0">
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </div>
          <CardAction>
            <Button aria-label={t('saveChanges')} onClick={() => void saveMediaSettings()} disabled={saving}>
              <Check data-icon="inline-start" />
              {t('saveChanges')}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-0 px-0">
          <MediaSettingsSection icon={Settings2} title={t('extensions')} description={t('extensionsDescription')}>
            <SettingsFieldSection title={t('organizeCandidateRecognition')}>
              <TextField label={t('videoExtensions')} value={organizeDraft.video} onChange={(video) => setOrganizeDraft({ ...organizeDraft, video })} />
              <TextField label={t('subtitleExtensions')} value={organizeDraft.subtitle} onChange={(subtitle) => setOrganizeDraft({ ...organizeDraft, subtitle })} />
            </SettingsFieldSection>
            <SettingsFieldSection title={t('organizeSourceCleanup')}>
              <Field>
                <Input
                  id={sidecarInputId}
                  value={organizeDraft.sidecar}
                  onChange={(event) => setOrganizeDraft({ ...organizeDraft, sidecar: event.target.value })}
                />
                <FieldLabelWithInfo htmlFor={sidecarInputId} help={t('sidecarExtensionsHelp')}>
                  {t('sidecarExtensions')}
                </FieldLabelWithInfo>
              </Field>
              <Field>
                <Input
                  id={minSizeInputId}
                  type="number"
                  min={0}
                  max={MIN_NON_SUBTITLE_FILE_SIZE_MAX_MB}
                  inputMode="numeric"
                  step={1}
                  value={organizeDraft.sizeMb}
                  onChange={(event) => {
                    const nextSizeMb = event.target.value
                    if (!isAllowedMinNonSubtitleSize(nextSizeMb)) return
                    setOrganizeDraft({ ...organizeDraft, sizeMb: nextSizeMb })
                  }}
                />
                <FieldLabelWithInfo htmlFor={minSizeInputId} help={t('minNonSubtitleFileSizeHelp')}>
                  {t('minNonSubtitleFileSizeMb')}
                </FieldLabelWithInfo>
              </Field>
            </SettingsFieldSection>
          </MediaSettingsSection>

          <MediaSettingsSection icon={BrainCircuit} title={t('providerLlm')} description={t('providerLlmDescription')}>
            <SettingsFieldSection title={copy.llmConnection}>
              <TextField label={t('llmApiKey')} value={draft.llm_api_key ?? ''} onChange={(llm_api_key) => setDraft({ ...draft, llm_api_key })} />
              <TextField label={t('baseUrl')} value={draft.llm_base_url ?? ''} onChange={(llm_base_url) => setDraft({ ...draft, llm_base_url })} />
              <TextField label={t('model')} value={draft.llm_model ?? ''} onChange={(llm_model) => setDraft({ ...draft, llm_model })} />
            </SettingsFieldSection>
            <SettingsFieldSection title={copy.llmRuntime}>
              <TextField label={t('batchSize')} value={String(draft.llm_batch_size)} onChange={(value) => updateLimitedProviderNumber('llm_batch_size', value, LLM_BATCH_SIZE_MAX)} type="number" min={0} max={LLM_BATCH_SIZE_MAX} step={1} inputMode="numeric" />
              <TextField label={t('rateLimit')} value={String(draft.llm_rate_limit)} onChange={(value) => updateLimitedProviderNumber('llm_rate_limit', value, LLM_RATE_LIMIT_MAX)} type="number" min={0} max={LLM_RATE_LIMIT_MAX} step={1} inputMode="numeric" />
              <TextField label={t('proxy')} value={draft.llm_proxy ?? ''} onChange={(llm_proxy) => setDraft({ ...draft, llm_proxy })} />
            </SettingsFieldSection>
          </MediaSettingsSection>

          <MediaSettingsSection icon={Search} title={t('providerTmdb')} description={t('providerTmdbDescription')}>
            <SettingsFieldSection title={copy.providerConnection}>
              <TextField label={t('tmdbApiKey')} value={draft.tmdb_api_key ?? ''} onChange={(tmdb_api_key) => setDraft({ ...draft, tmdb_api_key })} />
              <TextField label={t('baseUrl')} value={draft.tmdb_base_url} onChange={(tmdb_base_url) => setDraft({ ...draft, tmdb_base_url })} />
            </SettingsFieldSection>
            <SettingsFieldSection title={copy.providerRuntime}>
              <TextField label={t('rateLimit')} value={String(draft.tmdb_rate_limit)} onChange={(value) => updateLimitedProviderNumber('tmdb_rate_limit', value, TMDB_RATE_LIMIT_MAX)} type="number" min={0} max={TMDB_RATE_LIMIT_MAX} step={1} inputMode="numeric" />
              <TextField label={t('proxy')} value={draft.tmdb_proxy ?? ''} onChange={(tmdb_proxy) => setDraft({ ...draft, tmdb_proxy })} />
            </SettingsFieldSection>
          </MediaSettingsSection>

          {message ? <div className="px-4 pb-4 text-sm text-muted-foreground">{message}</div> : null}
        </CardContent>
      </Card>
    </AsyncFrame>
  )
}

function mediaSettingsCopy(locale: 'en-US' | 'zh-CN') {
  if (locale === 'zh-CN') {
    return {
      title: '媒体设置',
      description: '配置整理扩展名、LLM 识别和 TMDB 查询。',
      saved: '媒体设置已保存。',
      llmConnection: '连接与模型',
      llmRuntime: '批量与运行参数',
      providerConnection: '连接配置',
      providerRuntime: '速率与代理',
    }
  }
  return {
    title: 'Media settings',
    description: 'Configure source cleanup, LLM identification, and TMDB lookup in one place.',
    saved: 'Media settings saved.',
    llmConnection: 'Connection and model',
    llmRuntime: 'Batch and runtime',
    providerConnection: 'Connection settings',
    providerRuntime: 'Rate and proxy',
  }
}

function MediaSettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="flex flex-col">
      <div data-media-settings-group-header="true" className="relative mx-4 flex min-h-11 min-w-0 items-center gap-4 overflow-hidden border-y border-border/70 bg-muted/35 py-2.5 pl-[1.375rem] pr-4">
        <span className="omedia-metal-accent absolute inset-y-0 left-0 w-1.5" aria-hidden="true" />
        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex min-w-0 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
          <div className="shrink-0 font-heading text-sm font-semibold leading-snug text-foreground">{title}</div>
          <p className="min-w-0 truncate text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="grid gap-x-5 gap-y-4 px-4 py-5 lg:grid-cols-2">
        {children}
      </div>
    </section>
  )
}

function SettingsFieldSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="flex min-w-0 flex-col gap-3.5">
      <div className="text-[13px] font-semibold text-muted-foreground">{title}</div>
      {children}
    </div>
  )
}

function formatMinNonSubtitleSize(value: number) {
  return String(clampIntegerAtMost(value, MIN_NON_SUBTITLE_FILE_SIZE_MAX_MB))
}

function isAllowedMinNonSubtitleSize(value: string) {
  return isAllowedIntegerAtMost(value, MIN_NON_SUBTITLE_FILE_SIZE_MAX_MB)
}

function clampIntegerAtMost(value: number, max: number) {
  const normalized = Number.isFinite(value) ? Math.trunc(value) : 0
  return Math.max(0, Math.min(max, normalized))
}

function isAllowedIntegerAtMost(value: string, max: number) {
  return value === '' || (/^\d+$/.test(value) && Number(value) <= max)
}

function parseExtensionGroup(value: string, label: string, t: TFunction): { extensions: string[]; error: string } {
  const extensions: string[] = []
  for (const item of value.split(',')) {
    const rawExtension = item.trim().toLowerCase()
    if (!rawExtension) continue
    const extension = rawExtension.startsWith('.') ? rawExtension : `.${rawExtension}`
    if (!isValidExtension(extension)) {
      return { extensions: [], error: t('invalidExtension', { label, value: rawExtension }) }
    }
    if (!extensions.includes(extension)) extensions.push(extension)
  }
  return { extensions, error: '' }
}

function isValidExtension(extension: string) {
  return /^\.[a-z0-9][a-z0-9_-]*$/i.test(extension)
}
