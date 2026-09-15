# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH).resolve()
branding_dir = project_root / "assets" / "branding"
icon_file = branding_dir / "nodaris_icon.ico"

analysis = Analysis(
    [str(project_root / "desktop" / "tv_main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(branding_dir), "assets/branding"),
    ],
    hiddenimports=[],
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
    name="NODARIS TV",
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
    name="NODARIS TV",
)
