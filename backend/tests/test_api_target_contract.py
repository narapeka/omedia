from __future__ import annotations

import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.api.http.present.activity import present_activity_event
from app.api.http.present.transfer import present_transfer_job
from app.api.http.schemas import depot as depot_schemas
from app.api.http.schemas import organize as organize_schemas
from app.api.http.schemas import transfer as transfer_schemas
from app.main import create_app
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityStatus
from app.domain import depot as domain_depot
from app.domain import organize as domain_organize
from app.domain import transfer as domain_transfer
from support import RuntimeApiFixture


APP_ROOT = Path(__file__).parents[1] / "app"


class TargetApiContractTests(unittest.TestCase):
    def test_api_schemas_reuse_domain_enums_for_shared_business_concepts(self) -> None:
        self.assertIs(depot_schemas.ResolveMode, domain_depot.ResolveMode)
        self.assertIs(depot_schemas.DepotCandidateActionStatus, domain_depot.DepotCandidateActionStatus)
        self.assertIs(organize_schemas.ConflictReviewAction, domain_organize.ConflictReviewAction)
        self.assertIs(organize_schemas.ConflictReviewStatus, domain_organize.ConflictReviewStatus)
        self.assertIs(transfer_schemas.TransferTrigger, domain_transfer.TransferTrigger)

    def test_conflict_review_action_request_model_stores_router_payload_value_as_string(self) -> None:
        action_payload = organize_schemas.ConflictReviewActionRequest(
            identity_key="identity-1",
            source_candidate_id="candidate-1",
            action=domain_organize.ConflictReviewAction.KEEP.value,
        )

        self.assertIs(type(action_payload.action), str)

    def test_api_schemas_reuse_domain_enums_for_source_review_projection(self) -> None:
        self.assertIs(organize_schemas.BulkSessionItemStatus, domain_organize.BulkSessionItemStatus)
        self.assertIs(organize_schemas.SourceCandidateKind, domain_organize.SourceCandidateKind)
        self.assertIs(organize_schemas.SourceFileClassification, domain_organize.SourceFileClassification)
        self.assertIs(organize_schemas.SourceCandidateStatus, domain_organize.SourceCandidateStatus)
        self.assertIs(organize_schemas.SourceFileStatus, domain_organize.SourceFileStatus)
        self.assertIs(organize_schemas.SourceFilePlanStatus, domain_organize.SourceFilePlanStatus)
        self.assertIs(organize_schemas.SourceActionOperation, domain_organize.SourceActionOperation)
        self.assertIs(organize_schemas.SourceActionStatus, domain_organize.SourceActionStatus)

    def test_api_schemas_do_not_import_service_modules(self) -> None:
        schemas_dir = Path(__file__).parents[1] / "app" / "api" / "http" / "schemas"
        offenders = [
            path.relative_to(schemas_dir).as_posix()
            for path in schemas_dir.rglob("*.py")
            if "app.services" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_static_architecture_import_guard(self) -> None:
        rules = [
            ("api/http/schemas", ("app.services",)),
            ("domain", ("app.api", "app.services", "app.infra", "app.engines", "app.boot")),
            ("core", ("app.api", "app.services", "app.infra", "app.engines", "app.boot")),
            ("engines", ("app.api", "app.services", "app.infra", "app.boot")),
            ("infra", ("app.api", "app.services")),
            ("services", ("app.api.http.schemas", "app.api.http.present")),
        ]
        offenders: list[str] = []
        for relative_dir, forbidden_prefixes in rules:
            for path in (APP_ROOT / relative_dir).rglob("*.py"):
                for imported, line in _imports(path):
                    if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden_prefixes):
                        offenders.append(f"{path.relative_to(APP_ROOT).as_posix()}:{line}: {imported}")
        self.assertEqual(offenders, [])

    def test_transfer_job_presenter_does_not_depend_on_object_dict(self) -> None:
        job = _TransferJobLike()

        presented = present_transfer_job(job)

        self.assertEqual(presented.id, "transfer-1")
        self.assertEqual(presented.status, domain_transfer.TransferStatus.QUEUED)
        self.assertEqual(presented.metadata, {"candidate_ids": ["a"]})

    def test_activity_event_presenter_does_not_depend_on_object_dict(self) -> None:
        event = _ActivityEventLike()

        presented = present_activity_event(event)

        self.assertEqual(presented.id, "activity-1")
        self.assertEqual(presented.area, ActivityArea.MANUAL_TRANSFER)
        self.assertEqual(presented.context, {"trace_id": "transfer-1"})

    def test_target_openapi_uses_clean_paths_and_fields(self) -> None:
        with self._fixture() as fixture:
            app = create_app(runtime=fixture.runtime, openapi_surface="target")
            spec = app.openapi()
            paths = spec["paths"]
            schemas = spec["components"]["schemas"]

            self.assertIn("/api/settings/health", paths)
            self.assertIn("/api/inventory/directories", paths)
            self.assertIn("/api/depots/{depot_id}", paths)
            self.assertIn("/api/watch/settings", paths)
            self.assertIn("/api/identify/sessions/{session_id}", paths)
            self.assertIn("/api/organize/sessions/{session_id}/conflict-reviews/action", paths)
            self.assertIn("/api/organize/sessions/{session_id}/candidates/{candidate_id}/detail", paths)
            self.assertIn("/api/organize/sessions/{session_id}/execute", paths)
            self.assertIn("/api/admin/cache/tmdb/clear", paths)
            self.assertIn("/api/admin/backup", paths)
            self.assertNotIn("/api/fs/directories", paths)
            self.assertNotIn("/api/inventory/origins/{origin_id}/unknown/retry", paths)
            self.assertNotIn("/api/admin/" + "config/backup", paths)
            self.assertFalse(any("source-" + "candidates" in path for path in paths))
            self.assertFalse(any(path.startswith("/api/" + "v1") for path in paths))

            depot_schema = schemas["Depot"]["properties"]
            self.assertIn("resolve_mode", depot_schema)
            self.assertNotIn("overwrite_mode", depot_schema)

            review_candidate = schemas["SourceCandidate"]["properties"]
            self.assertIn("conflict_reviews", review_candidate)
            self.assertNotIn("overwrite_groups", review_candidate)

            watch_schema = schemas["WatchSettings"]["properties"]
            self.assertIn("path", watch_schema)
            self.assertNotIn("watch_settings", schemas)

            error_detail = schemas["ApiErrorDetail"]["properties"]
            self.assertIn("code", error_detail)
            self.assertNotIn("type", error_detail)
            self.assertFalse(any(name.endswith("Schema") or "Schema-" in name for name in schemas))
            self.assertEqual([name for name in schemas if name.endswith("Response")], ["ApiErrorResponse"])

    def test_target_runtime_routes_preserve_config_and_workflow_behavior(self) -> None:
        with self._fixture() as fixture:
            client = fixture.client
            root = fixture.root
            watch_path = root / "watch"
            depot_path = root / "Depot"
            origin_path = root / "origin"
            watch_path.mkdir()
            origin_path.mkdir()
            (origin_path / "Movie.mkv").write_text("movie", encoding="utf-8")

            self.assertEqual(client.put("/api/watch/settings", json={"path": str(watch_path), "enabled": False}).status_code, 200)
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "name": "Movie staging",
                        "path": str(depot_path),
                        "media_type": "movie",
                        "enabled": True,
                        "resolve_mode": "full",
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                client.put(
                    "/api/origins/manual",
                    json={
                        "name": "Manual movies",
                        "path": str(origin_path),
                        "media_type": "movie",
                        "trigger": "manual",
                        "enabled": True,
                        "policy": {"target_depot_id": "Depot"},
                    },
                ).status_code,
                200,
            )

            depot = client.get("/api/depots/Depot").json()
            self.assertEqual(depot["resolve_mode"], "full")
            self.assertNotIn("overwrite_mode", depot)

            session_response = client.post("/api/organize/sessions", json={"origin_id": "manual"})
            self.assertEqual(session_response.status_code, 200)
            session = session_response.json()
            self.assertEqual(session["state"], "scanned")
            self.assertNotIn("overwrite_groups", session["review_candidates"][0])
            self.assertIn("conflict_reviews", session["review_candidates"][0])

            transfer = client.post("/api/transfer/jobs", json={"depot_id": "Depot", "requested_by": "target-api-test"})
            self.assertEqual(transfer.status_code, 200)
            self.assertEqual(transfer.json()["status"], "queued")
            self.assertEqual(client.post(f"/api/transfer/jobs/{transfer.json()['id']}/cancel").json()["status"], "cancelled")

    def test_target_admin_backup_uses_clean_data_contract_names(self) -> None:
        with self._fixture() as fixture:
            client = fixture.client
            root = fixture.root
            (root / "watch").mkdir()
            self.assertEqual(client.put("/api/watch/settings", json={"path": str(root / "watch"), "enabled": True}).status_code, 200)
            self.assertEqual(
                client.put(
                    "/api/depots/Depot",
                    json={
                        "name": "Movie staging",
                        "path": str(root / "Depot"),
                        "media_type": "movie",
                        "enabled": True,
                        "resolve_mode": "full",
                        "policy": {"target_library_path": str(root / "library"), "trigger": "manual"},
                    },
                ).status_code,
                200,
            )

            response = client.get("/api/admin/backup")

            self.assertEqual(response.status_code, 200)
            backup = yaml.safe_load(response.text)
            self.assertEqual(backup["version"], 2)
            self.assertIn("watch_settings", backup)
            self.assertNotIn("watch_config", backup)
            self.assertIn("resolve_mode", backup["depots"][0])
            self.assertNotIn("overwrite_mode", backup["depots"][0])

    def _fixture(self):
        return RuntimeApiFixture()

