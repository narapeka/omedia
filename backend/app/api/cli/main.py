from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, Sequence

from app.core.error import ConfigurationError, OmediaError
from app.core.path import normalized_path_key
from app.domain.depot import Depot
from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy, Origin, OriginTrigger
from app.domain.rule import OrganizeRule
from app.domain.transfer import TransferJob
from app.services.organize.session import validate_ad_hoc_source


class ApplicationServices(Protocol):
    startup_settings: Any
    configuration: Any
    inventory: Any
    match: Any
    organize_pipeline: Any
    organizer: Any
    transfer_service: Any
    store: Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omedia", description="Disk-first media organizer")
    subcommands = parser.add_subparsers(dest="command", required=True)

    origin = subcommands.add_parser("origin", help="List or inspect Origins")
    origin.add_argument("--list", action="store_true")
    origin.add_argument("--origin")

    depot = subcommands.add_parser("depot", help="List or inspect Depots")
    depot.add_argument("--list", action="store_true")
    depot.add_argument("--depot")

    organize = subcommands.add_parser("organize", help="Organize a manual Origin or ad hoc source")
    organize.add_argument("--origin")
    organize.add_argument("--source")
    organize.add_argument("--depot")
    organize.add_argument("--type", choices=["movie", "tv"])
    organize.add_argument("--bucket", choices=["none", "first-char", "decade"])

    transfer = subcommands.add_parser("transfer", help="Transfer one Depot to Library")
    transfer.add_argument("--depot", required=True)

    return parser


def dispatch(args: argparse.Namespace, services: ApplicationServices):
    if args.command == "origin":
        return _origin_command(args, services)
    if args.command == "depot":
        return _depot_command(args, services)
    if args.command == "organize":
        return _organize_command(args, services)
    if args.command == "transfer":
        return _transfer_command(args, services)
    raise ValueError(f"Unknown command: {args.command}")


def run_cli(argv: Sequence[str], services: ApplicationServices):
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, services)


def run_cli_json(argv: Sequence[str], services: ApplicationServices) -> tuple[int, str]:
    try:
        payload = run_cli(argv, services)
        code = _success_exit_code(payload)
        return code, json.dumps({"ok": True, "result": to_jsonable(payload)}, ensure_ascii=False, sort_keys=True)
    except ConfigurationError as exc:
        return 2, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)
    except OmediaError as exc:
        return 3, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)
    except SystemExit as exc:
        return int(exc.code or 0), json.dumps({"ok": False, "error": {"type": "ArgumentError", "message": "Invalid arguments"}}, sort_keys=True)
    except Exception as exc:
        return 1, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)


def _origin_command(args: argparse.Namespace, services: ApplicationServices):
    _require_selector(args.list, args.origin, "origin")
    if args.list:
        return [_origin_summary(services, origin) for origin in services.configuration.list_origins()]
    return _origin_summary(services, _origin_for_selector(services, args.origin))


def _depot_command(args: argparse.Namespace, services: ApplicationServices):
    _require_selector(args.list, args.depot, "depot")
    if args.list:
        return [_depot_summary(services, depot) for depot in services.configuration.list_depots()]
    return _depot_detail(services, _depot_for_selector(services, args.depot))


def _organize_command(args: argparse.Namespace, services: ApplicationServices):
    if args.origin and args.source:
        raise ConfigurationError("Use either --origin or --source, not both")
    if args.origin:
        if args.depot or args.type or args.bucket:
            raise ConfigurationError("--origin uses the configured Origin policy and rejects --depot, --type, and --bucket")
        origin = _origin_for_selector(services, args.origin)
        if origin.trigger == OriginTrigger.WATCH:
            raise ConfigurationError("Watched folders are automatic; use a manual Origin")
        depot = services.configuration.get_depot(origin.policy.target_depot_id)
        rule = services.store.get_organize_rule(origin.policy.organize_rule_id) if origin.policy.organize_rule_id else None
        return _organize_source(
            services,
            source_path=origin.path,
            media_type=origin.media_type,
            policy=origin.policy,
            depot=depot,
            rule=rule,
            source_label=origin.id,
            context={"origin_id": origin.id, "origin_path": str(origin.path), "organize_rule_id": origin.policy.organize_rule_id},
        )
    if args.source:
        if not args.depot:
            raise ConfigurationError("Ad hoc organize requires --depot")
        if not args.type:
            raise ConfigurationError("Ad hoc organize requires --type movie|tv")
        source_path = Path(args.source)
        depot = _depot_for_selector(services, args.depot)
        media_type = MediaType(args.type)
        validate_ad_hoc_source(
            source_path,
            watch_settings=services.configuration.get_watch_settings(),
            origins=services.configuration.list_origins(),
            depots=services.configuration.list_depots(),
        )
        return _organize_source(
            services,
            source_path=source_path,
            media_type=media_type,
            policy=OrganizePolicy(target_depot_id=depot.id),
            depot=depot,
            rule=_bucket_rule(args.bucket or "none"),
            source_label=str(source_path),
            context={"bucket": args.bucket or "none"},
        )
    raise ConfigurationError("Organize requires --origin or --source")


