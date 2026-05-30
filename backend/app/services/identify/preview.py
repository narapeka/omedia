from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy
from app.domain.match import MatchResult
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile
from app.domain.organize import CandidatePreview, OrganizePlanItem, plan_item_id, source_file_id
from app.domain.rule import OrganizeRule
from app.domain.tv import TVEpisodeFile
from app.engines.name.renderer import (
    MovieNamingInput,
    NamingRenderResult,
    TVNamingInput,
    render_movie_path,
    render_tv_path,
)
from app.engines.rule.organize import OrganizeRuleContext, OrganizeRuleEngine
from app.engines.plan.movie.evidence import MOVIE_PLAN_EVIDENCE_KEY, movie_plan_evidence, set_movie_plan_tag
from app.engines.plan.movie.planner import plan_movie_files_for_candidate
from app.engines.plan.tv.evidence import TV_EPISODE_PLAN_EVIDENCE_KEY, set_tv_episode_plan_tag, tv_episode_plan_evidence
from app.engines.plan.tv.planner import TVEpisodePlanner, plan_episode_files
from app.engines.name.movie.source import extract_movie_tag
from app.engines.name.tv.source import extract_last_tag
from app.engines.plan.tv.catalog import episode_title_from_metadata
from app.services.identify.candidate import metadata_from_match_result
from app.services.identify.evidence import match_evidence_payload


def build_preview_from_metadata(
    *,
    source_path: Path,
    source_root: Path,
    media_type: MediaType,
    metadata: dict,
    organize_rule: OrganizeRule | None = None,
    tv_episode_title: str | None = None,
    tv_episode: TVEpisodeFile | None = None,
    movie_part_token: str | None = None,
    tag_suffix: str | None = None,
) -> CandidatePreview:
    relative_path = _relative_path(source_path, source_root)
    rule_result = OrganizeRuleEngine().match(
        organize_rule,
        OrganizeRuleContext(tmdb=metadata, relative_path=relative_path),
    )
    render_result = _render_candidate_path(
        media_type=media_type,
        source_path=source_path,
        metadata=metadata,
        tv_episode_title=tv_episode_title,
        tv_episode=tv_episode,
        movie_part_token=movie_part_token,
        tag_suffix=tag_suffix,
    )
    proposed = render_result.relative_path
    if proposed is not None and rule_result.bucket:
        proposed = Path(rule_result.bucket) / proposed
    return CandidatePreview(
        preview_bucket=rule_result.bucket or None,
        matched_category=rule_result.matched_category,
        proposed_relative_path=proposed,
        render_warnings=[*rule_result.warnings, *render_result.warnings],
    )


def build_candidate_preview(
    *,
    source_candidate_id: str,
    source_file_id: str,
    item_id: str,
    source_path: Path,
    source_root: Path,
    match_result: MatchResult,
    policy: OrganizePolicy,
    organize_rule: OrganizeRule | None = None,
    tv_episode_title: str | None = None,
    tv_episode: TVEpisodeFile | None = None,
    movie_part_token: str | None = None,
    extra_evidence: Mapping[str, object] | None = None,
    tag_suffix: str | None = None,
    tag_raw: str | None = None,
) -> OrganizePlanItem:
    metadata = metadata_from_match_result(match_result)
    preview = build_preview_from_metadata(
        source_path=source_path,
        source_root=source_root,
        media_type=match_result.media_type,
        metadata=metadata,
        organize_rule=organize_rule,
        tv_episode_title=tv_episode_title,
        tv_episode=tv_episode,
        movie_part_token=movie_part_token,
        tag_suffix=tag_suffix,
    )
    stat = _safe_stat(source_path)
    evidence = match_evidence_payload(match_result.evidence)
    if tv_episode is not None:
        evidence[TV_EPISODE_PLAN_EVIDENCE_KEY] = tv_episode_plan_evidence(tv_episode)
    if extra_evidence:
        evidence.update(extra_evidence)
    if tag_raw:
        set_movie_plan_tag(evidence, tag_raw, tag_suffix)
        set_tv_episode_plan_tag(evidence, tag_raw, tag_suffix)
    return OrganizePlanItem(
        id=item_id,
        source_candidate_id=source_candidate_id,
        source_file_id=source_file_id,
        source_path=source_path,
        source_size=stat[0],
        source_mtime=stat[1],
        confidence=match_result.confidence,
        metadata=metadata or None,
        metadata_source="auto" if metadata else None,
        evidence=evidence,
        preview=preview,
        user_decision=None,
    )