def _imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            imports.append((module, node.lineno))
            if module == "app":
                imports.extend((f"app.{alias.name}", node.lineno) for alias in node.names)
            else:
                imports.extend((f"{module}.{alias.name}", node.lineno) for alias in node.names)
    return imports


class _TransferJobLike:
    __slots__ = (
        "id",
        "depot_id",
        "status",
        "requested_by",
        "error_code",
        "created_at",
        "started_at",
        "finished_at",
        "message",
        "metadata",
    )

    def __init__(self) -> None:
        self.id = "transfer-1"
        self.depot_id = "Depot"
        self.status = domain_transfer.TransferStatus.QUEUED
        self.requested_by = "manual"
        self.error_code = None
        self.created_at = datetime(2026, 5, 26, tzinfo=timezone.utc)
        self.started_at = None
        self.finished_at = None
        self.message = None
        self.metadata = {"candidate_ids": ["a"]}


class _ActivityEventLike:
    __slots__ = (
        "id",
        "time",
        "area",
        "entity_type",
        "action",
        "status",
        "reason",
        "summary",
        "entity_source",
        "entity_target",
        "origin_id",
        "origin_name",
        "origin_path",
        "depot_id",
        "depot_name",
        "depot_path",
        "rule_id",
        "rule_name",
        "library_path",
        "media_type",
        "tmdb_id",
        "trace_id",
        "context",
    )

    def __init__(self) -> None:
        self.id = "activity-1"
        self.time = datetime(2026, 5, 26, tzinfo=timezone.utc)
        self.area = ActivityArea.MANUAL_TRANSFER
        self.entity_type = ActivityEntityType.TRANSFER_JOB
        self.action = ActivityAction.TRANSFER
        self.status = ActivityStatus.QUEUED
        self.reason = None
        self.summary = "queued"
        self.entity_source = None
        self.entity_target = None
        self.origin_id = None
        self.origin_name = None
        self.origin_path = None
        self.depot_id = "Depot"
        self.depot_name = "Depot"
        self.depot_path = Path("C:/Depot")
        self.rule_id = None
        self.rule_name = None
        self.library_path = Path("C:/Library")
        self.media_type = "movie"
        self.tmdb_id = None
        self.trace_id = "transfer-1"
        self.context = {"trace_id": "transfer-1"}


if __name__ == "__main__":
    unittest.main()
