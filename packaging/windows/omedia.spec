# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


repo_root = Path(SPECPATH).parents[1]
backend_dir = repo_root / "backend"
sys.path.insert(0, str(backend_dir))

datas = [
    (str(repo_root / "frontend" / "dist"), "frontend/dist"),
    (str(repo_root / "data" / "common.example.yaml"), "data"),
    (str(backend_dir / "app" / "infra" / "llm" / "prompts"), "app/infra/llm/prompts"),
    (str(backend_dir / "app" / "infra" / "db" / "migrations"), "app/infra/db/migrations"),
]

hiddenimports = collect_submodules("app.infra.db.migrations.versions")

a = Analysis(
    [str(backend_dir / "app" / "server.py")],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="omedia",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="omedia",
)
