import { useMemo } from 'react'
import type { OrganizeRuleDraft, TransferRuleDraft } from '@/api/types'
import { useI18n } from '@/app/providers/I18nProvider'
import { AsyncFrame } from '@/components/common/AsyncFrame'
import { useDepots } from '@/features/depot/api'
import { useOrigins } from '@/features/origin/api'
import { notifyError } from '@/lib/notifications'
import { RuleEditor } from './editor'
import { normalizeRuleReferences } from './references'
import { useOrganizeRules, useRuleActions, useRuleReferences, useTransferRules } from './api'

export function RulesPanel() {
  const { t } = useI18n()
  const organizeRules = useOrganizeRules()
  const transferRules = useTransferRules()
  const ruleReferences = useRuleReferences()
  const origins = useOrigins()
  const depots = useDepots()
  const actions = useRuleActions()
  const references = useMemo(() => normalizeRuleReferences(ruleReferences.data), [ruleReferences.data])
  const onMutationError = (error: unknown) => notifyError(error, t('requestFailed'))

  return (
    <div className="flex flex-col gap-4">
      <AsyncFrame
        loading={organizeRules.isLoading || transferRules.isLoading || origins.isLoading || depots.isLoading}
        error={organizeRules.error || transferRules.error || origins.error || depots.error}
      >
        <RuleEditor
          ruleReferences={references}
          organizeRules={organizeRules.data ?? []}
          transferRules={transferRules.data ?? []}
          organizeUsedBy={(ruleId) => (origins.data ?? []).filter((origin) => origin.policy.organize_rule_id === ruleId).map((origin) => origin.name)}
          transferUsedBy={(ruleId) => (depots.data ?? []).filter((depot) => depot.policy.transfer_rule_id === ruleId).map((depot) => depot.name)}
          saving={{
            organize: actions.createOrganizeRule.isPending || actions.saveOrganizeRule.isPending,
            transfer: actions.createTransferRule.isPending || actions.saveTransferRule.isPending,
          }}
          deleting={{
            organize: actions.deleteOrganizeRule.isPending,
            transfer: actions.deleteTransferRule.isPending,
          }}
          onSave={(kind, ruleId, rule) => {
            if (kind === 'organize') {
              const payload = rule as OrganizeRuleDraft
              if (ruleId) actions.saveOrganizeRule.mutate({ ruleId, data: payload }, { onError: onMutationError })
              else actions.createOrganizeRule.mutate(payload, { onError: onMutationError })
              return
            }
            const payload = rule as TransferRuleDraft
            if (ruleId) actions.saveTransferRule.mutate({ ruleId, data: payload }, { onError: onMutationError })
            else actions.createTransferRule.mutate(payload, { onError: onMutationError })
          }}
          onDelete={(kind, ruleId) => {
            if (kind === 'organize') actions.deleteOrganizeRule.mutate(ruleId, { onError: onMutationError })
            else actions.deleteTransferRule.mutate(ruleId, { onError: onMutationError })
          }}
        />
      </AsyncFrame>
    </div>
  )
}

