from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from app.boot.runtime import RuntimeContext, RuntimeSettings, create_runtime_context_from_settings


class RuntimeNotStarted(RuntimeError):
    pass


@dataclass
class RuntimeManager:
    settings: RuntimeSettings
    runtime: RuntimeContext | None = None
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _owns_runtime: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._owns_runtime = self.runtime is None

    def get(self) -> RuntimeContext:
        with self._lock:
            if self.runtime is None:
                raise RuntimeNotStarted("Runtime has not been started")
            return self.runtime

    def start(self) -> RuntimeContext:
        with self._lock:
            if self.runtime is None:
                self.runtime = create_runtime_context_from_settings(self.settings)
                self._owns_runtime = True
            self.runtime.start_automations()
            return self.runtime

    def stop(self) -> None:
        with self._lock:
            runtime = self.runtime
            if runtime is None:
                return
            if self._owns_runtime:
                runtime.close()
                self.runtime = None
                return
            runtime.stop_automations()

    def reload(self) -> RuntimeContext:
        new_runtime = create_runtime_context_from_settings(self.settings)
        with self._lock:
            old_runtime = self.runtime
            old_owns_runtime = self._owns_runtime
            try:
                if old_runtime is not None:
                    old_runtime.stop_automations()
                self.runtime = new_runtime
                self._owns_runtime = True
                new_runtime.start_automations()
            except Exception:
                new_runtime.close()
                self.runtime = old_runtime
                self._owns_runtime = old_owns_runtime
                if old_runtime is not None:
                    old_runtime.start_automations()
                raise
        if old_runtime is not None and old_owns_runtime:
            old_runtime.close()
        return new_runtime
