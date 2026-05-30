import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createOrganizeRule as createOrganizeRuleRequest,
  createTransferRule as createTransferRuleRequest,
  deleteOrganizeRule,
  deleteTransferRule,
  listOrganizeRules,
  listTransferRules,
  previewOrganizeRule,
  previewTransferRule,
  ruleReferences as getBundledRuleReferences,
  saveOrganizeRule as saveOrganizeRuleRequest,
  saveTransferRule as saveTransferRuleRequest,
} from '@/api/generated/rules/rules'
import type {
  OrganizeRuleDraft,
  OrganizeRulePreviewRequest,
  TransferRuleDraft,
  TransferRulePreviewRequest,
} from '@/api/types'

export const rulesKeys = {
  organize: ['rules', 'organize'] as const,
  transfer: ['rules', 'transfer'] as const,
  references: ['rules', 'bundled-references'] as const,
}

export function useOrganizeRules() {
  return useQuery({
    queryKey: rulesKeys.organize,
    queryFn: ({ signal }) => listOrganizeRules({ signal }),
  })
}

export function useTransferRules() {
  return useQuery({
    queryKey: rulesKeys.transfer,
    queryFn: ({ signal }) => listTransferRules({ signal }),
  })
}

export function useRuleReferences() {
  return useQuery({
    queryKey: rulesKeys.references,
    queryFn: ({ signal }) => getBundledRuleReferences({ signal }),
    staleTime: 24 * 60 * 60 * 1000,
  })
}

export function useRuleActions() {
  const queryClient = useQueryClient()
  return {
    saveOrganizeRule: useMutation({
      mutationFn: ({ ruleId, data }: { ruleId: string; data: OrganizeRuleDraft }) => saveOrganizeRuleRequest(ruleId, data),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.organize }),
    }),
    createOrganizeRule: useMutation({
      mutationFn: (data: OrganizeRuleDraft) => createOrganizeRuleRequest(data),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.organize }),
    }),
    deleteOrganizeRule: useMutation({
      mutationFn: (ruleId: string) => deleteOrganizeRule(ruleId),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.organize }),
    }),
    saveTransferRule: useMutation({
      mutationFn: ({ ruleId, data }: { ruleId: string; data: TransferRuleDraft }) => saveTransferRuleRequest(ruleId, data),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.transfer }),
    }),
    createTransferRule: useMutation({
      mutationFn: (data: TransferRuleDraft) => createTransferRuleRequest(data),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.transfer }),
    }),
    deleteTransferRule: useMutation({
      mutationFn: (ruleId: string) => deleteTransferRule(ruleId),
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: rulesKeys.transfer }),
    }),
    previewOrganizeRule: useMutation({
      mutationFn: (data: OrganizeRulePreviewRequest) => previewOrganizeRule(data),
    }),
    previewTransferRule: useMutation({
      mutationFn: (data: TransferRulePreviewRequest) => previewTransferRule(data),
    }),
  }
}
