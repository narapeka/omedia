from __future__ import annotations

import unittest

from app.engines.rule.references import bundled_rule_references


class RuleReferenceTests(unittest.TestCase):
    def test_bundled_rule_references_include_curated_country_list(self) -> None:
        references = bundled_rule_references()
        countries = references["countries"]
        codes = [country["iso_3166_1"] for country in countries]

        self.assertEqual(references["source"], "bundled")
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(
            {
                "AR",
                "AU",
                "BE",
                "BR",
                "CA",
                "CH",
                "CL",
                "CO",
                "CZ",
                "DE",
                "DK",
                "EG",
                "ES",
                "FR",
                "GR",
                "HK",
                "IL",
                "IN",
                "IQ",
                "IR",
                "IT",
                "JP",
                "MM",
                "MO",
                "MX",
                "MY",
                "NL",
                "NO",
                "PH",
                "PK",
                "PL",
                "RU",
                "SE",
                "SG",
                "TH",
                "TR",
                "US",
                "VN",
                "CN",
                "GB",
                "TW",
                "NZ",
                "SA",
                "LA",
                "KP",
                "KR",
                "PT",
                "MN",
            }.issubset(set(codes))
        )

    def test_bundled_rule_references_include_chinese_genre_names(self) -> None:
        references = bundled_rule_references()
        movie_genres = {genre["id"]: genre for genre in references["movie_genres"]}
        tv_genres = {genre["id"]: genre for genre in references["tv_genres"]}

        self.assertEqual(movie_genres[28]["name_zh"], "动作")
        self.assertEqual(movie_genres[878]["name_zh"], "科幻")
        self.assertEqual(tv_genres[10759]["name_zh"], "动作冒险")
        self.assertEqual(tv_genres[10767]["name_zh"], "脱口秀")


if __name__ == "__main__":
    unittest.main()
