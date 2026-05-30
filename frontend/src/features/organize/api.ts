import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  applyConflictReviewAction,
  cancelOrganizeSession as cancelSession,
  createOrganizeSession as createSession,
  createOrganizeSessionsBulk as createSessionsBulk,
  deleteOrganizeCandidate as deleteSourceCandidate,
  deleteOrganizeCandidateFile as deleteSourceFile,
  executeOrganizeSession as organizeSession,
  listOrganizeSessions as listSessions,
  organizeCandidateDetail as getSourceCandidateDetail,
  organizeCandidateFileDetail as getSourceFileDetail,
  renameOrganizeCandidate as renameSourceCandidate,
  renameOrganizeCandidateFile as renameSourceFile,
  scanOrganizeSession as restartScanPhaseForSession,
  setOrganizeCandidateDecision as setSourceCandidateDecision,
  setOrganizePlanItemDecision as setPlanItemDecision,
} from '@/api/generated/organize/organize'
import {
  applyIdentifyCandidateOverride as applySourceCandidateTmdbOverride,
  identifySession as runIdentifyPhaseForSession,
  searchIdentifySession as searchTmdbForSession,
} from '@/api/generated/identify/identify'
import type {
  CandidateDecisionRequest,
  ConflictReviewActionRequest,
  IdentityOverrideRequest,
  IdentifySearchRequest,
  OrganizeBulkSessionCreateRequest,
  OrganizeRequest,
  OrganizeSession,
  RenameRequest,
} from '@/api/types'
import { activityKeys } from '@/features/activity/api'
import { depotKeys } from '@/features/depot/api'
import { originKeys } from '@/features/origin/api'

export const organizeKeys = {
  sessions: ['organizeSessions'] as const,
}

type CandidateDecisionValue = CandidateDecisionRequest['decision']
type DecisionMutationContext = {
  previousSessions?: OrganizeSession[]
}

function updatePlanItemDecision(
  sessions: OrganizeSession[] | undefined,
  sessionId: string,
  planItemId: string,
  decision: CandidateDecisionValue,
) {
  if (!sessions) return sessions
  let changed = false
  const nextSessions = sessions.map((session) => {
    if (session.id !== sessionId) return session
    let sessionChanged = false
    const reviewCandidates = session.review_candidates.map((candidate) => {
      let candidateChanged = false
      const planItems = candidate.plan_items.map((planItem) => {
        if (planItem.id !== planItemId) return planItem
        candidateChanged = true
        return { ...planItem, user_decision: decision }
      })
      if (!candidateChanged) return candidate
      sessionChanged = true
      return { ...candidate, plan_items: planItems }
    })
    if (!sessionChanged) return session
    changed = true
    return { ...session, review_candidates: reviewCandidates }
  })
  return changed ? nextSessions : sessions
}

function updateSourceCandidateDecision(
  sessions: OrganizeSession[] | undefined,
  sessionId: string,
  candidateId: string,
  decision: CandidateDecisionValue,
) {
  if (!sessions) return sessions
  let changed = false
  const nextSessions = sessions.map((session) => {
    if (session.id !== sessionId) return session
    let sessionChanged = false
    const reviewCandidates = session.review_candidates.map((candidate) => {
      if (candidate.id !== candidateId) return candidate
      sessionChanged = true
      const planItems = candidate.plan_items.map((planItem) => {
        if (decision === 'accept' && !planItem.acceptance.can_accept) return planItem
        return { ...planItem, user_decision: decision }
      })
      return { ...candidate, selection_decision: decision, plan_items: planItems }
    })
    if (!sessionChanged) return session
    changed = true
    return { ...session, review_candidates: reviewCandidates }
  })
  return changed ? nextSessions : sessions
}

export function useOrganizeSessions({ poll = true }: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: organizeKeys.sessions,
    queryFn: ({ signal }) => listSessions({ signal }),
    refetchInterval: poll ? 3_000 : false,
  })
}

