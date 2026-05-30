import { useI18n } from '@/app/providers/I18nProvider'
import { TextSwitch } from '@/components/common/TextSwitch'

export function DepotCandidateDecisionSwitcher({
  accepted,
  disabled,
  inherited,
  target,
  onAcceptedChange,
}: {
  accepted: boolean
  disabled?: boolean
  inherited?: boolean
  target: string
  onAcceptedChange?: (accepted: boolean) => void
}) {
  const { t } = useI18n()
  const label = inherited
    ? t('acceptedTargetInherited', { state: accepted ? t('selected') : t('unselected'), target })
    : accepted
      ? t('acceptedTargetClickIgnore', { target })
      : t('ignoredTargetClickAccept', { target })

  return (
    <TextSwitch
      checked={accepted}
      checkedLabel={t('accept')}
      uncheckedLabel={t('ignore')}
      ariaLabel={label}
      disabled={disabled || inherited}
      onCheckedChange={onAcceptedChange}
      title={inherited ? t('inheritedFromCandidate') : accepted ? t('acceptedClickIgnore') : t('ignoredClickAccept')}
      widthRem={5.5}
    />
  )
}
