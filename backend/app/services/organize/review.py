from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from app.domain.depot import Depot, ResolveMode, effective_depot_resolve_mode
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.organize import (
    CandidateDecision,
    ConflictReviewAction,
    ConflictReviewStatus,
    OrganizePlanItem,
    OrganizeSessionState,
)
from app.engines.resolve.identity import apply_tag_override_to_plan_item, package_identity, planned_tag
from app.services.identify.candidate import CandidateMatch
from app.services.organize.candidate import find_plan_item, require_active_candidate, source_state
from app.services.organize.session import (
    ConflictReviewState,
    OrganizeSession,
    OrganizeSessionError,
    SourceCandidateStatus,
    SourceFileStatus,
    require_state,
)


@dataclass(frozen=True)
class ReviewAcceptance:
    can_accept: bool = False
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictReview:
    identity_key: str
    items: tuple[OrganizePlanItem, ...]
    source_candidate_ids: tuple[str, ...]
    accepted_source_candidate_ids: tuple[str, ...]
    existing: bool
    status: ConflictReviewStatus
    action_required: bool


@dataclass(frozen=True)
class ConflictReviewRead:
    identity_key: str
    kind: str
    status: str
    display_path: Path
    root_relative_path: Path
    plan_item_ids: list[str]
    source_candidate_ids: list[str]
    accepted_source_candidate_ids: list[str]
    action_required: bool
    conflict: bool
    conflict_reason: str | None
    existing: bool
    action: str | None
    action_source_candidate_id: str | None
    replace_intent: bool
    source_tag: str | None


def require_plan_item_eligible(task: OrganizeSession, item: OrganizePlanItem) -> None:
    candidate_state = source_state(task, item.source_candidate_id)
    if candidate_state.status != SourceCandidateStatus.ACTIVE:
        raise OrganizeSessionError(f"Source candidate is {candidate_state.status.value}")
    state = task.file_states.get(item.source_file_id)
    if state is not None and state.status != SourceFileStatus.ACTIVE:
        raise OrganizeSessionError(f"Source file is {state.status.value}")


def validate_candidate_decision(task: OrganizeSession, item: OrganizePlanItem, decision: CandidateDecision) -> None:
    if decision == CandidateDecision.IGNORE:
        return
    if decision == CandidateDecision.ACCEPT:
        acceptance = plan_item_acceptance(task, item)
        if acceptance.can_accept:
            return
        raise OrganizeSessionError(f"Cannot accept plan item: {', '.join(acceptance.blockers)}")
    raise OrganizeSessionError(f"Unsupported plan item decision: {decision}")


def plan_item_acceptance(task: OrganizeSession, item: OrganizePlanItem) -> ReviewAcceptance:
    blockers: list[str] = []
    candidate_state = source_state(task, item.source_candidate_id)
    if candidate_state.status != SourceCandidateStatus.ACTIVE:
        blockers.append("inactive_source_candidate")
    state = task.file_states.get(item.source_file_id)
    if state is not None and state.status != SourceFileStatus.ACTIVE:
        blockers.append("inactive_source_file")
    if not item.metadata or item.metadata_source not in {"auto", "manual_override"}:
        blockers.append("missing_metadata")
    if item.preview.proposed_relative_path is None:
        blockers.append("missing_target_path")
    return ReviewAcceptance(can_accept=not blockers, blockers=tuple(blockers))


def candidate_match_acceptance(task: OrganizeSession, match: CandidateMatch | None) -> ReviewAcceptance:
    if match is None:
        return ReviewAcceptance(False, ("manual_override_required",))
    blockers: list[str] = []
    candidate_state = source_state(task, match.source_candidate_id)
    if candidate_state.status != SourceCandidateStatus.ACTIVE:
        blockers.append("inactive_source_candidate")
    if not match.metadata or match.metadata_source not in {"auto", "manual_override"}:
        blockers.append("missing_metadata")
    child_items = [item for item in task.plan_items if item.source_candidate_id == match.source_candidate_id]
    if child_items and not any(plan_item_acceptance(task, item).can_accept for item in child_items):
        blockers.append("missing_target_path")
    return ReviewAcceptance(can_accept=not blockers, blockers=tuple(blockers))


