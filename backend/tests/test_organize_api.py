from __future__ import annotations

import unittest
from pathlib import Path

from app.domain.organize import CandidateDecision
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.domain.match import MatchResult, TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.services.identify.candidate import CandidateMatch
from app.services.identify.preview import Preview
from app.services.organize.review import set_plan_item_decision
from app.engines.scan.source import scan_movie_root
from support import RuntimeApiFixture


class OrganizeManualOverrideApiTests(unittest.TestCase):
    def test_manual_tmdb_search_endpoint_returns_ranked_results_without_mutation(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()
            fixture.tmdb.search_pages[("Avatar", 2009, "zh-CN", 1)] = TMDBSearchPage(
                (
                    TMDBCandidate(
                        19995,
                        MediaType.MOVIE,
                        "Avatar",
                        year=2009,
                        metadata={
                            "overview": "A marine on Pandora.",
                            "poster_url": "https://image.tmdb.org/t/p/w154/avatar.jpg",
                            "vote_average": 7.6,
                            "popularity": 88.5,
                            "origin_country": ["US"],
                            "directors": ["James Cameron"],
                            "cast": ["Sam Worthington", "Zoe Saldana", "Sigourney Weaver"],
                        },
                    ),
                ),
                page=1,
                total_pages=1,
                total_results=1,
            )

            response = fixture.client.post(
                f"/api/identify/sessions/{session.id}/search",
                json={"source_candidate_id": source_candidate.id, "query": "Avatar", "year": 2009},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["results"][0]["tmdb_id"], 19995)
            self.assertEqual(body["results"][0]["overview"], "A marine on Pandora.")
            self.assertEqual(body["results"][0]["origin_country"], ["US"])
            self.assertEqual(body["results"][0]["directors"], ["James Cameron"])
            self.assertEqual(body["results"][0]["cast"][:2], ["Sam Worthington", "Zoe Saldana"])
            self.assertEqual(body["results"][0]["confidence"], "high")
            self.assertEqual(body["page"], 1)
            self.assertEqual(fixture.runtime.organize_sessions.get(session.id).candidate_matches[source_candidate.id].metadata["title"], "Old Movie")

    def test_manual_tmdb_search_endpoint_respects_cleared_year_for_explicit_query(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()
            fixture.tmdb.search_pages[("Transformers", None, "zh-CN", 1)] = TMDBSearchPage(
                (
                    TMDBCandidate(
                        1858,
                        MediaType.MOVIE,
                        "Transformers",
                        year=2007,
                    ),
                ),
                page=1,
                total_pages=1,
                total_results=1,
            )

            response = fixture.client.post(
                f"/api/identify/sessions/{session.id}/search",
                json={"source_candidate_id": source_candidate.id, "query": "Transformers", "year": None},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual([item["tmdb_id"] for item in body["results"]], [1858])

    def test_manual_tmdb_search_endpoint_rejects_empty_request_without_context(self) -> None:
        with _ApiFixture() as fixture:
            session, _source_candidate, _plan_item = fixture.movie_session()

            response = fixture.client.post(
                f"/api/identify/sessions/{session.id}/search",
                json={},
            )

            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "identify.search_context_required")

    def test_source_candidate_override_endpoint_returns_updated_session(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()
            fixture.tmdb.details[(MediaType.MOVIE, 2)] = TMDBCandidate(
                2,
                MediaType.MOVIE,
                "Override Movie",
                year=2022,
                metadata={"title": "Override Movie", "release_year": 2022, "tmdb_id": 2},
            )

            response = fixture.client.put(
                f"/api/identify/sessions/{session.id}/candidates/{source_candidate.id}/override",
                json={"tmdb_id": 2},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            plan_item = body["review_candidates"][0]["plan_items"][0]
            match = body["review_candidates"][0]["match"]
            self.assertEqual(match["confidence"], "high")
            self.assertNotIn("match_state", match)
            self.assertTrue(match["acceptance"]["can_accept"])
            self.assertEqual(plan_item["manual_override_tmdb_id"], "2")
            self.assertEqual(plan_item["metadata_source"], "manual_override")
            self.assertEqual(plan_item["confidence"], "high")
            self.assertIn("acceptance", plan_item)
            self.assertNotIn("match_state", plan_item)
            self.assertIn("Override Movie (2022)", plan_item["preview"]["proposed_relative_path"])

    def test_source_candidate_override_endpoint_validates_candidate_and_media_type(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()
            fixture.tmdb.details[(MediaType.MOVIE, 2)] = TMDBCandidate(
                2,
                MediaType.TV,
                "Wrong Show",
                year=2022,
                metadata={"title": "Wrong Show", "release_year": 2022, "tmdb_id": 2},
            )

            missing = fixture.client.put(
                f"/api/identify/sessions/{session.id}/candidates/missing/override",
                json={"tmdb_id": 2},
            )
            wrong_type = fixture.client.put(
                f"/api/identify/sessions/{session.id}/candidates/{source_candidate.id}/override",
                json={"tmdb_id": 2},
            )

            self.assertEqual(missing.status_code, 400)
            self.assertEqual(wrong_type.status_code, 400)
            self.assertIsNone(fixture.runtime.organize_sessions.get(session.id).candidate_matches[source_candidate.id].manual_override_tmdb_id)

    def test_source_file_detail_and_delete_endpoints_use_session_scoped_ids(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, plan_item = fixture.movie_session()

            candidate_detail = fixture.client.get(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/detail",
            )
            self.assertEqual(candidate_detail.status_code, 200)
            candidate_body = candidate_detail.json()
            self.assertEqual(candidate_body["candidate"]["id"], source_candidate.id)
            self.assertEqual(candidate_body["candidate"]["file_count"], 1)
            self.assertIsNotNone(candidate_body["candidate"]["modified_time"])
            self.assertEqual(candidate_body["detail"]["file_type"], "file")
            self.assertIsNotNone(candidate_body["detail"]["created_time"])
            self.assertIsNotNone(candidate_body["detail"]["modified_time"])

            detail = fixture.client.get(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/{plan_item.source_file_id}/detail",
            )
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["classification"], "video")

            missing = fixture.client.get(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/missing/detail",
            )
            self.assertEqual(missing.status_code, 400)

            deleted = fixture.client.delete(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/{plan_item.source_file_id}",
            )

            self.assertEqual(deleted.status_code, 200)
            body = deleted.json()
            self.assertEqual(body["last_source_action_outcome"]["operation"], "delete")
            self.assertEqual(body["last_source_action_outcome"]["source_file_id"], plan_item.source_file_id)
            self.assertEqual(body["review_candidates"][0]["files"][0]["status"], "deleted")
            self.assertEqual(body["review_candidates"][0]["plan_items"], [])

    def test_source_candidate_delete_endpoint_removes_source_unit(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()

            deleted = fixture.client.delete(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}",
            )

            self.assertEqual(deleted.status_code, 200)
            body = deleted.json()
            self.assertEqual(body["review_candidates"][0]["status"], "deleted")
            self.assertEqual(body["review_candidates"][0]["files"][0]["status"], "deleted")
            self.assertEqual(body["review_candidates"][0]["plan_items"], [])

    def test_source_candidate_decision_endpoint_updates_scanned_selection(self) -> None:
        with _ApiFixture() as fixture:
            source_root = fixture.root / "source"
            source_root.mkdir()
            (source_root / "Avatar.2009.mkv").write_text("movie", encoding="utf-8")
            session = fixture.runtime.organize_sessions.create_for_origin(
                Origin(
                    id="manual",
                    name="Manual",
                    path=source_root,
                    media_type=MediaType.MOVIE,
                    trigger=OriginTrigger.MANUAL,
                    policy=OrganizePolicy(target_depot_id="Depot"),
                )
            )
            source_candidate = scan_movie_root(source_root, fixture.runtime.startup_settings.organize.extensions)[0]
            fixture.runtime.organize_sessions.mark_scanned(session.id, [source_candidate])

            response = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/decision",
                json={"decision": "ignore"},
            )

            self.assertEqual(response.status_code, 204)
            self.assertFalse(response.content)
            body = fixture.client.get(f"/api/organize/sessions/{session.id}").json()
            review_candidate = body["review_candidates"][0]
            self.assertEqual(review_candidate["selection_decision"], CandidateDecision.IGNORE.value)
            self.assertEqual(review_candidate["plan_items"], [])

    def test_source_file_rename_endpoint_returns_updated_session(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, plan_item = fixture.movie_session()
            old_file_id = plan_item.source_file_id

            response = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/{old_file_id}/rename",
                json={"new_name": "Avatar.2009.Remux.mkv"},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            review_candidate = body["review_candidates"][0]
            renamed_file = review_candidate["files"][0]
            self.assertEqual(review_candidate["id"], source_candidate.id)
            self.assertEqual(renamed_file["relative_path"], "Avatar.2009.Remux.mkv")
            self.assertNotEqual(renamed_file["id"], old_file_id)
            self.assertEqual(review_candidate["plan_items"][0]["source_file_id"], renamed_file["id"])
            self.assertTrue(review_candidate["plan_items"][0]["source_path"].endswith("Avatar.2009.Remux.mkv"))
            self.assertEqual(body["last_source_action_outcome"]["old_source_file_id"], old_file_id)
            self.assertEqual(body["last_source_action_outcome"]["new_source_file_id"], renamed_file["id"])
            self.assertFalse((fixture.root / "source" / "Avatar.2009.mkv").exists())
            self.assertTrue((fixture.root / "source" / "Avatar.2009.Remux.mkv").exists())

    def test_source_candidate_rename_endpoint_preserves_candidate_id(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, _plan_item = fixture.movie_session()

            response = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/rename",
                json={"new_name": "Avatar.Director.Cut.mkv"},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            review_candidate = body["review_candidates"][0]
            self.assertEqual(review_candidate["id"], source_candidate.id)
            self.assertTrue(review_candidate["source_path"].endswith("Avatar.Director.Cut.mkv"))
            self.assertEqual(review_candidate["files"][0]["relative_path"], "Avatar.Director.Cut.mkv")
            self.assertEqual(body["last_source_action_outcome"]["operation"], "rename")

    def test_scan_restart_endpoint_returns_fresh_scanned_session(self) -> None:
        with _ApiFixture() as fixture:
            session, _source_candidate, plan_item = fixture.movie_session()
            set_plan_item_decision(fixture.runtime.organize_sessions.get(session.id), plan_item.id, "accept")

            response = fixture.client.post(f"/api/organize/sessions/{session.id}/scan")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["state"], "scanned")
            review_candidate = body["review_candidates"][0]
            self.assertIsNone(review_candidate["match"])
            self.assertEqual(review_candidate["plan_items"], [])
            self.assertEqual(review_candidate["files"][0]["planned_item_ids"], [])

    def test_source_rename_endpoints_return_structured_errors(self) -> None:
        with _ApiFixture() as fixture:
            session, source_candidate, plan_item = fixture.movie_session()
            (fixture.root / "source" / "Existing.mkv").write_text("existing", encoding="utf-8")

            missing = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/missing/rename",
                json={"new_name": "New.mkv"},
            )
            invalid = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/{plan_item.source_file_id}/rename",
                json={"new_name": "bad/name.mkv"},
            )

            self.assertEqual(missing.status_code, 400)
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(missing.json()["error"]["code"], "source_file.unknown")
            invalid_error = invalid.json()["error"]
            self.assertEqual(invalid_error["code"], "source_file.rename_blocked")
            self.assertEqual(invalid_error["details"]["status"], "blocked")
            self.assertEqual(invalid_error["details"]["blocked_reason"], "path_separator")

        with _ApiFixture() as fixture:
            session, source_candidate, plan_item = fixture.movie_session()
            (fixture.root / "source" / "Existing.mkv").write_text("existing", encoding="utf-8")
            conflict = fixture.client.put(
                f"/api/organize/sessions/{session.id}/candidates/{source_candidate.id}/files/{plan_item.source_file_id}/rename",
                json={"new_name": "Existing.mkv"},
            )

            self.assertEqual(conflict.status_code, 400)
            conflict_error = conflict.json()["error"]
            self.assertEqual(conflict_error["code"], "source_file.rename_blocked")
            self.assertEqual(conflict_error["details"]["status"], "conflict")
            self.assertEqual(conflict_error["details"]["blocked_reason"], "target_exists")

    def test_openapi_includes_source_review_schemas_and_routes(self) -> None:
        with _ApiFixture() as fixture:
            response = fixture.client.get("/openapi.json")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("/api/identify/sessions/{session_id}/search", body["paths"])
            self.assertIn("/api/organize/sessions/{session_id}/scan", body["paths"])
            self.assertIn(
                "/api/identify/sessions/{session_id}/candidates/{candidate_id}/override",
                body["paths"],
            )
            self.assertIn(
                "/api/organize/sessions/{session_id}/candidates/{candidate_id}/detail",
                body["paths"],
            )
            self.assertIn(
                "/api/organize/sessions/{session_id}/candidates/{candidate_id}/files/{file_id}/detail",
                body["paths"],
            )
            self.assertIn(
                "/api/organize/sessions/{session_id}/candidates/{candidate_id}/rename",
                body["paths"],
            )
            self.assertIn(
                "/api/organize/sessions/{session_id}/candidates/{candidate_id}/files/{file_id}/rename",
                body["paths"],
            )
            schemas = body["components"]["schemas"]
            self.assertIn("IdentifySearchRequest", schemas)
            self.assertIn("SourceCandidate", schemas)
            self.assertIn("SourceCandidateDetail", schemas)
            self.assertIn("SourceFileDetail", schemas)
            self.assertIn("RenameRequest", schemas)
            self.assertIn("SourceActionOutcome", schemas)
            self.assertIn("PlanItem", schemas)
            self.assertIn("source_candidate_id", schemas["IdentifySearchRequest"]["properties"])
            self.assertIn("review_candidates", schemas["OrganizeSession"]["properties"])
            self.assertNotIn("DeleteOutcome", schemas)
            self.assertNotIn("RenameOutcome", schemas)
            self.assertNotIn("last_delete_outcome", schemas["OrganizeSession"]["properties"])
            self.assertNotIn("last_rename_outcome", schemas["OrganizeSession"]["properties"])
            self.assertIn("last_source_action_outcome", schemas["OrganizeSession"]["properties"])
            self.assertNotIn("candidates", schemas["OrganizeSession"]["properties"])
            self.assertEqual(schemas["CandidateDecision"]["enum"], ["accept", "ignore"])
            self.assertIn("selection_decision", schemas["SourceCandidate"]["properties"])
            self.assertIn("confidence", schemas["CandidateMatch"]["properties"])
            self.assertIn("acceptance", schemas["CandidateMatch"]["properties"])
            self.assertNotIn("match_state", schemas["CandidateMatch"]["properties"])
            self.assertIn("confidence", schemas["PlanItem"]["properties"])
            self.assertIn("acceptance", schemas["PlanItem"]["properties"])
            self.assertNotIn("match_state", schemas["PlanItem"]["properties"])
            self.assertFalse(any(name.endswith("Schema") or "Schema-" in name for name in schemas))


class _ApiFixture(RuntimeApiFixture):
    def __enter__(self):
        super().__enter__()
        self.tmdb = _ApiTMDB()
        self.runtime.match.tmdb = self.tmdb
        return self

    def movie_session(self):
        source_root = self.root / "source"
        source_root.mkdir()
        source = source_root / "Avatar.2009.mkv"
        source.write_text("movie", encoding="utf-8")
        session = self.runtime.organize_sessions.create_for_origin(
            Origin(
                id="manual",
                name="Manual",
                path=source_root,
                media_type=MediaType.MOVIE,
                trigger=OriginTrigger.MANUAL,
                policy=OrganizePolicy(target_depot_id="Depot"),
            )
        )
        source_candidate = scan_movie_root(source_root, self.runtime.startup_settings.organize.extensions)[0]
        match = MatchResult(
            candidate_id=source_candidate.id,
            media_type=MediaType.MOVIE,
            confidence=ConfidenceLevel.HIGH,
            title="Old Movie",
            year=2000,
            tmdb_id=1,
            metadata={"title": "Old Movie", "release_year": 2000, "tmdb_id": 1},
        )
        plan_items = Preview.for_candidate(
            media_candidate=source_candidate,
            source_root=source_root,
            match_result=match,
            policy=OrganizePolicy(target_depot_id="Depot"),
            extensions=self.runtime.startup_settings.organize.extensions,
        )
        self.runtime.organize_sessions.mark_scanned(session.id, [source_candidate])
        self.runtime.organize_sessions.start_identify(session.id)
        self.runtime.organize_sessions.mark_identified(
            session.id,
            candidate_matches={
                source_candidate.id: CandidateMatch(
                    source_candidate_id=source_candidate.id,
                    confidence=ConfidenceLevel.HIGH,
                    metadata={"title": "Old Movie", "release_year": 2000, "tmdb_id": 1},
                    metadata_source="auto",
                )
            },
            plan_items=plan_items,
        )
        return session, source_candidate, plan_items[0]


class _ApiTMDB:
    def __init__(self):
        self.details = {}
        self.external = {}
        self.search_pages = {}

    def get_by_id(self, media_type, tmdb_id):
        return self.details.get((media_type, int(tmdb_id)))

    def find_by_external_id(self, imdb_id, media_type):
        return self.external.get((imdb_id, media_type))

    def search_page(self, media_type, title, year, language, page):
        value = self.search_pages.get(
            (title, year, language, page),
            TMDBSearchPage(page=page),
        )
        if isinstance(value, TMDBSearchPage):
            return TMDBSearchPage(
                tuple(self._search_result(item, language) for item in value.results),
                page=value.page,
                total_pages=value.total_pages,
                total_results=value.total_results,
            )
        return value

    def load_candidate_details(self, media_type, tmdb_id, language, fallback_search_result):
        return (
            self.details.get((media_type, int(tmdb_id), language))
            or self.details.get((media_type, int(tmdb_id)))
            or fallback_search_result.to_candidate()
        )

    def _search_result(self, item, language):
        if isinstance(item, TMDBSearchResult):
            return item
        if isinstance(item, TMDBCandidate):
            self.details.setdefault((item.media_type, item.tmdb_id, language), item)
            return TMDBSearchResult(
                item.tmdb_id,
                item.media_type,
                item.title,
                original_title=item.original_title,
                year=item.year,
                metadata=dict(item.metadata),
            )
        return item


if __name__ == "__main__":
    unittest.main()
