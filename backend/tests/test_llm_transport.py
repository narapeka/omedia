from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from email.message import Message
from urllib.error import HTTPError
from unittest.mock import patch

from app.domain.media import MediaType
from app.domain.media import MediaCandidate, MediaFile
from app.core.error import ConfigurationError
from app.infra.llm.client import OpenAICompatibleExtractor
from app.infra.llm.prompt import PromptSet
from app.boot.match import MatchRuntime
from app.services.config.values import ProviderSettings
from support import FakeRequester, make_startup_settings


class LLMTransportTests(unittest.TestCase):
    def test_post_chat_uses_requester(self) -> None:
        requester = FakeRequester([chat_response({"title": "ok"})])
        extractor = make_extractor(requester=requester)

        result = extractor._post_chat({"model": "gpt-test", "messages": []})

        self.assertEqual(result["choices"][0]["message"]["content"], '{"title": "ok"}')
        self.assertEqual(requester.calls[0]["url"], "https://llm.example/v1/chat/completions")
        self.assertEqual(requester.calls[0]["timeout_seconds"], 300.0)
        self.assertEqual(requester.calls[0]["headers"]["Authorization"], "Bearer key")

    def test_response_format_fallback_still_runs_after_400(self) -> None:
        requester = FakeRequester([http_error(400), chat_response({"items": []})])
        extractor = make_extractor(requester=requester)

        result = extractor._chat_json([{"role": "user", "content": "hello"}])

        self.assertEqual(result, {"items": []})
        self.assertEqual(len(requester.calls), 2)
        self.assertIn("response_format", requester.calls[0]["payload"])
        self.assertNotIn("response_format", requester.calls[1]["payload"])

    def test_runtime_wires_configured_llm_requester(self) -> None:
        runtime = MatchRuntime(
            make_startup_settings(
                providers=ProviderSettings(
                    llm_api_key="llm-key",
                    llm_rate_limit=0.25,
                    llm_proxy="http://127.0.0.1:10810",
                )
            )
        )

        self.assertIsNotNone(runtime.llm)
        self.assertEqual(runtime.llm.requester.rate_limit, 0.25)
        self.assertEqual(runtime.llm.timeout_seconds, 300.0)
        self.assertEqual(runtime.llm.requester.proxy, "http://127.0.0.1:10810")

    def test_runtime_requires_yaml_llm_key_even_when_environment_has_key(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            runtime = MatchRuntime(make_startup_settings(providers=ProviderSettings()))

        with self.assertRaisesRegex(ConfigurationError, "LLM provider settings"):
            _ = runtime.llm

    def test_identity_llm_uses_raw_folder_and_file_names_for_tv(self) -> None:
        requester = FakeRequester(
            [
                chat_response(
                    {
                        "chinese_title": "一人之下",
                        "english_title": "The Outcast",
                        "year": None,
                        "tmdb_id": None,
                        "season": 2,
                        "episode": 1,
                    }
                )
            ]
        )
        extractor = make_extractor(requester=requester)
        candidate_path = Path("source") / "一人之下 第二季"
        candidate = MediaCandidate(
            id="tv",
            media_type=MediaType.TV,
            source_root=Path("source"),
            candidate_path=candidate_path,
            display_name=candidate_path.name,
            files=[
                MediaFile(
                    path=candidate_path / "The.Outcast.S02E01.1080p.mkv",
                    relative_path=Path("The.Outcast.S02E01.1080p.mkv"),
                    extension=".mkv",
                )
            ],
            structure="direct_files",
        )

        hint = extractor.extract_hint(candidate)
        user_content = requester.calls[0]["payload"]["messages"][1]["content"]

        self.assertIn('"folder_name": "一人之下 第二季"', user_content)
        self.assertIn('"file_name": "The.Outcast.S02E01.1080p.mkv"', user_content)
        self.assertNotIn("display_name", user_content)
        self.assertNotIn("source_root", user_content)
        self.assertEqual([title.value for title in hint.titles], ["一人之下", "The Outcast"])

    def test_batch_identity_llm_uses_movie_standalone_file_shape(self) -> None:
        requester = FakeRequester(
            [
                chat_response(
                    {
                        "items": [
                            {
                                "candidate_id": "movie",
                                "chinese_title": None,
                                "english_title": "Avatar",
                                "year": 2009,
                                "tmdb_id": 19995,
                            }
                        ]
                    }
                )
            ]
        )
        extractor = make_extractor(requester=requester)
        candidate = MediaCandidate(
            id="movie",
            media_type=MediaType.MOVIE,
            source_root=Path("source"),
            candidate_path=Path("source") / "Avatar.2009.{tmdb-19995}.mkv",
            display_name="Avatar.2009.{tmdb-19995}",
            structure="standalone_file",
        )

        hints = extractor.extract_hints([candidate])
        user_content = requester.calls[0]["payload"]["messages"][1]["content"]

        self.assertIn('"candidate_id": "movie"', user_content)
        self.assertIn('"folder_name": null', user_content)
        self.assertIn('"file_name": "Avatar.2009.{tmdb-19995}.mkv"', user_content)
        self.assertNotIn("path_name", user_content)
        self.assertEqual(hints["movie"].tmdb_id, 19995)


def make_extractor(*, requester: FakeRequester):
    prompts = PromptSet(
        media_match_system="system",
        media_match_user="{{INPUT_JSON}}",
        media_match_batch_system="batch system",
        media_match_batch_user="{{INPUT_JSON}}",
        tv_resolution_system="resolution system",
        tv_resolution_user="{{SHOW_NAME}} {{FILENAMES_JSON}} {{TMDB_CONTEXT}}",
    )
    return OpenAICompatibleExtractor(
        "key",
        base_url="https://llm.example/v1/",
        model="gpt-test",
        prompts=prompts,
        requester=requester,
    )


def chat_response(content) -> bytes:
    payload = {"choices": [{"message": {"content": json.dumps(content)}}]}
    return json.dumps(payload).encode("utf-8")


def http_error(code: int) -> HTTPError:
    return HTTPError("https://llm.example/v1/chat/completions", code, "error", Message(), io.BytesIO(b"error"))


if __name__ == "__main__":
    unittest.main()