def sort_plan_items(items: list[OrganizePlanItem]) -> list[OrganizePlanItem]:
    return sorted(items, key=lambda item: (item.source_candidate_id, str(item.source_path).casefold()))


def auto_accept_high_confidence_plan_items(task: OrganizeSession) -> None:
    for item in task.plan_items:
        if item.confidence != ConfidenceLevel.HIGH:
            continue
        if plan_item_acceptance(task, item).can_accept:
            item.user_decision = CandidateDecision.ACCEPT


def set_plan_item_decision(
    task: OrganizeSession,
    plan_item_id: str,
    decision: CandidateDecision,
    *,
    target_depot: Depot | None = None,
) -> OrganizePlanItem:
    require_state(task, {OrganizeSessionState.IDENTIFIED})
    item = find_plan_item(task, plan_item_id)
    require_plan_item_eligible(task, item)
    decision = CandidateDecision(decision)
    validate_candidate_decision(task, item, decision)
    if decision == CandidateDecision.ACCEPT and not ConflictReviews(task, target_depot=target_depot).plan_item_directly_switchable(item):
        raise OrganizeSessionError("Plan item belongs to an unresolved conflict review")
    item.user_decision = decision
    return item


def set_source_candidate_decision(
    task: OrganizeSession,
    source_candidate_id: str,
    decision: CandidateDecision,
    *,
    target_depot: Depot | None = None,
) -> OrganizeSession:
    require_state(task, {OrganizeSessionState.SCANNED, OrganizeSessionState.IDENTIFIED})
    require_active_candidate(task, source_candidate_id)
    decision = CandidateDecision(decision)
    if task.state == OrganizeSessionState.SCANNED:
        source_state(task, source_candidate_id).selection_decision = decision
        return task
    conflict_reviews = ConflictReviews(task, target_depot=target_depot)
    for item in task.plan_items:
        if item.source_candidate_id != source_candidate_id:
            continue
        try:
            require_plan_item_eligible(task, item)
            validate_candidate_decision(task, item, decision)
            if decision == CandidateDecision.ACCEPT and not conflict_reviews.plan_item_directly_switchable(item):
                continue
        except OrganizeSessionError:
            continue
        item.user_decision = decision
    return task