export function useSessionActions() {
  const queryClient = useQueryClient()
  const refresh = () => void queryClient.invalidateQueries({ queryKey: organizeKeys.sessions })
  const refreshActivity = () => void queryClient.invalidateQueries({ queryKey: activityKeys.root })
  const refreshSession = (session: OrganizeSession) => {
    queryClient.setQueryData<OrganizeSession[]>(organizeKeys.sessions, (current) => {
      if (!current) return [session]
      const exists = current.some((item) => item.id === session.id)
      return exists ? current.map((item) => (item.id === session.id ? session : item)) : [session, ...current]
    })
    refresh()
  }

  return {
    createSession: useMutation({
      mutationFn: (data: OrganizeRequest) => createSession(data),
      onSuccess: refresh,
    }),
    createSessionsBulk: useMutation({
      mutationFn: (data: OrganizeBulkSessionCreateRequest) => createSessionsBulk(data),
      onSuccess: refresh,
    }),
    runIdentifyPhase: useMutation({
      mutationFn: (sessionId: string) => runIdentifyPhaseForSession(sessionId),
      onSuccess: refresh,
    }),
    restartScanPhase: useMutation({
      mutationFn: (sessionId: string) => restartScanPhaseForSession(sessionId),
      onSuccess: refreshSession,
    }),
    cancelSession: useMutation({
      mutationFn: (sessionId: string) => cancelSession(sessionId),
      onSuccess: refresh,
    }),
    getSourceCandidateDetail: useMutation({
      mutationFn: ({ sessionId, candidateId }: { sessionId: string; candidateId: string }) =>
        getSourceCandidateDetail(sessionId, candidateId),
    }),
    getSourceFileDetail: useMutation({
      mutationFn: ({ sessionId, candidateId, fileId }: { sessionId: string; candidateId: string; fileId: string }) =>
        getSourceFileDetail(sessionId, candidateId, fileId),
    }),
    deleteSourceFile: useMutation({
      mutationFn: ({ sessionId, candidateId, fileId }: { sessionId: string; candidateId: string; fileId: string }) =>
        deleteSourceFile(sessionId, candidateId, fileId),
      onSuccess: (session) => {
        refreshSession(session)
        refreshActivity()
      },
    }),
    deleteSourceCandidate: useMutation({
      mutationFn: ({ sessionId, candidateId }: { sessionId: string; candidateId: string }) =>
        deleteSourceCandidate(sessionId, candidateId),
      onSuccess: (session) => {
        refreshSession(session)
        refreshActivity()
      },
    }),
    renameSourceFile: useMutation({
      mutationFn: ({ sessionId, candidateId, fileId, data }: { sessionId: string; candidateId: string; fileId: string; data: RenameRequest }) =>
        renameSourceFile(sessionId, candidateId, fileId, data),
      onSuccess: (session) => {
        refreshSession(session)
        refreshActivity()
      },
    }),
    renameSourceCandidate: useMutation({
      mutationFn: ({ sessionId, candidateId, data }: { sessionId: string; candidateId: string; data: RenameRequest }) =>
        renameSourceCandidate(sessionId, candidateId, data),
      onSuccess: (session) => {
        refreshSession(session)
        refreshActivity()
      },
    }),
    setPlanItemDecision: useMutation({
      mutationFn: async ({ sessionId, planItemId, data }: { sessionId: string; planItemId: string; data: CandidateDecisionRequest }) => {
        await setPlanItemDecision(sessionId, planItemId, data)
      },
      onMutate: async ({ sessionId, planItemId, data }) => {
        await queryClient.cancelQueries({ queryKey: organizeKeys.sessions })
        const previousSessions = queryClient.getQueryData<OrganizeSession[]>(organizeKeys.sessions)
        queryClient.setQueryData<OrganizeSession[]>(organizeKeys.sessions, (current) =>
          updatePlanItemDecision(current, sessionId, planItemId, data.decision),
        )
        return { previousSessions } satisfies DecisionMutationContext
      },
      onError: (_error, _variables, context) => {
        if (context?.previousSessions) queryClient.setQueryData(organizeKeys.sessions, context.previousSessions)
      },
    }),
    setSourceCandidateDecision: useMutation({
      mutationFn: async ({ sessionId, candidateId, data }: { sessionId: string; candidateId: string; data: CandidateDecisionRequest }) => {
        await setSourceCandidateDecision(sessionId, candidateId, data)
      },
      onMutate: async ({ sessionId, candidateId, data }) => {
        await queryClient.cancelQueries({ queryKey: organizeKeys.sessions })
        const previousSessions = queryClient.getQueryData<OrganizeSession[]>(organizeKeys.sessions)
        queryClient.setQueryData<OrganizeSession[]>(organizeKeys.sessions, (current) =>
          updateSourceCandidateDecision(current, sessionId, candidateId, data.decision),
        )
        return { previousSessions } satisfies DecisionMutationContext
      },
      onError: (_error, _variables, context) => {
        if (context?.previousSessions) queryClient.setQueryData(organizeKeys.sessions, context.previousSessions)
      },
    }),
    applyConflictReviewAction: useMutation({
      mutationFn: ({ sessionId, data }: { sessionId: string; data: ConflictReviewActionRequest }) =>
        applyConflictReviewAction(sessionId, data),
      onSuccess: refreshSession,
    }),
    searchTmdb: useMutation({
      mutationFn: ({ sessionId, data }: { sessionId: string; data: IdentifySearchRequest }) =>
        searchTmdbForSession(sessionId, data),
    }),
    applySourceCandidateTmdbOverride: useMutation({
      mutationFn: ({ sessionId, candidateId, data }: { sessionId: string; candidateId: string; data: IdentityOverrideRequest }) =>
        applySourceCandidateTmdbOverride(sessionId, candidateId, data),
      onSuccess: refresh,
    }),
    organizeSession: useMutation({
      mutationFn: (sessionId: string) => organizeSession(sessionId),
      onSuccess: () => {
        refresh()
        void queryClient.invalidateQueries({ queryKey: originKeys.all })
        void queryClient.invalidateQueries({ queryKey: depotKeys.all })
        refreshActivity()
      },
    }),
  }
}