@dataclass(frozen=True)
class Preview:
    media_candidate: MediaCandidate
    source_root: Path
    match_result: MatchResult
    policy: OrganizePolicy
    organize_rule: OrganizeRule | None = None
    extensions: MediaExtensionPolicy | None = None
    tv_episode_planner: TVEpisodePlanner | None = None

    @classmethod
    def for_candidate(
        cls,
        *,
        media_candidate: MediaCandidate,
        source_root: Path,
        match_result: MatchResult,
        policy: OrganizePolicy,
        organize_rule: OrganizeRule | None = None,
        extensions: MediaExtensionPolicy | None = None,
        tv_episode_planner: TVEpisodePlanner | None = None,
    ) -> list[OrganizePlanItem]:
        return cls(
            media_candidate=media_candidate,
            source_root=source_root,
            match_result=match_result,
            policy=policy,
            organize_rule=organize_rule,
            extensions=extensions,
            tv_episode_planner=tv_episode_planner,
        ).build()

    def build(self) -> list[OrganizePlanItem]:
        media_candidate = self.media_candidate
        source_root = self.source_root
        match_result = self.match_result
        policy = self.policy
        organize_rule = self.organize_rule
        extensions = self.extensions
        tv_episode_planner = self.tv_episode_planner

        if media_candidate.media_type == MediaType.TV and media_candidate.candidate_path.is_dir():
            candidates: list[OrganizePlanItem] = []
            effective_extensions = _tv_extensions(media_candidate, extensions)
            files_by_path = {file.path: file for file in media_candidate.files}
            planned_episodes = (
                tv_episode_planner.plan(media_candidate, match_result, include_subtitles=True)
                if tv_episode_planner is not None
                else plan_episode_files(
                    media_candidate,
                    extensions=effective_extensions,
                    include_subtitles=True,
                )
            )
            tag = extract_last_tag(media_candidate.candidate_path.name)
            for planned_episode in planned_episodes:
                file = files_by_path[planned_episode.source_path]
                item_id = plan_item_id(media_candidate.id, file.relative_path)
                candidates.append(
                    build_candidate_preview(
                        source_candidate_id=media_candidate.id,
                        source_file_id=source_file_id(media_candidate.id, file.relative_path),
                        item_id=item_id,
                        source_path=planned_episode.source_path,
                        source_root=source_root,
                        match_result=_match_for_source_file(match_result, item_id),
                        policy=policy,
                        organize_rule=organize_rule,
                        tv_episode_title=planned_episode.title,
                        tv_episode=planned_episode,
                        tag_suffix=tag.rendered_suffix if tag else None,
                        tag_raw=tag.raw_tag if tag else None,
                    )
                )
            return candidates

        if media_candidate.media_type == MediaType.MOVIE and extensions is not None:
            candidates: list[OrganizePlanItem] = []
            files_by_path = {file.path: file for file in media_candidate.files}
            tag = extract_movie_tag(media_candidate.candidate_path.stem if media_candidate.candidate_path.suffix else media_candidate.candidate_path.name)
            for planned_file in plan_movie_files_for_candidate(media_candidate, extensions):
                file = files_by_path.get(planned_file.source_path)
                relative_path = file.relative_path if file is not None else _relative_path(planned_file.source_path, media_candidate.candidate_path.parent)
                item_id = plan_item_id(media_candidate.id, relative_path)
                candidates.append(
                    build_candidate_preview(
                        source_candidate_id=media_candidate.id,
                        source_file_id=source_file_id(media_candidate.id, relative_path),
                        item_id=item_id,
                        source_path=planned_file.source_path,
                        source_root=source_root,
                        match_result=_match_for_source_file(match_result, item_id)
                        if file is not None
                        else match_result,
                        policy=policy,
                        organize_rule=organize_rule,
                        extra_evidence={MOVIE_PLAN_EVIDENCE_KEY: movie_plan_evidence(planned_file)},
                        movie_part_token=planned_file.part_token,
                        tag_suffix=tag.rendered_suffix if tag else None,
                        tag_raw=tag.raw_tag if tag else None,
                    )
                )
            return candidates

        source = _first_media_file(media_candidate)
        relative_path = source.relative_path if source is not None else _relative_path(media_candidate.candidate_path, source_root)
        item_id = plan_item_id(media_candidate.id, relative_path)
        return [
            build_candidate_preview(
                source_candidate_id=media_candidate.id,
                source_file_id=source_file_id(media_candidate.id, relative_path),
                item_id=item_id,
                source_path=media_candidate.candidate_path,
                source_root=source_root,
                match_result=match_result,
                policy=policy,
                organize_rule=organize_rule,
            )
        ]


