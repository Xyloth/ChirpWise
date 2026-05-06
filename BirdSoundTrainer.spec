# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path.cwd()

datas = [
    (str(ROOT / "app"), "app"),
    (str(ROOT / "data" / "app"), "data/app"),
    (str(ROOT / "data" / "processed" / "training_clips_20s"), "data/processed/training_clips_20s"),
    (str(ROOT / "data" / "manifests"), "data/manifests"),
    (str(ROOT / "docs"), "docs"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "pyproject.toml"), "."),
]

a = Analysis(
    ["tools/portable_launcher.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name="BirdSoundTrainer",
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
    name="BirdSoundTrainer",
)
