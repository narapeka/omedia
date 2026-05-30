from __future__ import annotations

from collections.abc import Sequence

from app.domain.runtime import BackgroundWorker, WorkerStatus


class BackgroundRuntime:
    def __init__(self, workers: Sequence[BackgroundWorker]):
        self._workers = list(workers)

    def start(self) -> None:
        for worker in self._workers:
            worker.start()

    def stop(self) -> None:
        for worker in reversed(self._workers):
            worker.stop()

    def status(self) -> list[WorkerStatus]:
        return [worker.status() for worker in self._workers]

    @property
    def workers(self) -> tuple[BackgroundWorker, ...]:
        return tuple(self._workers)
