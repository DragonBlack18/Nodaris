# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH).resolve()
icon_file = project_root / "assets" / "branding" / "nodaris_icon.ico"

analysis = Analysis(
    [str(project_root / "core" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (
            str(project_root / "defaults" / "ips.json"),
            "defaults",
        ),
    ],
    # Uvicorn resolve "api.main:app" dinamicamente em runtime.
    hiddenimports=[
        "api.main",
        "core.watchdog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="NODARIS Core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_file),
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="NODARIS Core",
)