def _transfer_command(args: argparse.Namespace, services: ApplicationServices):
    depot = _depot_for_selector(services, args.depot)
    result = services.transfer_service.execute_depot(depot, requested_by="cli")
    job = result.job
    return {
        "job": result.job,
        "progress": [
            {"status": "queued", "job_id": job.id, "depot_id": depot.id},
            {"status": result.job.status, "job_id": job.id, "moved": result.moved, "skipped": result.skipped, "failed": result.failed},
        ],
        "moved": result.moved,
        "skipped": result.skipped,
        "failed": result.failed,
    }


def _organize_source(
    services: ApplicationServices,
    *,
    source_path: Path,
    media_type: MediaType,
    policy: OrganizePolicy,
    depot: Depot,
    rule: OrganizeRule | None,
    source_label: str,
    context: dict[str, Any] | None = None,
):
    return services.organize_pipeline.organize_source_direct(
        source_path=source_path,
        media_type=media_type,
        policy=policy,
        depot=depot,
        rule=rule,
        source_label=source_label,
        context=context,
    )


def _origin_summary(services: ApplicationServices, origin: Origin) -> dict:
    scan = services.inventory.origin_summary(origin)
    return {
        "id": origin.id,
        "name": origin.name,
        "path": origin.path,
        "media_type": origin.media_type,
        "trigger": origin.trigger,
        "enabled": origin.enabled,
        "target_depot_id": origin.policy.target_depot_id,
        "candidate_count": scan.candidate_count,
        "file_count": scan.file_count,
        "unknown_count": scan.unknown_count,
    }


def _depot_summary(services: ApplicationServices, depot: Depot) -> dict:
    scan = services.inventory.depot_summary(depot)
    return {
        "id": depot.id,
        "name": depot.name,
        "path": depot.path,
        "media_type": depot.media_type,
        "enabled": depot.enabled,
        "pending_count": scan.pending_count,
        "target_library_path": depot.policy.target_library_path,
        "transfer_rule_id": depot.policy.transfer_rule_id,
        "transfer_trigger": depot.policy.trigger,
        "recent_transfers": _recent_transfers(services, depot.id),
    }


def _depot_detail(services: ApplicationServices, depot: Depot) -> dict:
    summary = _depot_summary(services, depot)
    detail = services.inventory.depot_detail(depot)
    return {
        **summary,
        "candidates": detail.candidates,
    }


def _recent_transfers(services: ApplicationServices, depot_id: str) -> list[TransferJob]:
    if not hasattr(services.store, "list_transfer_jobs"):
        return []
    return [job for job in services.store.list_transfer_jobs(limit=20) if job.depot_id == depot_id][:5]


def _origin_for_selector(services: ApplicationServices, selector: str) -> Origin:
    for origin in services.configuration.list_origins():
        if origin.id == selector or origin.name.casefold() == selector.casefold() or _selector_path_matches(selector, origin.path):
            return origin
    raise ConfigurationError(f"Unknown Origin: {selector}")


def _depot_for_selector(services: ApplicationServices, selector: str) -> Depot:
    for depot in services.configuration.list_depots():
        if depot.id == selector or depot.name.casefold() == selector.casefold() or _selector_path_matches(selector, depot.path):
            return depot
    raise ConfigurationError(f"Unknown Depot: {selector}")


def _selector_path_matches(selector: str, path: Path) -> bool:
    selector_path = Path(selector)
    if not selector_path.is_absolute():
        return False
    return normalized_path_key(selector_path) == normalized_path_key(path)


def _bucket_rule(bucket: str) -> OrganizeRule | None:
    if bucket == "none":
        return None
    variable = "{first_char}" if bucket == "first-char" else "{decade}"
    return OrganizeRule(id=f"cli-{bucket}", name=f"CLI {bucket}", fallback_bucket=variable)


def _require_selector(list_selected: bool, item: str | None, label: str) -> None:
    if list_selected == bool(item):
        raise ConfigurationError(f"Use exactly one of --list or --{label}")


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return value


def _success_exit_code(payload: Any) -> int:
    job = payload.get("job") if isinstance(payload, dict) else None
    status = getattr(job, "status", None)
    if status and getattr(status, "value", status) == "failed":
        return 3
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"-h", "--help"} for arg in raw_args):
        build_parser().parse_args(raw_args)
        return 0

    try:
        from app.boot.runtime import create_runtime_context_from_settings, resolve_runtime_settings

        services = create_runtime_context_from_settings(resolve_runtime_settings())
        code, output = run_cli_json(raw_args, services)
    except ConfigurationError as exc:
        code, output = 2, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)
    except OmediaError as exc:
        code, output = 3, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)
    except Exception as exc:
        code, output = 1, json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}, sort_keys=True)
    print(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