class ConflictReviews:
    def __init__(self, task: OrganizeSession, *, target_depot: Depot | None = None) -> None:
        self.task = task
        self.target_depot = target_depot

    def groups(self) -> dict[str, ConflictReview]:
        task = self.task
        if not self._full_package_resolve_enabled():
            return {}
        grouped: dict[str, list[OrganizePlanItem]] = {}
        for item in task.plan_items:
            if not self._plan_item_is_package_eligible(item):
                continue
            identity = package_identity(item, task.media_type)
            if identity is None:
                continue
            grouped.setdefault(identity.key, []).append(item)

        review_groups: dict[str, ConflictReview] = {}
        for key, items in grouped.items():
            identity = package_identity(items[0], task.media_type)
            if identity is None:
                continue
            source_ids = tuple(sorted({str(item.source_candidate_id) for item in items if item.source_candidate_id}))
            accepted_source_ids = tuple(
                sorted({str(item.source_candidate_id) for item in items if item.source_candidate_id and item.user_decision == CandidateDecision.ACCEPT})
            )
            existing = bool(self.target_depot and (self.target_depot.path / identity.root_relative_path).exists())
            duplicate = len(source_ids) > 1
            if duplicate and existing:
                status = ConflictReviewStatus.DUPLICATE_SOURCE_AND_TARGET_EXISTS
            elif duplicate:
                status = ConflictReviewStatus.DUPLICATE_SOURCE
            elif existing:
                status = ConflictReviewStatus.TARGET_EXISTS
            else:
                status = ConflictReviewStatus.READY
            review_groups[key] = ConflictReview(
                identity_key=key,
                items=tuple(sort_plan_items(items)),
                source_candidate_ids=source_ids,
                accepted_source_candidate_ids=accepted_source_ids,
                existing=existing,
                status=status,
                action_required=status != ConflictReviewStatus.READY,
            )
        return review_groups

    def apply_defaults(self) -> None:
        groups = self.groups()
        action_required_item_ids = {
            item.id
            for group in groups.values()
            if group.action_required
            for item in group.items
        }
        for item in self.task.plan_items:
            if item.id not in action_required_item_ids:
                continue
            item.user_decision = None
        self.drop_stale()

    def validate_accepted_scope(self) -> None:
        if self.target_depot is None:
            raise OrganizeSessionError("Conflict review validation requires a target Depot")
        if not self._full_package_resolve_enabled():
            return
        accepted_items = [
            item
            for item in self.task.plan_items
            if item.user_decision == CandidateDecision.ACCEPT and self._plan_item_is_package_eligible(item)
        ]
        grouped: dict[str, list[OrganizePlanItem]] = {}
        for item in accepted_items:
            identity = package_identity(item, self.task.media_type)
            if identity is None:
                continue
            grouped.setdefault(identity.key, []).append(item)

        for key, items in grouped.items():
            identity = package_identity(items[0], self.task.media_type)
            if identity is None:
                continue
            source_ids = {item.source_candidate_id for item in items if item.source_candidate_id}
            if len(source_ids) > 1:
                raise OrganizeSessionError("Multiple accepted source packages target the same package")
            existing = (self.target_depot.path / identity.root_relative_path).exists()
            if not existing:
                continue
            state = self.task.conflict_review_states.get(key)
            if not state or not state.replace or state.source_candidate_id not in source_ids:
                raise OrganizeSessionError("Accepted package target already exists but has no replace intent")

    def apply_action(
        self,
        *,
        identity_key: str,
        source_candidate_id: str,
        action: ConflictReviewAction,
        tag_override: str | None = None,
    ) -> OrganizeSession:
        require_state(self.task, {OrganizeSessionState.IDENTIFIED})
        action = ConflictReviewAction(action)
        group = self.groups().get(identity_key)
        if group is None:
            raise OrganizeSessionError(
                f"Unknown conflict review: {identity_key}",
                code="conflict_review.unknown",
                details={"session_id": self.task.id, "identity_key": identity_key},
            )
        if source_candidate_id not in group.source_candidate_ids:
            raise OrganizeSessionError(
                f"Source candidate is not in conflict review: {source_candidate_id}",
                code="source_candidate.not_in_conflict_review",
                details={"session_id": self.task.id, "identity_key": identity_key, "source_candidate_id": source_candidate_id},
            )
        if action == ConflictReviewAction.TAG_VARIANT:
            self.apply_tag_variant(group, source_candidate_id=source_candidate_id, tag_override=tag_override)
            return self.task

        current_items = [item for item in group.items if item.source_candidate_id == source_candidate_id]
        if not current_items:
            raise OrganizeSessionError(
                f"Source candidate has no items in conflict review: {source_candidate_id}",
                code="source_candidate.not_in_conflict_review",
                details={"session_id": self.task.id, "identity_key": identity_key, "source_candidate_id": source_candidate_id},
            )

        if action == ConflictReviewAction.KEEP:
            if group.status != ConflictReviewStatus.DUPLICATE_SOURCE:
                raise OrganizeSessionError("Keep can only resolve duplicate source package conflicts without an existing target")
            self.select_source(group, source_candidate_id)
            self.task.conflict_review_states[identity_key] = ConflictReviewState(
                action=action,
                source_candidate_id=source_candidate_id,
                replace=False,
            )
            return self.task

        if action == ConflictReviewAction.KEEP_AND_REPLACE:
            if group.status != ConflictReviewStatus.DUPLICATE_SOURCE_AND_TARGET_EXISTS:
                raise OrganizeSessionError("Keep and replace can only resolve duplicate source conflicts with an existing target")
            self.select_source(group, source_candidate_id)
            self.task.conflict_review_states[identity_key] = ConflictReviewState(
                action=action,
                source_candidate_id=source_candidate_id,
                replace=True,
            )
            return self.task

        if action == ConflictReviewAction.REPLACE_TARGET:
            if group.status != ConflictReviewStatus.TARGET_EXISTS:
                raise OrganizeSessionError("Replace target can only resolve a single-source package that already exists")
            self.select_source(group, source_candidate_id)
            self.task.conflict_review_states[identity_key] = ConflictReviewState(
                action=action,
                source_candidate_id=source_candidate_id,
                replace=True,
            )
            return self.task

        raise OrganizeSessionError(f"Unsupported conflict review action: {action.value}")

    def select_source(self, group: ConflictReview, source_candidate_id: str) -> None:
        for item in group.items:
            if item.source_candidate_id == source_candidate_id:
                validate_candidate_decision(self.task, item, CandidateDecision.ACCEPT)
                item.user_decision = CandidateDecision.ACCEPT
            else:
                item.user_decision = None

    def plan_item_directly_switchable(self, item: OrganizePlanItem) -> bool:
        key = plan_item_package_key(item, self.task.media_type)
        if key is None:
            return True
        group = self.groups().get(key)
        if group is None or not group.action_required:
            return True
        state = self.task.conflict_review_states.get(key)
        if state is None or state.source_candidate_id != item.source_candidate_id:
            return False
        if group.status == ConflictReviewStatus.DUPLICATE_SOURCE and state.action == ConflictReviewAction.KEEP:
            return True
        if group.status == ConflictReviewStatus.TARGET_EXISTS and state.action == ConflictReviewAction.REPLACE_TARGET:
            return True
        if group.status == ConflictReviewStatus.DUPLICATE_SOURCE_AND_TARGET_EXISTS and state.action == ConflictReviewAction.KEEP_AND_REPLACE:
            return True
        return False

    def require_file_operation_allowed(self, source_candidate_id: str, source_file_id_value: str | None) -> None:
        if self.task.state != OrganizeSessionState.IDENTIFIED:
            return
        for group in self.groups().values():
            if not group.action_required:
                continue
            for item in group.items:
                if item.source_candidate_id != source_candidate_id:
                    continue
                if source_file_id_value is not None and item.source_file_id != source_file_id_value:
                    continue
                raise OrganizeSessionError(
                    "Source candidate participates in a conflict review; choose an action or rescan after changing source files"
                )

    def drop_stale(self) -> None:
        groups = ConflictReviews(self.task, target_depot=None).groups()
        self.task.conflict_review_states = {
            key: state
            for key, state in self.task.conflict_review_states.items()
            if key in groups and (state.source_candidate_id is None or state.source_candidate_id in groups[key].source_candidate_ids)
        }

    def drop_source(self, source_candidate_id: str) -> None:
        self.task.conflict_review_states = {
            key: state
            for key, state in self.task.conflict_review_states.items()
            if state.source_candidate_id != source_candidate_id
        }
        prefix = f"{source_candidate_id}\n"
        self.task.conflict_tag_overrides = {
            key: value
            for key, value in self.task.conflict_tag_overrides.items()
            if not key.startswith(prefix)
        }

    def apply_existing_tag_overrides(self, *, source_candidate_id: str | None = None) -> None:
        if not self.task.conflict_tag_overrides:
            return
        for override_key, raw_tag in list(self.task.conflict_tag_overrides.items()):
            stored_source_candidate_id, _, identity_key = override_key.partition("\n")
            if source_candidate_id is not None and stored_source_candidate_id != source_candidate_id:
                continue
            self.apply_tag_override(identity_key, raw_tag, source_candidate_id=stored_source_candidate_id)

    def apply_tag_override(
        self,
        identity_key: str,
        tag_override: str,
        *,
        source_candidate_id: str | None = None,
    ) -> bool:
        matched = False
        for item in self.task.plan_items:
            if source_candidate_id is not None and item.source_candidate_id != source_candidate_id:
                continue
            if plan_item_package_key(item, self.task.media_type) != identity_key:
                continue
            matched = apply_tag_override_to_plan_item(item, self.task.media_type, tag_override) or matched
        if matched:
            self.task.plan_items = sort_plan_items(self.task.plan_items)
        return matched

    def apply_tag_variant(
        self,
        group: ConflictReview,
        *,
        source_candidate_id: str,
        tag_override: str | None,
    ) -> None:
        raw_tag = (tag_override or "").strip()
        if not raw_tag:
            raise OrganizeSessionError("Tag variant requires a non-empty tag")
        current_items = [item for item in group.items if item.source_candidate_id == source_candidate_id]
        if not current_items:
            raise OrganizeSessionError(f"Source candidate has no items in conflict review: {source_candidate_id}")

        snapshots = [(item, item.preview, deepcopy(item.evidence), item.user_decision) for item in current_items]
        try:
            for item in current_items:
                if not apply_tag_override_to_plan_item(item, self.task.media_type, raw_tag):
                    raise OrganizeSessionError("Tag variant cannot be applied to this conflict review")
            new_identities = {package_identity(item, self.task.media_type) for item in current_items}
            if None in new_identities or len(new_identities) != 1:
                raise OrganizeSessionError("Tag variant produced an invalid package identity")
            new_identity = next(identity for identity in new_identities if identity is not None)
            current_item_ids = {item.id for item in current_items}
            for other in self.task.plan_items:
                if other.id in current_item_ids:
                    continue
                other_identity = package_identity(other, self.task.media_type)
                if other_identity and other_identity.key == new_identity.key and self._plan_item_is_package_eligible(other):
                    raise OrganizeSessionError("Tag variant conflicts with another source package")
            if self.target_depot and (self.target_depot.path / new_identity.root_relative_path).exists():
                raise OrganizeSessionError("Tag variant target package already exists")
        except Exception:
            for item, preview, evidence, decision in snapshots:
                item.preview = preview
                item.evidence = evidence
                item.user_decision = decision
            raise

        for item in current_items:
            validate_candidate_decision(self.task, item, CandidateDecision.ACCEPT)
            item.user_decision = CandidateDecision.ACCEPT
        self.task.conflict_tag_overrides[_conflict_tag_override_key(group.identity_key, source_candidate_id)] = raw_tag
        self.task.conflict_review_states.pop(group.identity_key, None)
        self.task.plan_items = sort_plan_items(self.task.plan_items)

    def _full_package_resolve_enabled(self) -> bool:
        if self.target_depot and self.task.media_type == MediaType.TV and effective_depot_resolve_mode(self.target_depot) == ResolveMode.INCREMENTAL:
            return False
        return True

    def _plan_item_is_package_eligible(self, item: OrganizePlanItem) -> bool:
        try:
            require_plan_item_eligible(self.task, item)
        except OrganizeSessionError:
            return False
        if package_identity(item, self.task.media_type) is None:
            return False
        return plan_item_acceptance(self.task, item).can_accept


