from __future__ import annotations

import unittest

from app.engines.plan.movie.evidence import (
    MOVIE_PLAN_EVIDENCE_KEY,
    movie_plan_extension,
    movie_plan_ignored_duplicate_subtitles,
    movie_plan_media_kind,
    movie_plan_part_token,
    movie_plan_tag,
    movie_plan_tag_suffix,
    set_movie_plan_tag,
)
from app.engines.plan.tv.evidence import (
    TV_EPISODE_PLAN_EVIDENCE_KEY,
    set_tv_episode_plan_tag,
    set_tv_episode_title_evidence,
    tv_episode_plan_ignored_duplicate_subtitles,
    tv_episode_plan_int,
    tv_episode_plan_media_kind,
    tv_episode_plan_resolution_status,
    tv_episode_plan_tag,
    tv_episode_plan_tag_suffix,
)
from app.domain.tv import episode_number_value


class PlanEvidenceAccessorTests(unittest.TestCase):
    def test_movie_plan_accessors_read_and_update_tag(self) -> None:
        evidence = {
            MOVIE_PLAN_EVIDENCE_KEY: {
                "media_kind": "primary",
                "extension": ".mkv",
                "part_token": "CD1",
                "ignored_duplicate_subtitles": ["extras/dup.zh.srt"],
            }
        }

        self.assertEqual(movie_plan_media_kind(evidence), "primary")
        self.assertEqual(movie_plan_extension(evidence), ".mkv")
        self.assertEqual(movie_plan_part_token(evidence), "CD1")
        self.assertEqual(movie_plan_ignored_duplicate_subtitles(evidence), ["extras/dup.zh.srt"])

        self.assertTrue(set_movie_plan_tag(evidence, "Directors Cut", "[Directors Cut]"))
        self.assertEqual(movie_plan_tag(evidence), "Directors Cut")
        self.assertEqual(movie_plan_tag_suffix(evidence), "[Directors Cut]")

        self.assertTrue(set_movie_plan_tag(evidence, None, None))
        self.assertIsNone(movie_plan_tag(evidence))
        self.assertIsNone(movie_plan_tag_suffix(evidence))

    def test_tv_plan_accessors_read_and_update_tag_and_title(self) -> None:
        evidence = {
            TV_EPISODE_PLAN_EVIDENCE_KEY: {
                "media_kind": "subtitle",
                "season": "2",
                "episode": "3",
                "resolution": {"status": "applied"},
                "ignored_duplicate_subtitles": ["S02E03.zh.srt"],
            }
        }

        self.assertEqual(tv_episode_plan_media_kind(evidence), "subtitle")
        self.assertEqual(tv_episode_plan_int(evidence, "season"), 2)
        self.assertEqual(tv_episode_plan_int(evidence, "episode"), 3)
        self.assertEqual(tv_episode_plan_resolution_status(evidence), "applied")
        self.assertEqual(tv_episode_plan_ignored_duplicate_subtitles(evidence), ["S02E03.zh.srt"])

        self.assertTrue(set_tv_episode_plan_tag(evidence, "WEB", "[WEB]"))
        self.assertEqual(tv_episode_plan_tag(evidence), "WEB")
        self.assertEqual(tv_episode_plan_tag_suffix(evidence), "[WEB]")

        self.assertTrue(set_tv_episode_title_evidence(evidence, "Pilot", "metadata"))
        plan = evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]
        self.assertEqual(plan["episode_title"], "Pilot")
        self.assertEqual(plan["episode_title_source"], "metadata")

    def test_plan_accessors_tolerate_missing_or_malformed_payloads(self) -> None:
        self.assertIsNone(movie_plan_media_kind({}))
        self.assertEqual(movie_plan_ignored_duplicate_subtitles({MOVIE_PLAN_EVIDENCE_KEY: "bad"}), [])
        self.assertFalse(set_movie_plan_tag({}, "tag", "[tag]"))

        self.assertIsNone(tv_episode_plan_media_kind({TV_EPISODE_PLAN_EVIDENCE_KEY: "bad"}))
        self.assertIsNone(tv_episode_plan_int({TV_EPISODE_PLAN_EVIDENCE_KEY: {"season": "bad"}}, "season"))
        self.assertFalse(set_tv_episode_plan_tag({}, "tag", "[tag]"))

    def test_episode_number_value_is_the_tv_number_coercion_owner(self) -> None:
        self.assertEqual(episode_number_value("02"), 2)
        self.assertEqual(episode_number_value(0), 0)
        self.assertIsNone(episode_number_value("bad"))
        self.assertIsNone(episode_number_value(None))


if __name__ == "__main__":
    unittest.main()
