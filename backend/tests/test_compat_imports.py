from __future__ import annotations

import importlib

import pytest


TARGET_IMPORTS = [
    "app.api.http.routers",
    "app.api.http.schemas",
    "app.services.organize",
    "app.services.watch",
    "app.services.identify",
    "app.services.depot",
    "app.services.transfer",
    "app.services.inventory",
    "app.engines.scan",
    "app.engines.resolve",
    "app.engines.plan.tv",
    "app.engines.plan.movie",
    "app.infra.fs",
    "app.infra.db",
    "app.infra.db.models",
    "app.infra.db.records",
    "app.boot",
]


@pytest.mark.parametrize("module_name", TARGET_IMPORTS)
def test_target_public_imports_are_available(module_name: str) -> None:
    assert importlib.import_module(module_name)