def conflict_reviews(task: OrganizeSession, *, target_depot: Depot | None = None) -> dict[str, ConflictReview]:
    return ConflictReviews(task, target_depot=target_depot).groups()


def conflict_review_reads(
    task: OrganizeSession,
    candidate_plan_items: list[OrganizePlanItem],
    *,
    target_depot: Depot | None,
) -> list[ConflictReviewRead]:
    if task.state.value not in {"identified", "organizing"}:
        return []
    if target_depot and task.media_type == MediaType.TV and effective_depot_resolve_mode(target_depot) == ResolveMode.INCREMENTAL:
        return []
    review_groups = conflict_reviews(task, target_depot=target_depot)
    candidate_groups = _package_group_items(candidate_plan_items, task.media_type)
    reviews: list[ConflictReviewRead] = []
    for key, items in sorted(candidate_groups.items(), key=lambda item: item[0]):
        identity = package_identity(items[0], task.media_type)
        if identity is None:
            continue
        group = review_groups.get(key)
        if group is None:
            continue
        candidate_group_items = [item for item in group.items if item.source_candidate_id == items[0].source_candidate_id]
        if not candidate_group_items:
            continue
        conflict_reason = _conflict_review_conflict_reason(group.status.value)
        state = task.conflict_review_states.get(key)
        reviews.append(
            ConflictReviewRead(
                identity_key=key,
                kind=identity.kind,
                status=group.status.value,
                display_path=identity.root_relative_path,
                root_relative_path=identity.root_relative_path,
                plan_item_ids=[item.id for item in _sort_plan_items_for_read(candidate_group_items)],
                source_candidate_ids=list(group.source_candidate_ids),
                accepted_source_candidate_ids=list(group.accepted_source_candidate_ids),
                action_required=group.action_required,
                conflict=bool(conflict_reason),
                conflict_reason=conflict_reason,
                existing=group.existing,
                action=state.action.value if state and state.action else None,
                action_source_candidate_id=state.source_candidate_id if state else None,
                replace_intent=bool(state and state.replace and state.source_candidate_id == items[0].source_candidate_id),
                source_tag=planned_tag(candidate_group_items[0]),
            )
        )
    return reviews


