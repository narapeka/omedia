from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request

from app.core.error import MatchError
from app.domain.match import MatchHint
from app.domain.media import MediaCandidate
from app.domain.tv import EpisodeLLMResult
from app.infra.http.requester import ProviderRequester, RequesterPolicy
from app.infra.llm.episode import validate_results
from app.infra.llm.identity import input_for_candidate
from app.infra.llm.payload import first_object, hint_from_payload, loads_json_from_content, objects, text
from app.infra.llm.prompt import PromptSet, render


LLM_TIMEOUT_SECONDS = 300.0


LLM_REQUESTER_POLICY = RequesterPolicy(
    retry_statuses=frozenset({429, 500, 502, 503, 504}),
    max_retries=3,
    backoff_initial_seconds=2.0,
    backoff_max_seconds=60.0,
    max_concurrency=4,
)


class OpenAICompatibleExtractor:
    """OpenAI-compatible JSON extractor for identity hints and TV file resolution."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        model: str | None = None,
        prompt_dir: str | Path | None = None,
        prompts: PromptSet | None = None,
        timeout_seconds: float = LLM_TIMEOUT_SECONDS,
        rate_limit: float = 0.33,
        proxy: str | None = None,
        requester: ProviderRequester | None = None,
    ):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model or "gpt-4o-mini"
        self.prompts = prompts or PromptSet.from_dir(prompt_dir)
        self.timeout_seconds = timeout_seconds
        self.requester = requester or ProviderRequester(
            name="llm",
            rate_limit=rate_limit,
            proxy=proxy,
            policy=LLM_REQUESTER_POLICY,
        )

    def extract_hint(self, candidate: MediaCandidate) -> MatchHint:
        input_json = json.dumps(input_for_candidate(candidate), ensure_ascii=False, indent=2)
        payload = self._chat_json(
            [
                {
                    "role": "system",
                    "content": self.prompts.media_match_system,
                },
                {
                    "role": "user",
                    "content": render(self.prompts.media_match_user, INPUT_JSON=input_json),
                },
            ]
        )
        payload = first_object(payload)
        return hint_from_payload(payload)

    def extract_hints(
        self,
        candidates: Sequence[MediaCandidate],
        *,
        batch_size: int = 50,
    ) -> dict[str, MatchHint]:
        if not candidates:
            return {}
        if batch_size <= 0:
            raise MatchError("LLM batch size must be greater than zero")
        results: dict[str, MatchHint] = {}
        for chunk_start in range(0, len(candidates), batch_size):
            chunk = candidates[chunk_start:chunk_start + batch_size]
            input_json = json.dumps(
                [
                    input_for_candidate(candidate, include_candidate_id=True)
                    for candidate in chunk
                ],
                ensure_ascii=False,
                indent=2,
            )
            payload = self._chat_json(
                [
                    {
                        "role": "system",
                        "content": self.prompts.media_match_batch_system,
                    },
                    {
                        "role": "user",
                        "content": render(self.prompts.media_match_batch_user, INPUT_JSON=input_json),
                    },
                ]
            )
            allowed = {candidate.id for candidate in chunk}
            for item in objects(payload):
                candidate_id = text(item.get("candidate_id") or item.get("id"))
                if candidate_id not in allowed:
                    continue
                results[candidate_id] = hint_from_payload(item)
        return results

    def extract_episodes(
        self,
        *,
        show_name: str,
        filenames: Sequence[str],
        tmdb_context: str = "",
        chunk_size: int = 100,
    ):
        if chunk_size <= 0:
            raise MatchError("TV resolution chunk size must be greater than zero")
        results: dict[str, EpisodeLLMResult] = {}
        keys = list(filenames)
        for chunk_start in range(0, len(keys), chunk_size):
            chunk = keys[chunk_start:chunk_start + chunk_size]
            results.update(
                self._extract_episode_chunk(
                    show_name=show_name,
                    filenames=chunk,
                    tmdb_context=tmdb_context,
                )
            )
        return results

    def _extract_episode_chunk(
        self,
        *,
        show_name: str,
        filenames: Sequence[str],
        tmdb_context: str,
    ) -> dict[str, EpisodeLLMResult]:
        filenames_json = json.dumps(list(filenames), ensure_ascii=False, indent=2)
        payload = self._chat_json(
            [
                {
                    "role": "system",
                    "content": self.prompts.tv_resolution_system,
                },
                {
                    "role": "user",
                    "content": render(
                        self.prompts.tv_resolution_user,
                        SHOW_NAME=show_name,
                        FILENAMES_JSON=filenames_json,
                        TMDB_CONTEXT=tmdb_context or "No TMDB episode context was provided.",
                    ),
                },
            ]
        )
        if isinstance(payload, list):
            raw_items = payload
        else:
            raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return validate_results(filenames, raw_items)

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any] | list[Any]:
        request_payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            payload = self._post_chat(request_payload)
        except HTTPError as exc:
            if exc.code not in {400, 422}:
                raise MatchError(f"LLM request failed: {exc}") from exc
            retry_payload = dict(request_payload)
            retry_payload.pop("response_format", None)
            try:
                payload = self._post_chat(retry_payload)
            except HTTPError as retry_exc:
                raise MatchError(f"LLM request failed: {retry_exc}") from retry_exc

        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return {}
        return loads_json_from_content(content)

    def _post_chat(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            body = self.requester.read(request, timeout_seconds=self.timeout_seconds)
            return json.loads(body.decode("utf-8"))
        except HTTPError:
            raise
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MatchError(f"LLM request failed: {exc}") from exc

