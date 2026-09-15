# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package in ("pygame", "pystray", "win10toast"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

analysis = Analysis(
    ["monitorping.py"],
    pathex=[],
    binaries=[],
    datas=[("ips.json", ".")],
    hiddenimports=hiddenimports,
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
    analysis.binaries,
    analysis.datas,
    [],
    name="MonitorPing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