def apply_conflict_review_defaults(task: OrganizeSession, *, target_depot: Depot | None = None) -> None:
    ConflictReviews(task, target_depot=target_depot).apply_defaults()


def validate_accepted_conflict_scope(task: OrganizeSession, *, target_depot: Depot) -> None:
    ConflictReviews(task, target_depot=target_depot).validate_accepted_scope()


def apply_conflict_review_action(
    task: OrganizeSession,
    *,
    identity_key: str,
    source_candidate_id: str,
    action: ConflictReviewAction,
    tag_override: str | None = None,
    target_depot: Depot | None = None,
) -> OrganizeSession:
    return ConflictReviews(task, target_depot=target_depot).apply_action(
        identity_key=identity_key,
        source_candidate_id=source_candidate_id,
        action=action,
        tag_override=tag_override,
    )


def apply_existing_tag_overrides(task: OrganizeSession, *, source_candidate_id: str | None = None) -> None:
    ConflictReviews(task).apply_existing_tag_overrides(source_candidate_id=source_candidate_id)


def apply_tag_override(
    task: OrganizeSession,
    identity_key: str,
    tag_override: str,
    *,
    source_candidate_id: str | None = None,
) -> bool:
    return ConflictReviews(task).apply_tag_override(identity_key, tag_override, source_candidate_id=source_candidate_id)


def plan_item_package_key(item: OrganizePlanItem, media_type: MediaType) -> str | None:
    identity = package_identity(item, media_type)
    return identity.key if identity else None


def _conflict_review_conflict_reason(status: str) -> str | None:
    if status == "duplicate_source":
        return "duplicate_source_package"
    if status == "target_exists":
        return "package_exists"
    if status == "duplicate_source_and_target_exists":
        return "duplicate_source_package_and_package_exists"
    return None


def _package_group_items(plan_items: list[OrganizePlanItem], media_type: MediaType) -> dict[str, list[OrganizePlanItem]]:
    groups: dict[str, list[OrganizePlanItem]] = {}
    for item in plan_items:
        identity = package_identity(item, media_type)
        if identity is None:
            continue
        groups.setdefault(identity.key, []).append(item)
    return groups


def _sort_plan_items_for_read(items: list[OrganizePlanItem]) -> list[OrganizePlanItem]:
    return sorted(items, key=lambda item: (item.source_path.as_posix().lower(), item.id))


def _conflict_tag_override_key(identity_key: str, source_candidate_id: str) -> str:
    return f"{source_candidate_id}\n{identity_key}"
