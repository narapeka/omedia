from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.domain.runtime import WorkerStatus
from app.boot.background import BackgroundRuntime
from app.boot.manager import RuntimeManager, RuntimeNotStarted
from app.boot.runtime import RuntimeSettings, create_runtime_context, resolve_runtime_settings
from app.main import create_app


class BackgroundRuntimeTests(unittest.TestCase):
    def test_runtime_starts_workers_and_stops_in_reverse_order(self) -> None:
        events: list[str] = []
        runtime = BackgroundRuntime(
            [
                DummyWorker("watch", events),
                DummyWorker("transfer", events),
            ]
        )

        runtime.start()
        statuses = runtime.status()
        runtime.stop()

        self.assertEqual(events, ["start:watch", "start:transfer", "stop:transfer", "stop:watch"])
        self.assertEqual([status.id for status in statuses], ["watch", "transfer"])
        self.assertTrue(all(status.running for status in statuses))

    def test_runtime_context_delegates_automation_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = resolve_runtime_settings(cwd=Path(__file__).resolve().parents[1])
            context = create_runtime_context(
                common_path=settings.common_path,
                db_path=root / "state.sqlite",
            )
            try:
                self.assertIsInstance(context.background, BackgroundRuntime)
                self.assertEqual(context.background.workers, (context.watch_automation, context.transfer_service))

                background = FakeBackgroundRuntime()
                object.__setattr__(context, "background", background)

                context.start_automations()
                context.stop_automations()

                self.assertEqual(background.events, ["start", "stop"])
            finally:
                context.store.close()

    def test_runtime_manager_lazily_creates_owned_runtime(self) -> None:
        settings = RuntimeSettings(common_path=Path("common.yaml"), db_path=Path("state.sqlite"))
        runtime = FakeManagedRuntime()
        manager = RuntimeManager(settings)

        with self.assertRaises(RuntimeNotStarted):
            manager.get()

        with patch("app.boot.manager.create_runtime_context_from_settings", return_value=runtime) as create_runtime:
            self.assertIs(manager.start(), runtime)

        create_runtime.assert_called_once_with(settings)
        self.assertIs(manager.get(), runtime)

        manager.stop()

        self.assertEqual(runtime.events, ["start", "close"])
        with self.assertRaises(RuntimeNotStarted):
            manager.get()

    def test_runtime_manager_does_not_close_injected_runtime_on_stop(self) -> None:
        settings = RuntimeSettings(common_path=Path("common.yaml"), db_path=Path("state.sqlite"))
        runtime = FakeManagedRuntime()
        manager = RuntimeManager(settings, runtime=runtime)

        manager.start()
        manager.stop()

        self.assertEqual(runtime.events, ["start", "stop"])

    def test_runtime_manager_reload_rolls_back_when_new_runtime_start_fails(self) -> None:
        settings = RuntimeSettings(common_path=Path("common.yaml"), db_path=Path("state.sqlite"))
        old_runtime = FakeManagedRuntime()
        new_runtime = FakeManagedRuntime(start_error=RuntimeError("boom"))
        manager = RuntimeManager(settings, runtime=old_runtime)

        with patch("app.boot.manager.create_runtime_context_from_settings", return_value=new_runtime):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                manager.reload()

        self.assertIs(manager.get(), old_runtime)
        self.assertEqual(old_runtime.events, ["stop", "start"])
        self.assertEqual(new_runtime.events, ["start", "close"])

    def test_create_app_does_not_create_runtime_before_lifespan_start(self) -> None:
        settings = RuntimeSettings(common_path=Path("common.yaml"), db_path=Path("state.sqlite"))

        with patch("app.boot.manager.create_runtime_context_from_settings") as create_runtime:
            app = create_app(settings=settings)

        create_runtime.assert_not_called()
        self.assertIsInstance(app.state.runtime_manager, RuntimeManager)


class DummyWorker:
    def __init__(self, worker_id: str, events: list[str]):
        self.worker_id = worker_id
        self.events = events
        self.running = False

    def start(self) -> None:
        self.events.append(f"start:{self.worker_id}")
        self.running = True

    def stop(self) -> None:
        self.events.append(f"stop:{self.worker_id}")
        self.running = False

    def status(self) -> WorkerStatus:
        return WorkerStatus(
            id=self.worker_id,
            label=self.worker_id.title(),
            running=self.running,
            state="running" if self.running else "stopped",
        )


class FakeBackgroundRuntime:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


class FakeManagedRuntime:
    def __init__(self, *, start_error: Exception | None = None) -> None:
        self.events: list[str] = []
        self.start_error = start_error

    def start_automations(self) -> None:
        self.events.append("start")
        if self.start_error is not None:
            raise self.start_error

    def stop_automations(self) -> None:
        self.events.append("stop")

    def close(self) -> None:
        self.events.append("close")


if __name__ == "__main__":
    unittest.main()
