# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: builds a single-file Windows .exe with no external
dependencies required on the target machine (PySide6, qfluentwidgets,
exifread, Pillow are all bundled in).

Build with:  pyinstaller packaging\\photo_organizer.spec --noconfirm
from the repo root (see packaging\\build.ps1).
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # packaging/ -> photo_organizer/ -> repo root

hiddenimports = (
    collect_submodules("qfluentwidgets")
    + [
        "PySide6.QtSvg",
        "PySide6.QtNetwork",
        "PySide6.QtXml",
    ]
)

datas = collect_data_files("qfluentwidgets") + [
    (str(REPO_ROOT / "photo_organizer" / "app" / "resources"), "photo_organizer/app/resources"),
]

a = Analysis(
    [str(REPO_ROOT / "photo_organizer" / "app" / "main.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtMultimedia",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PhotoOrganizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_ROOT / "photo_organizer" / "app" / "resources" / "icon.ico"),
)
