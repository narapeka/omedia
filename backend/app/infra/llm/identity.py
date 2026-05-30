from __future__ import annotations

from app.domain.media import MediaCandidate, MediaType


def input_for_candidate(candidate: MediaCandidate, *, include_candidate_id: bool = False) -> dict[str, object]:
    item: dict[str, object] = {
        "media_type": candidate.media_type.value,
        "folder_name": _folder_name(candidate),
        "file_name": _representative_file(candidate),
    }
    if include_candidate_id:
        item = {"candidate_id": candidate.id, **item}
    return item


def _folder_name(candidate: MediaCandidate) -> str | None:
    if candidate.media_type == MediaType.MOVIE and candidate.structure == "standalone_file":
        return None
    if candidate.media_type == MediaType.MOVIE and candidate.candidate_path.suffix and not candidate.files:
        return None
    return candidate.candidate_path.name or candidate.display_name


def _representative_file(candidate: MediaCandidate) -> str | None:
    primary_files = sorted(
        [file for file in candidate.files if not file.is_sidecar],
        key=lambda item: item.relative_path.as_posix().lower(),
    )
    if primary_files:
        return primary_files[0].relative_path.as_posix()
    if candidate.media_type == MediaType.MOVIE and _folder_name(candidate) is None:
        return candidate.candidate_path.name
    return None
