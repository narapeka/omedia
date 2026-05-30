from __future__ import annotations

import unittest
from pathlib import Path

from app.core.error import ConfigurationError
from app.domain.rule import (
    OrganizeRule,
    RuleCondition,
    RuleOperator,
    RuleCategory,
    TransferRule,
    rule_condition_value_is_empty,
    rule_value_contains,
    rule_value_equals,
)
from app.engines.rule.bucket import render_rule_bucket, validate_rule_bucket
from app.engines.rule.organize import OrganizeRuleContext, OrganizeRuleEngine
from app.engines.rule.transfer import TransferRuleContext, TransferRuleEngine


class RuleEngineTests(unittest.TestCase):
    def test_rule_condition_value_empty_helper_matches_rule_validation_semantics(self) -> None:
        for value in (None, "", " ", [], [""], (" ",), {None}):
            with self.subTest(value=value):
                self.assertTrue(rule_condition_value_is_empty(value))
        for value in ("Avatar", 0, False, ["Avatar"], [0]):
            with self.subTest(value=value):
                self.assertFalse(rule_condition_value_is_empty(value))

    def test_rule_value_helpers_match_rule_engine_comparison_semantics(self) -> None:
        self.assertTrue(rule_value_equals("Avatar", "avatar"))
        self.assertFalse(rule_value_equals("Avatar", "Titanic"))
        self.assertTrue(rule_value_contains("Avatar.2009.MKV", "avatar"))
        self.assertTrue(rule_value_contains(["US", "HK"], "hk"))
        self.assertFalse(rule_value_contains(None, "avatar"))

    def test_rule_bucket_helpers_validate_and_render_shared_variables(self) -> None:
        validate_rule_bucket("Library/{first_char}/{decade}")

        rendered = render_rule_bucket(
            "Library/{first_char}/{decade}",
            {"first_char": "A", "decade": "2000"},
        )

        self.assertEqual(rendered, "Library/A/2000")
        self.assertEqual(render_rule_bucket("Library/{decade}", {"first_char": "A"}), None)
        with self.assertRaises(ConfigurationError):
            validate_rule_bucket("Library/{tmdb_id}")

    def test_organize_rule_matches_categories_and_renders_metadata_variables(self) -> None:
        rule = OrganizeRule(
            id="organize",
            name="Organize",
            fallback_bucket="{decade}",
            categories=[
                RuleCategory(
                    name="animation",
                    bucket="Animation/{first_char}",
                    conditions=[
                        RuleCondition(field="tmdb.genre_ids", op=RuleOperator.CONTAINS, value=16),
                        RuleCondition(field="relative_path", op=RuleOperator.MATCHES, value=r"\.mkv$"),
                    ],
                )
            ],
        )

        result = OrganizeRuleEngine().match(
            rule,
            OrganizeRuleContext(
                relative_path=Path("Ne Zha.mkv"),
                tmdb={"title": "Ne Zha", "release_date": "2019-07-26", "genre_ids": [16, 28]},
            ),
        )

        self.assertEqual(result.bucket, "Animation/N")
        self.assertEqual(result.matched_category, "animation")

        fallback = OrganizeRuleEngine().match(
            rule,
            OrganizeRuleContext(
                relative_path=Path("Drama.mp4"),
                tmdb={"title": "Drama", "release_year": 1999, "genre_ids": [18]},
            ),
        )

        self.assertEqual(fallback.bucket, "1990")
        self.assertIsNone(fallback.matched_category)

    def test_organize_rule_validation_rejects_unsupported_shape(self) -> None:
        engine = OrganizeRuleEngine()

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="bad-field",
                    name="Bad Field",
                    categories=[
                        RuleCategory(
                            name="bad",
                            bucket="Movies",
                            conditions=[RuleCondition(field="tmdb.vote_average", op=RuleOperator.EQUALS, value=8)],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(OrganizeRule(id="bad-bucket", name="Bad Bucket", fallback_bucket="{unknown}"))

        with self.assertRaises(ConfigurationError):
            engine.validate(OrganizeRule(id="escape-bucket", name="Escape Bucket", fallback_bucket="../escape"))

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="empty-category-bucket",
                    name="Empty Category Bucket",
                    categories=[
                        RuleCategory(
                            name="empty-bucket",
                            bucket="",
                            conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="Avatar")],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="empty-category-conditions",
                    name="Empty Category Conditions",
                    categories=[RuleCategory(name="empty-conditions", bucket="Movies", conditions=[])],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="empty-condition-value",
                    name="Empty Condition Value",
                    categories=[
                        RuleCategory(
                            name="empty-value",
                            bucket="Movies",
                            conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value=" ")],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="bad-range-value",
                    name="Bad Range Value",
                    categories=[
                        RuleCategory(
                            name="bad-range",
                            bucket="Movies",
                            conditions=[RuleCondition(field="tmdb.release_year", op=RuleOperator.IN_RANGE, value="")],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="bad-operator",
                    name="Bad Operator",
                    categories=[
                        RuleCategory(
                            name="bad",
                            bucket="Movies",
                            conditions=[RuleCondition(field="tmdb.genre_ids", op=RuleOperator.MATCHES, value="16")],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="bad-relative-path-operator",
                    name="Bad Relative Path Operator",
                    categories=[
                        RuleCategory(
                            name="bad",
                            bucket="Movies",
                            conditions=[
                                RuleCondition(field="relative_path", op=RuleOperator.EQUALS, value="Avatar.mkv")
                            ],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                OrganizeRule(
                    id="bad-release-year-operator",
                    name="Bad Release Year Operator",
                    categories=[
                        RuleCategory(
                            name="bad",
                            bucket="Movies",
                            conditions=[RuleCondition(field="tmdb.release_year", op=RuleOperator.IN, value=[2000, 2009])],
                        )
                    ],
                )
            )

    def test_organize_rule_in_operator_accepts_list_actual_values(self) -> None:
        rule = OrganizeRule(
            id="country",
            name="Country",
            fallback_bucket="Other",
            categories=[
                RuleCategory(
                    name="regional",
                    bucket="Regional",
                    conditions=[
                        RuleCondition(field="tmdb.origin_country", op=RuleOperator.IN, value=["CN", "HK"])
                    ],
                )
            ],
        )

        result = OrganizeRuleEngine().match(
            rule,
            OrganizeRuleContext(tmdb={"origin_country": ["US", "HK"], "title": "Example"}),
        )

        self.assertEqual(result.bucket, "Regional")
        self.assertEqual(result.matched_category, "regional")

    def test_organize_relative_path_string_conditions_are_case_insensitive(self) -> None:
        rule = OrganizeRule(
            id="organize-case",
            name="Organize Case",
            fallback_bucket="Other",
            categories=[
                RuleCategory(
                    name="movie",
                    bucket="Movie",
                    conditions=[
                        RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="avatar"),
                        RuleCondition(field="relative_path", op=RuleOperator.MATCHES, value=r"\.mkv$"),
                    ],
                )
            ],
        )

        result = OrganizeRuleEngine().match(
            rule,
            OrganizeRuleContext(relative_path=Path("Avatar.2009.MKV"), tmdb={"title": "Avatar"}),
        )

        self.assertEqual(result.bucket, "Movie")
        self.assertEqual(result.matched_category, "movie")

    def test_transfer_rule_matches_categories_and_parses_system_folder_variables(self) -> None:
        rule = TransferRule(
            id="transfer",
            name="Transfer",
            fallback_bucket="Library/{decade}",
            categories=[
                RuleCategory(
                    name="recent-avatar",
                    bucket="Recent/{first_char}/{decade}",
                    conditions=[
                        RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="Avatar"),
                        RuleCondition(field="relative_path", op=RuleOperator.MATCHES, value=r"2009"),
                    ],
                )
            ],
        )

        result = TransferRuleEngine().match(
            rule,
            TransferRuleContext(relative_path=Path("Avatar (2009) {tmdb-19995}") / "Avatar (2009).mkv"),
        )

        self.assertEqual(result.bucket, "Recent/A/2000")
        self.assertEqual(result.matched_category, "recent-avatar")
        self.assertEqual(result.variables, {"first_char": "A", "decade": "2000"})

    def test_transfer_rule_parses_variables_from_media_root_after_organize_prefix(self) -> None:
        rule = TransferRule(
            id="transfer",
            name="Transfer",
            fallback_bucket="{decade}/{first_char}",
            categories=[
                RuleCategory(
                    name="regional",
                    bucket="Regional/{decade}/{first_char}",
                    conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="欧美电影")],
                )
            ],
        )

        result = TransferRuleEngine().match(
            rule,
            TransferRuleContext(relative_path=Path("欧美电影/科幻/Inception (2010) {tmdb-27205}/Inception.mkv")),
        )

        self.assertEqual(result.bucket, "Regional/2010/I")
        self.assertEqual(result.matched_category, "regional")
        self.assertEqual(result.variables, {"first_char": "I", "decade": "2010"})

    def test_transfer_relative_path_string_conditions_are_case_insensitive(self) -> None:
        rule = TransferRule(
            id="transfer-case",
            name="Transfer Case",
            fallback_bucket="Other",
            categories=[
                RuleCategory(
                    name="movie",
                    bucket="Movie",
                    conditions=[
                        RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="avatar"),
                    ],
                )
            ],
        )

        result = TransferRuleEngine().match(
            rule,
            TransferRuleContext(relative_path=Path("AVATAR.MKV")),
        )

        self.assertEqual(result.bucket, "Movie")
        self.assertEqual(result.matched_category, "movie")

    def test_transfer_relative_path_conditions_use_media_root_not_filename(self) -> None:
        rule = TransferRule(
            id="transfer-package-path",
            name="Transfer Package Path",
            fallback_bucket="Other",
            categories=[
                RuleCategory(
                    name="file-extension",
                    bucket="File Extension",
                    conditions=[
                        RuleCondition(field="relative_path", op=RuleOperator.MATCHES, value=r"\.mkv$"),
                    ],
                )
            ],
        )

        result = TransferRuleEngine().match(
            rule,
            TransferRuleContext(relative_path=Path("AVATAR.MKV")),
        )

        self.assertEqual(result.bucket, "Other")
        self.assertIsNone(result.matched_category)

    def test_transfer_rule_missing_variables_render_empty_bucket(self) -> None:
        result = TransferRuleEngine().match(
            TransferRule(id="transfer", name="Transfer", fallback_bucket="Library/{decade}"),
            TransferRuleContext(relative_path=Path("Loose.mkv")),
        )

        self.assertEqual(result.bucket, "")
        self.assertEqual(result.variables, {"first_char": "L"})

    def test_transfer_rule_validation_rejects_unsupported_shape(self) -> None:
        engine = TransferRuleEngine()

        with self.assertRaises(ConfigurationError):
            engine.validate(
                TransferRule(
                    id="bad-field",
                    name="Bad Field",
                    categories=[
                        RuleCategory(
                            name="bad",
                            bucket="Movies",
                            conditions=[RuleCondition(field="tmdb.genre_ids", op=RuleOperator.CONTAINS, value=16)],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(TransferRule(id="bad-bucket", name="Bad Bucket", fallback_bucket="{tmdb_id}"))

        with self.assertRaises(ConfigurationError):
            engine.validate(TransferRule(id="escape-bucket", name="Escape Bucket", fallback_bucket="../escape"))

        with self.assertRaises(ConfigurationError):
            engine.validate(TransferRule(id="absolute-bucket", name="Absolute Bucket", fallback_bucket="C:/escape"))

        with self.assertRaises(ConfigurationError):
            engine.validate(
                TransferRule(
                    id="empty-category-bucket",
                    name="Empty Category Bucket",
                    categories=[
                        RuleCategory(
                            name="empty-bucket",
                            bucket="",
                            conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="Avatar")],
                        )
                    ],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                TransferRule(
                    id="empty-category-conditions",
                    name="Empty Category Conditions",
                    categories=[RuleCategory(name="empty-conditions", bucket="Movies", conditions=[])],
                )
            )

        with self.assertRaises(ConfigurationError):
            engine.validate(
                TransferRule(
                    id="empty-condition-value",
                    name="Empty Condition Value",
                    categories=[
                        RuleCategory(
                            name="empty-value",
                            bucket="Movies",
                            conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value=" ")],
                        )
                    ],
                )
            )

        for operator in (RuleOperator.EQUALS, RuleOperator.IN_RANGE):
            with self.assertRaises(ConfigurationError):
                engine.validate(
                    TransferRule(
                        id=f"bad-{operator.value}-operator",
                        name="Bad Operator",
                        categories=[
                            RuleCategory(
                                name="bad",
                                bucket="Movies",
                                conditions=[
                                    RuleCondition(field="relative_path", op=operator, value="Avatar.mkv")
                                ],
                            )
                        ],
                    )
                )


if __name__ == "__main__":
    unittest.main()
