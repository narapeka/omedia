from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.transfer import TransferStatus
from app.domain.match import MatchEvidence, MatchResult
from app.domain.transfer import TransferJob
from support import RuntimeApiFixture


class ConfigApiTests(unittest.TestCase):
    def test_config_api_crud_scans_organize_transfer_activity_rules_and_cache(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            watch_settings_path = root / "watch"
            watch_settings_path.mkdir()
            self.assertEqual(client.put("/api/watch/settings", json={"path": str(watch_settings_path), "enabled": False}).status_code, 200)
            self.assertEqual(client.get("/api/watch/settings").json()["path"], str(watch_settings_path))
            self.assertEqual(client.get("/api/watch/status").json()["state"], "stopped")
            self.assertEqual(client.post("/api/watch/start").status_code, 200)
            self.assertEqual(client.get("/api/watch/status").json()["state"], "running")
            self.assertEqual(client.post("/api/watch/restart").status_code, 200)
            self.assertEqual(client.post("/api/watch/stop").status_code, 200)
            self.assertFalse(client.get("/api/watch/settings").json()["enabled"])

            depot_path = root / "Depot"
            library_path = root / "library"
            depot_payload = {
                "id": "Depot",
                "name": "Movie staging",
                "path": str(depot_path),
                "media_type": "movie",
                "enabled": True,
                "policy": {"target_library_path": str(library_path), "trigger": "manual"},
            }
            self.assertEqual(client.put("/api/depots/Depot", json=depot_payload).status_code, 200)
            self.assertEqual(client.get("/api/depots/Depot").json()["name"], "Movie staging")

            origin_path = root / "origin"
            origin_path.mkdir()
            (origin_path / "Movie.mkv").write_text("x", encoding="utf-8")
            origin_payload = {
                "id": "manual",
                "name": "Manual movies",
                "path": str(origin_path),
                "media_type": "movie",
                "trigger": "manual",
                "enabled": True,
                "policy": {"target_depot_id": "Depot"},
            }
            self.assertEqual(client.put("/api/origins/manual", json=origin_payload).status_code, 200)
            origin_summary = client.get("/api/origins").json()[0]
            self.assertEqual(origin_summary["name"], "Manual movies")
            self.assertEqual(origin_summary["candidate_count"], 0)

            depot_path.mkdir()
            (depot_path / "Ready.mkv").write_text("ready", encoding="utf-8")
            self.assertEqual(client.get("/api/depots/Depot").json()["pending_count"], 1)

            rule_payload = {"id": "fallback", "name": "Fallback", "categories": [], "fallback_bucket": ""}
            self.assertEqual(client.put("/api/rules/transfer/fallback", json=rule_payload).status_code, 200)
            self.assertEqual(client.get("/api/rules/transfer").json()[0]["id"], "fallback")

            session = client.post("/api/organize/sessions", json={"origin_id": "manual"}).json()
            self.assertEqual(session["state"], "scanned")
            self.assertEqual(session["review_candidates"][0]["file_count"], 1)
            self.assertEqual(session["review_candidates"][0]["plan_items"], [])
            object.__setattr__(runtime, "match", FakeMatch())
            runtime.organize_pipeline.update_matcher(runtime.match)
            identified = client.post(f"/api/identify/sessions/{session['id']}").json()
            self.assertEqual(identified["state"], "identified")
            plan_item = identified["review_candidates"][0]["plan_items"][0]
            self.assertEqual(plan_item["evidence"]["summary"][0]["source"], "fake")
            decision = client.put(
                f"/api/organize/sessions/{session['id']}/plan-items/{plan_item['id']}/decision",
                json={"decision": "accept"},
            )
            self.assertEqual(decision.status_code, 204)
            refreshed = client.get(f"/api/organize/sessions/{session['id']}")
            self.assertEqual(refreshed.status_code, 200)
            self.assertEqual(
                refreshed.json()["review_candidates"][0]["plan_items"][0]["user_decision"],
                "accept",
            )
            organized = client.post(f"/api/organize/sessions/{session['id']}/execute")
            self.assertEqual(organized.status_code, 200)
            self.assertEqual(organized.json()["moved"], 1)

            transfer = client.post("/api/transfer/jobs", json={"depot_id": "Depot", "requested_by": "manual"})
            self.assertEqual(transfer.status_code, 200)
            self.assertEqual(transfer.json()["status"], "queued")
            result = runtime.transfer_service.run_queued_once()
            self.assertIsNotNone(result)
            self.assertEqual(result.job.status.value, "succeeded")
            (depot_path / "Cancel.mkv").write_text("cancel", encoding="utf-8")
            queued = client.post("/api/transfer/jobs", json={"depot_id": "Depot", "requested_by": "manual-cancel"}).json()
            self.assertEqual(queued["status"], "queued")
            self.assertEqual(client.post(f"/api/transfer/jobs/{queued['id']}/cancel").json()["status"], "cancelled")
            self.assertIsNone(runtime.transfer_service.run_queued_once())
            cancelled_jobs = client.get("/api/transfer/jobs", params={"requested_by": "manual-cancel", "status": "cancelled"}).json()
            self.assertEqual([job["id"] for job in cancelled_jobs], [queued["id"]])
            self.assertGreaterEqual(len(client.get("/api/transfer/jobs", params={"q": "Movie staging", "limit": 1}).json()), 1)
            self.assertGreaterEqual(len(client.get("/api/activity/events").json()), 1)

            self.assertTrue(client.get("/api/settings/health").json()["ok"])

    def test_organize_session_slot_conflict_returns_409(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            origin_path = root / "origin"
            origin_path.mkdir()
            depot_payload = {
                "id": "Depot",
                "name": "Movie staging",
                "path": str(depot_path),
                "media_type": "movie",
                "enabled": True,
                "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
            }
            origin_payload = {
                "id": "manual",
                "name": "Manual movies",
                "path": str(origin_path),
                "media_type": "movie",
                "trigger": "manual",
                "enabled": True,
                "policy": {"target_depot_id": "Depot"},
            }
            self.assertEqual(client.put("/api/depots/Depot", json=depot_payload).status_code, 200)
            self.assertEqual(client.put("/api/origins/manual", json=origin_payload).status_code, 200)
            self.assertEqual(client.post("/api/organize/sessions", json={"origin_id": "manual"}).status_code, 200)

            conflict = client.post("/api/organize/sessions", json={"origin_id": "manual"})

            self.assertEqual(conflict.status_code, 409)
            error = conflict.json()["error"]
            self.assertEqual(error["code"], "origin.manual_active_session")
            self.assertEqual(error["details"]["origin_id"], "manual")

    def test_bulk_organize_session_create_scans_multiple_manual_origins(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            first = self._save_origin(client, root, "manual-a", depot_path=depot_path)
            second = self._save_origin(client, root, "manual-b", depot_path=depot_path)
            (first / "First.mkv").write_text("first", encoding="utf-8")
            (second / "Second.mkv").write_text("second", encoding="utf-8")

            response = client.post("/api/organize/sessions/bulk", json={"origin_ids": ["manual-a", "manual-b"]})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual([item["status"] for item in body["results"]], ["created", "created"])
            self.assertEqual({item["origin_id"] for item in body["results"]}, {"manual-a", "manual-b"})
            self.assertEqual(len(body["sessions"]), 2)
            self.assertEqual({session["kind"] for session in body["sessions"]}, {"origin"})
            self.assertEqual({session["state"] for session in body["sessions"]}, {"scanned"})
            self.assertEqual([len(session["review_candidates"]) for session in body["sessions"]], [1, 1])
            self.assertEqual(len(client.get("/api/organize/sessions").json()), 2)

    def test_bulk_organize_session_create_returns_partial_failures(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            ready = self._save_origin(client, root, "ready", depot_path=depot_path)
            busy = self._save_origin(client, root, "busy", depot_path=depot_path)
            disabled = self._save_origin(client, root, "disabled", depot_path=depot_path, enabled=False)
            (ready / "Ready.mkv").write_text("ready", encoding="utf-8")
            (busy / "Busy.mkv").write_text("busy", encoding="utf-8")
            (disabled / "Disabled.mkv").write_text("disabled", encoding="utf-8")
            self.assertEqual(client.post("/api/organize/sessions", json={"origin_id": "busy"}).status_code, 200)

            response = client.post(
                "/api/organize/sessions/bulk",
                json={"origin_ids": ["ready", "busy", "missing", "disabled", "ready"]},
            )

            self.assertEqual(response.status_code, 200)
            by_origin = {item["origin_id"]: item for item in response.json()["results"]}
            self.assertEqual(by_origin["ready"]["status"], "duplicate")
            self.assertEqual(response.json()["results"][0]["status"], "created")
            self.assertEqual(by_origin["busy"]["status"], "conflict")
            self.assertEqual(by_origin["missing"]["status"], "missing")
            self.assertEqual(by_origin["disabled"]["status"], "disabled")
            self.assertEqual(len(response.json()["sessions"]), 1)
            self.assertEqual(len(client.get("/api/organize/sessions").json()), 2)

    def test_bulk_organize_session_create_rejects_watch_origin_without_blocking_manual_origin(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            watch_settings_path = root / "watch"
            watch_settings_path.mkdir()
            depot_path = root / "Depot"
            self.assertEqual(client.put("/api/watch/settings", json={"path": str(watch_settings_path), "enabled": True}).status_code, 200)
            self._save_depot(client, root, depot_path=depot_path)
            manual = self._save_origin(client, root, "manual", depot_path=depot_path)
            auto = watch_settings_path / "auto"
            self.assertEqual(
                client.put(
                    "/api/origins/auto",
                    json={
                        "id": "auto",
                        "name": "Auto Watch",
                        "path": str(auto),
                        "media_type": "movie",
                        "trigger": "watch",
                        "enabled": True,
                        "policy": {"target_depot_id": "Depot"},
                    },
                ).status_code,
                200,
            )
            (manual / "Manual.mkv").write_text("manual", encoding="utf-8")

            response = client.post("/api/organize/sessions/bulk", json={"origin_ids": ["auto", "manual"]})

            self.assertEqual(response.status_code, 200)
            results = {item["origin_id"]: item for item in response.json()["results"]}
            self.assertEqual(results["auto"]["status"], "watch_origin")
            self.assertEqual(results["manual"]["status"], "created")
            self.assertEqual(len(response.json()["sessions"]), 1)
            self.assertEqual(response.json()["sessions"][0]["state"], "scanned")

    def test_single_organize_session_endpoint_still_supports_manual_origin_and_ad_hoc_requests(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            origin_path = self._save_origin(client, root, "manual", depot_path=depot_path)
            ad_hoc = root / "ad-hoc"
            ad_hoc.mkdir()
            (origin_path / "Manual.mkv").write_text("manual", encoding="utf-8")
            (ad_hoc / "Loose.mkv").write_text("loose", encoding="utf-8")

            manual = client.post("/api/organize/sessions", json={"origin_id": "manual"})
            ad_hoc_response = client.post(
                "/api/organize/sessions",
                json={
                    "source_path": str(ad_hoc),
                    "media_type": "movie",
                    "policy": {"target_depot_id": "Depot"},
                },
            )

            self.assertEqual(manual.status_code, 200)
            self.assertEqual(manual.json()["kind"], "origin")
            self.assertEqual(manual.json()["state"], "scanned")
            self.assertEqual(ad_hoc_response.status_code, 200)
            self.assertEqual(ad_hoc_response.json()["kind"], "ad_hoc")
            self.assertEqual(ad_hoc_response.json()["state"], "scanned")

    def test_transfer_job_errors_are_structured_and_atomic(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_payload = {
                "id": "Depot",
                "name": "Movie staging",
                "path": str(root / "Depot"),
                "media_type": "movie",
                "enabled": True,
                "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
            }
            self.assertEqual(client.put("/api/depots/Depot", json=depot_payload).status_code, 200)

            first = client.post(
                "/api/transfer/jobs",
                json={"depot_id": "Depot", "requested_by": "web-ui-transfer"},
            )
            self.assertEqual(first.status_code, 200)
            busy = client.post(
                "/api/transfer/jobs",
                json={"depot_id": "Depot", "requested_by": "web-ui-transfer"},
            )

            self.assertEqual(busy.status_code, 409)
            error = busy.json()["error"]
            self.assertEqual(error["code"], "depot.active_transfer")
            self.assertEqual(error["details"]["transfer_error_code"], "depot_transfer_busy")
            self.assertEqual(error["details"]["depot_id"], "Depot")
            self.assertEqual(len(client.get("/api/transfer/jobs").json()), 1)
            unknown = client.post("/api/transfer/jobs/missing/cancel")
            self.assertEqual(unknown.status_code, 400)
            error = unknown.json()["error"]
            self.assertEqual(error["code"], "transfer_job.unknown")
            self.assertEqual(error["details"]["job_id"], "missing")

    def test_scheduled_depot_rejects_invalid_cron_schedule(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            response = client.put(
                "/api/depots/scheduled",
                json={
                    "id": "scheduled",
                    "name": "Scheduled staging",
                    "path": str(root / "Depot"),
                    "media_type": "movie",
                    "enabled": True,
                    "policy": {
                        "target_library_path": str(root / "library"),
                        "trigger": "scheduled",
                        "schedule": "*/0 * * * *",
                    },
                },
            )

            self.assertEqual(response.status_code, 400)
            error = response.json()["error"]
            self.assertEqual(error["code"], "transfer_schedule.invalid")
            self.assertEqual(error["details"]["field"], "minute")
            self.assertEqual(runtime.configuration.list_depots(), [])

    def test_depot_detail_candidates_and_candidate_file_operations(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            folder = depot_path / "Avatar"
            folder.mkdir(parents=True)
            (folder / "Avatar.mkv").write_text("video", encoding="utf-8")
            (folder / "Avatar.nfo").write_text("metadata", encoding="utf-8")
            (depot_path / "Loose.mkv").write_text("loose", encoding="utf-8")
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )

            detail = client.get("/api/depots/Depot").json()
            self.assertNotIn("files", detail)
            by_name = {candidate["display_name"]: candidate for candidate in detail["candidates"]}
            self.assertEqual(by_name["Avatar"]["kind"], "folder")
            self.assertEqual(by_name["Loose.mkv"]["kind"], "file")

            unknown = client.get("/api/depots/Depot/candidates/not-real/detail")
            self.assertEqual(unknown.status_code, 400)

            loose_id = by_name["Loose.mkv"]["id"]
            detail_response = client.get(f"/api/depots/Depot/candidates/{loose_id}/detail")
            self.assertEqual(detail_response.status_code, 200)
            self.assertEqual(detail_response.json()["detail"]["file_type"], "file")

            conflict = client.put(
                f"/api/depots/Depot/candidates/{loose_id}/rename",
                json={"new_name": "Avatar"},
            )
            self.assertEqual(conflict.status_code, 200)
            self.assertEqual(conflict.json()["outcome"]["status"], "conflict")

            renamed = client.put(
                f"/api/depots/Depot/candidates/{loose_id}/rename",
                json={"new_name": "Loose.Renamed.mkv"},
            )
            self.assertEqual(renamed.status_code, 200)
            body = renamed.json()
            self.assertNotEqual(body["outcome"]["old_candidate_id"], body["outcome"]["new_candidate_id"])
            self.assertNotIn("depot", body)
            refreshed = client.get("/api/depots/Depot").json()
            self.assertIn("Loose.Renamed.mkv", {candidate["display_name"] for candidate in refreshed["candidates"]})

            folder_candidate = next(candidate for candidate in refreshed["candidates"] if candidate["display_name"] == "Avatar")
            nfo_file = next(file for file in folder_candidate["files"] if file["display_name"] == "Avatar.nfo")
            deleted = client.delete(f"/api/depots/Depot/candidates/{folder_candidate['id']}/files/{nfo_file['id']}")
            self.assertEqual(deleted.status_code, 200)
            deleted_body = deleted.json()
            self.assertNotIn("depot", deleted_body)
            refreshed_after_delete = client.get("/api/depots/Depot").json()
            refreshed_folder = next(candidate for candidate in refreshed_after_delete["candidates"] if candidate["display_name"] == "Avatar")
            self.assertEqual({file["display_name"] for file in refreshed_folder["files"]}, {"Avatar.mkv"})

            return_response = client.post(
                "/api/depots/Depot/return",
                json={"candidate_ids": [refreshed_folder["id"]], "relative_paths": [], "destination_root": str(root / "return")},
            )
            self.assertEqual(return_response.status_code, 200)
            return_body = return_response.json()
            self.assertNotIn("depot", return_body)
            self.assertEqual(len(return_body["activity_events"]), 1)
            refreshed_after_return = client.get("/api/depots/Depot").json()
            self.assertNotIn("Avatar", {candidate["display_name"] for candidate in refreshed_after_return["candidates"]})

    def test_depot_detail_serializes_grouped_candidate(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            media = depot_path / "测试前缀" / "Avatar (2009) {tmdb-19995}"
            media.mkdir(parents=True)
            (media / "Avatar.mkv").write_text("video", encoding="utf-8")
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )

            response = client.get("/api/depots/Depot")

            self.assertEqual(response.status_code, 200)
            candidate = response.json()["candidates"][0]
            self.assertEqual(candidate["display_name"], "Avatar (2009) {tmdb-19995}")
            self.assertEqual(candidate["group"]["organize_prefix"], "测试前缀")
            self.assertEqual(candidate["group"]["display_name"], "测试前缀")
            self.assertEqual(candidate["media_relative_path"], "Avatar (2009) {tmdb-19995}")

    def test_depot_candidate_mutation_rejects_active_transfer(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            depot_path.mkdir()
            (depot_path / "Ready.mkv").write_text("ready", encoding="utf-8")
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )
            candidate_id = client.get("/api/depots/Depot").json()["candidates"][0]["id"]
            runtime.store.save_transfer_job(TransferJob(id="queued", depot_id="Depot", status=TransferStatus.QUEUED))

            response = client.delete(f"/api/depots/Depot/candidates/{candidate_id}")

            self.assertEqual(response.status_code, 409)
            error = response.json()["error"]
            self.assertEqual(error["code"], "depot.active_transfer")
            self.assertEqual(error["details"]["transfer_error_code"], "depot_transfer_busy")
            self.assertEqual(error["details"]["depot_id"], "Depot")
            self.assertTrue((depot_path / "Ready.mkv").exists())

    def test_watch_origin_save_creates_direct_child_folder(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            watch_settings_path = root / "watch"
            watch_settings_path.mkdir()
            depot_path = root / "Depot"
            child_path = watch_settings_path / "auto"
            self.assertEqual(client.put("/api/watch/settings", json={"path": str(watch_settings_path), "enabled": True}).status_code, 200)
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )

            response = client.put(
                "/api/origins/auto",
                json={
                    "id": "auto",
                    "name": "Auto Watch",
                    "path": str(child_path),
                    "media_type": "movie",
                    "trigger": "watch",
                    "enabled": True,
                    "policy": {"target_depot_id": "Depot"},
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(child_path.is_dir())
            self.assertEqual(client.get("/api/watch/children").json()[0]["status"], "configured")

    def test_watch_root_change_stops_worker_and_deletes_configured_watch_origins(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            watch_settings_path = root / "watch"
            new_watch_settings_path = root / "new-watch"
            child_path = watch_settings_path / "auto"
            child_path.mkdir(parents=True)
            new_watch_settings_path.mkdir()
            (child_path / "Movie.mkv").write_text("x", encoding="utf-8")
            depot_path = root / "Depot"
            self.assertEqual(client.put("/api/watch/settings", json={"path": str(watch_settings_path), "enabled": True}).status_code, 200)
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                client.put(
                    "/api/origins/auto",
                    json={
                        "id": "auto",
                        "name": "Auto Watch",
                        "path": str(child_path),
                        "media_type": "movie",
                        "trigger": "watch",
                        "enabled": True,
                        "policy": {"target_depot_id": "Depot"},
                    },
                ).status_code,
                200,
            )
            old_worker = runtime.watch_automation.worker
            self.assertIsNotNone(old_worker)
            self.assertGreater(len(old_worker._pending), 0)

            response = client.put("/api/watch/settings", json={"path": str(new_watch_settings_path), "enabled": True})

            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["enabled"])
            self.assertEqual(client.get("/api/watch/status").json()["state"], "stopped")
            self.assertEqual(client.get("/api/origins").json(), [])
            self.assertEqual(old_worker._pending, {})
            self.assertIsNone(runtime.watch_automation.worker)
            self.assertEqual(client.get("/api/watch/children").json(), [])

    def test_delete_rejects_referenced_depot_and_rules(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            origin_path = root / "origin"
            origin_path.mkdir()
            organize_rule = {"id": "organize-rule", "name": "Organize", "categories": [], "fallback_bucket": ""}
            transfer_rule = {"id": "transfer-rule", "name": "Transfer", "categories": [], "fallback_bucket": ""}
            self.assertEqual(client.put("/api/rules/organize/organize-rule", json=organize_rule).status_code, 200)
            self.assertEqual(client.put("/api/rules/transfer/transfer-rule", json=transfer_rule).status_code, 200)
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "id": "Depot",
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "policy": {
                            "target_library_path": str(root / "library"),
                            "trigger": "manual",
                            "transfer_rule_id": "transfer-rule",
                        },
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                client.put(
                    "/api/origins/origin",
                    json={
                        "id": "origin",
                        "name": "Origin",
                        "path": str(origin_path),
                        "media_type": "movie",
                        "trigger": "manual",
                        "enabled": True,
                        "policy": {
                            "target_depot_id": "Depot",
                            "organize_rule_id": "organize-rule",
                        },
                    },
                ).status_code,
                200,
            )

            depot_delete = client.delete("/api/depots/Depot")
            organize_delete = client.delete("/api/rules/organize/organize-rule")
            transfer_delete = client.delete("/api/rules/transfer/transfer-rule")

            self.assertEqual(depot_delete.status_code, 400)
            error = depot_delete.json()["error"]
            self.assertEqual(error["code"], "depot.used_by_origin")
            self.assertEqual(error["details"]["depot_id"], "Depot")
            self.assertEqual(error["details"]["count"], 1)
            self.assertEqual(organize_delete.status_code, 400)
            error = organize_delete.json()["error"]
            self.assertEqual(error["code"], "rule.used")
            self.assertEqual(error["details"]["rule_kind"], "organize")
            self.assertEqual(error["details"]["object"], "Origin")
            self.assertEqual(transfer_delete.status_code, 400)
            error = transfer_delete.json()["error"]
            self.assertEqual(error["code"], "rule.used")
            self.assertEqual(error["details"]["rule_kind"], "transfer")
            self.assertEqual(error["details"]["object"], "Depot")

    def test_delete_origin_rejects_active_organize_session(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            self._save_origin(client, root, "manual", depot_path=depot_path)
            self.assertEqual(client.post("/api/organize/sessions", json={"origin_id": "manual"}).status_code, 200)

            response = client.delete("/api/origins/manual")

            self.assertEqual(response.status_code, 400)
            error = response.json()["error"]
            self.assertEqual(error["code"], "origin.active_session")
            self.assertEqual(error["details"]["origin_id"], "manual")
            self.assertEqual(len(error["details"]["session_ids"]), 1)
            self.assertEqual(client.get("/api/origins/manual").status_code, 200)

    def test_delete_depot_rejects_active_organize_session(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            source_path = root / "ad-hoc"
            source_path.mkdir()
            self._save_depot(client, root, depot_path=depot_path)
            response = client.post(
                "/api/organize/sessions",
                json={
                    "source_path": str(source_path),
                    "media_type": "movie",
                    "policy": {"target_depot_id": "Depot"},
                },
            )
            self.assertEqual(response.status_code, 200)

            response = client.delete("/api/depots/Depot")

            self.assertEqual(response.status_code, 400)
            error = response.json()["error"]
            self.assertEqual(error["code"], "depot.active_session")
            self.assertEqual(error["details"]["depot_id"], "Depot")
            self.assertEqual(len(error["details"]["session_ids"]), 1)
            self.assertEqual(client.get("/api/depots/Depot").status_code, 200)

    def test_delete_depot_rejects_active_transfer_job(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            transfer = client.post("/api/transfer/jobs", json={"depot_id": "Depot", "requested_by": "manual"})
            self.assertEqual(transfer.status_code, 200)

            response = client.delete("/api/depots/Depot")

            self.assertEqual(response.status_code, 400)
            error = response.json()["error"]
            self.assertEqual(error["code"], "depot.active_transfer")
            self.assertEqual(error["details"]["depot_id"], "Depot")
            self.assertEqual(error["details"]["transfer_job_id"], transfer.json()["id"])
            self.assertEqual(client.get("/api/depots/Depot").status_code, 200)

    def test_delete_depot_allows_completed_transfer_history(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            depot_path = root / "Depot"
            self._save_depot(client, root, depot_path=depot_path)
            runtime.store.save_transfer_job(TransferJob(id="history", depot_id="Depot", status=TransferStatus.SUCCEEDED))

            response = client.delete("/api/depots/Depot")

            self.assertEqual(response.status_code, 204)
            self.assertEqual(client.get("/api/transfer/jobs", params={"depot_id": "Depot"}).json()[0]["id"], "history")

    def test_configuration_list_endpoints_do_not_scan_configured_paths(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            self._save_depot(client, root, depot_path=root / "Depot")
            self._save_origin(client, root, "manual", depot_path=root / "Depot")
            object.__setattr__(runtime, "inventory", ExplodingInventory())

            origins = client.get("/api/origins")
            depots = client.get("/api/depots")

            self.assertEqual(origins.status_code, 200)
            self.assertEqual(depots.status_code, 200)
            self.assertEqual(origins.json()[0]["candidate_count"], 0)
            self.assertEqual(origins.json()[0]["file_count"], 0)
            self.assertEqual(origins.json()[0]["unknown_count"], 0)
            self.assertEqual(depots.json()[0]["pending_count"], 0)

    def _app(self):
        return RuntimeApiFixture(
            common={
                "organize": {
                    "extensions": {
                        "video": [".mkv"],
                        "subtitle": [".srt", ".sup"],
                        "sidecar": [".nfo", ".jpg"],
                    },
                    "min_non_subtitle_file_size_mb": 0,
                },
                "tmdb": {"api_key": ""},
                "llm": {"api_key": ""},
            }
        )

    def _save_depot(self, client: TestClient, root: Path, *, depot_path: Path) -> None:
        self.assertEqual(
            client.put(
                "/api/depots/Depot",
                json={
                    "id": "Depot",
                    "name": "Movie staging",
                    "path": str(depot_path),
                    "media_type": "movie",
                    "enabled": True,
                    "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                },
            ).status_code,
            200,
        )

    def _save_origin(
        self,
        client: TestClient,
        root: Path,
        origin_id: str,
        *,
        depot_path: Path,
        enabled: bool = True,
    ) -> Path:
        origin_path = root / origin_id
        origin_path.mkdir()
        self.assertEqual(
            client.put(
                f"/api/origins/{origin_id}",
                json={
                    "id": origin_id,
                    "name": origin_id,
                    "path": str(origin_path),
                    "media_type": "movie",
                    "trigger": "manual",
                    "enabled": enabled,
                    "policy": {"target_depot_id": "Depot"},
                },
            ).status_code,
            200,
        )
        return origin_path


class FakeMatch:
    def match_batch(self, candidates):
        return {
            candidate.id: MatchResult(
                candidate_id=candidate.id,
                media_type=MediaType.MOVIE,
                confidence=ConfidenceLevel.HIGH,
                title="Movie",
                year=2020,
                tmdb_id=1,
                evidence=[
                    MatchEvidence(
                        source="fake",
                        confidence=ConfidenceLevel.HIGH,
                        values={"title": "Movie"},
                        reason="test match",
                    )
                ],
            )
            for candidate in candidates
        }


class ExplodingInventory:
    def origin_summary(self, *_args, **_kwargs):
        raise AssertionError("configuration list endpoints must not scan origin paths")

    def depot_summary(self, *_args, **_kwargs):
        raise AssertionError("configuration list endpoints must not scan depot paths")

    def depot_detail(self, *_args, **_kwargs):
        raise AssertionError("configuration list endpoints must not scan depot detail")


if __name__ == "__main__":
    unittest.main()
