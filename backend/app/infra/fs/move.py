from __future__ import annotations

import multiprocessing
import os
import queue
import shutil
import time
from collections.abc import Collection
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.infra.fs.cleanup import cleanup_source_parents
from app.infra.fs.constants import (
    MOVE_KILL_GRACE_SECONDS,
    MOVE_SETTLE_SECONDS,
    MOVE_TIMEOUT_SECONDS,
)
from app.infra.fs.result import CleanupResult, MoveResult, StorageMoveStatus


def move_with_replace(
    source: Path,
    destination: Path,
    *,
    cleanup_root: Path | None,
    sidecar_extensions: Collection[str],
    cleanup_stop_root: Path | None = None,
    subtitle_extensions: Collection[str] | None = None,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MoveResult:
    source = Path(source)
    destination = Path(destination)
    source_parent = source.parent
    queue_: multiprocessing.Queue[dict[str, Any]] = multiprocessing.Queue(maxsize=1)
    process = multiprocessing.Process(
        target=_move_worker,
        args=(str(source), str(destination), queue_),
        name="omedia-storage-move",
        daemon=False,
    )
    process.start()
    process.join(MOVE_TIMEOUT_SECONDS)
    if process.is_alive():
        return _handle_timeout(
            process,
            source,
            destination,
            cleanup_root=cleanup_root,
            cleanup_stop_root=cleanup_stop_root,
            source_parent=source_parent,
            sidecar_extensions=sidecar_extensions,
            subtitle_extensions=subtitle_extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )

    payload = _queue_payload(queue_)
    if payload.get("status") == "succeeded":
        result = MoveResult(
            status=StorageMoveStatus.SUCCEEDED,
            source_path=source,
            destination_path=destination,
            message="Moved",
            timed_out=False,
            source_exists_after=source.exists(),
            destination_exists_after=destination.exists(),
        )
        return _with_cleanup(
            result,
            cleanup_root,
            cleanup_stop_root,
            source_parent,
            sidecar_extensions,
            subtitle_extensions=subtitle_extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    if payload.get("status") == "failed":
        return MoveResult(
            status=StorageMoveStatus.FAILED,
            source_path=source,
            destination_path=destination,
            message=str(payload.get("message") or "Move failed"),
            error_type=str(payload.get("error_type") or "MoveError"),
            timed_out=False,
            source_exists_after=source.exists(),
            destination_exists_after=destination.exists(),
        )
    return MoveResult(
        status=StorageMoveStatus.FAILED,
        source_path=source,
        destination_path=destination,
        message="Move process exited without reporting a result",
        error_type="MissingMoveResult",
        timed_out=False,
        source_exists_after=source.exists(),
        destination_exists_after=destination.exists(),
    )


def classify_timeout_result(source: Path, destination: Path) -> MoveResult:
    source_exists = source.exists()
    destination_exists = destination.exists()
    if source_exists and not destination_exists:
        return MoveResult(
            status=StorageMoveStatus.TIMEOUT,
            source_path=source,
            destination_path=destination,
            message="Move timed out; source remains available for retry",
            error_type="MoveTimeout",
            timed_out=True,
            source_exists_after=True,
            destination_exists_after=False,
        )
    if not source_exists and destination_exists:
        return MoveResult(
            status=StorageMoveStatus.SUCCEEDED,
            source_path=source,
            destination_path=destination,
            message="Move exceeded timeout but completed on disk",
            timed_out=True,
            source_exists_after=False,
            destination_exists_after=True,
        )
    return MoveResult(
        status=StorageMoveStatus.AMBIGUOUS,
        source_path=source,
        destination_path=destination,
        message="Move timed out and left ambiguous disk state",
        error_type="AmbiguousMoveState",
        timed_out=True,
        source_exists_after=source_exists,
        destination_exists_after=destination_exists,
    )


def _handle_timeout(
    process: multiprocessing.Process,
    source: Path,
    destination: Path,
    *,
    cleanup_root: Path | None,
    cleanup_stop_root: Path | None,
    source_parent: Path,
    sidecar_extensions: Collection[str],
    subtitle_extensions: Collection[str] | None,
    min_non_subtitle_file_size_bytes: int | None,
) -> MoveResult:
    process.terminate()
    process.join(MOVE_KILL_GRACE_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(MOVE_KILL_GRACE_SECONDS)
    time.sleep(MOVE_SETTLE_SECONDS)
    result = classify_timeout_result(source, destination)
    if result.succeeded:
        return _with_cleanup(
            result,
            cleanup_root,
            cleanup_stop_root,
            source_parent,
            sidecar_extensions,
            subtitle_extensions=subtitle_extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    return result


def _with_cleanup(
    result: MoveResult,
    cleanup_root: Path | None,
    cleanup_stop_root: Path | None,
    source_parent: Path,
    sidecar_extensions: Collection[str],
    subtitle_extensions: Collection[str] | None = None,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MoveResult:
    if cleanup_root is None:
        return replace(result, cleanup=CleanupResult(attempted=False, stop_reason="no_cleanup_root"))
    cleanup = cleanup_source_parents(
        source_parent,
        cleanup_root,
        sidecar_extensions,
        stop_root=cleanup_stop_root,
        subtitle_extensions=subtitle_extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    return replace(result, cleanup=cleanup)


def _queue_payload(queue_: multiprocessing.Queue[dict[str, Any]]) -> dict[str, Any]:
    try:
        return queue_.get_nowait()
    except queue.Empty:
        return {}


def _move_worker(source_text: str, destination_text: str, result_queue) -> None:
    source = Path(source_text)
    destination = Path(destination_text)
    try:
        _direct_move_with_replace(source, destination)
    except Exception as exc:
        result_queue.put({"status": "failed", "error_type": type(exc).__name__, "message": str(exc)})
        return
    result_queue.put({"status": "succeeded"})


def _direct_move_with_replace(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        _remove_destination(destination)
    if source.is_dir():
        os.rename(source, destination)
        return
    os.replace(source, destination)


def _remove_destination(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
