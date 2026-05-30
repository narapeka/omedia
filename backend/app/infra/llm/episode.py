from __future__ import annotations

from typing import Sequence

from app.core.error import MatchError
from app.domain.tv import EpisodeLLMResult


def validate_results(
    input_filenames: Sequence[str],
    raw_items: Sequence[dict],
) -> dict[str, EpisodeLLMResult]:
    allowed = set(input_filenames)
    results: dict[str, EpisodeLLMResult] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename", ""))
        if filename not in allowed:
            continue
        try:
            season = int(item.get("season", 1))
            episode = int(item.get("episode", 1))
            end_episode_raw = item.get("end_episode")
            end_episode = int(end_episode_raw) if end_episode_raw is not None else None
        except (TypeError, ValueError):
            raise MatchError(f"Invalid LLM episode result for {filename}") from None
        results[filename] = EpisodeLLMResult(filename, season, episode, end_episode)
    return results