def _tv_extensions(media_candidate: MediaCandidate, extensions: MediaExtensionPolicy | None) -> MediaExtensionPolicy:
    if extensions is not None:
        return extensions
    video = frozenset(file.extension.lower() for file in media_candidate.files if not file.is_sidecar)
    sidecar = frozenset(file.extension.lower() for file in media_candidate.files if file.is_sidecar)
    return MediaExtensionPolicy(video=video, subtitle=frozenset(), sidecar=sidecar)


def _match_for_source_file(
    match_result: MatchResult,
    candidate_id: str,
) -> MatchResult:
    return MatchResult(
        candidate_id=candidate_id,
        media_type=match_result.media_type,
        confidence=match_result.confidence,
        title=match_result.title,
        original_title=match_result.original_title,
        year=match_result.year,
        tmdb_id=match_result.tmdb_id,
        selected_external_id=match_result.selected_external_id,
        evidence=list(match_result.evidence),
        metadata=dict(match_result.metadata),
    )


def _relative_path(source_path: Path, source_root: Path) -> Path:
    try:
        return source_path.relative_to(source_root)
    except ValueError:
        return Path(source_path.name)


def _safe_stat(path: Path) -> tuple[int | None, float | None]:
    try:
        stat = path.stat()
        return stat.st_size, stat.st_mtime
    except OSError:
        return None, None


def _first_media_file(media_candidate: MediaCandidate) -> MediaFile | None:
    return sorted(media_candidate.files, key=lambda file: file.relative_path.as_posix().lower())[0] if media_candidate.files else None


def _render_candidate_path(
    media_type: MediaType,
    source_path: Path,
    metadata: dict,
    *,
    tv_episode_title: str | None = None,
    tv_episode: TVEpisodeFile | None = None,
    movie_part_token: str | None = None,
    tag_suffix: str | None = None,
) -> NamingRenderResult:
    if media_type == MediaType.MOVIE:
        return render_movie_path(
            MovieNamingInput(
                title=metadata.get("title"),
                year=metadata.get("release_year") or metadata.get("year"),
                tmdb_id=metadata.get("tmdb_id"),
                extension=source_path.suffix,
                part_token=movie_part_token,
                tag_suffix=tag_suffix,
            )
        )
    if tv_episode is None:
        return NamingRenderResult(None, ["missing_tv_episode_plan"])
    return render_tv_path(
        TVNamingInput(
            title=metadata.get("title") or metadata.get("name"),
            year=metadata.get("release_year") or metadata.get("year"),
            tmdb_id=metadata.get("tmdb_id"),
            season=tv_episode.season_number,
            episode=tv_episode.episode_number,
            episode_title=tv_episode_title
            or tv_episode.title
            or episode_title_from_metadata(metadata, tv_episode.season_number, tv_episode.episode_number),
            extension=tv_episode.extension or source_path.suffix,
            end_episode=tv_episode.end_episode_number,
            tag_suffix=tag_suffix,
        )
    )

