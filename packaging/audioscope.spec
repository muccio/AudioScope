# -*- mode: python ; coding: utf-8 -*-
"""Master PyInstaller Specification for AudioScope.

Produces standalone native bundles:
- macOS: AudioScope.app (.app bundle with Info.plist audio document types)
- Windows: AudioScope.exe (standalone executable with manifest and VC++ runtime)
- Linux: AudioScope (standalone binary)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_submodules

block_cipher = None

# Determine repository root
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.abspath(os.path.join(spec_dir, ".."))
sys.path.insert(0, project_root)

# 1. Discover PyAV dynamic libraries and data files
av_binaries = collect_dynamic_libs("av")
av_datas = collect_data_files("av")
pyloudnorm_datas = collect_data_files("pyloudnorm")

# 2. Collect hidden imports
hidden_imports = [
    "pyloudnorm",
    "scipy.signal",
    "scipy.special",
    "scipy.ndimage",
    "mutagen",
    "mutagen.wave",
    "mutagen.id3",
    "mutagen.flac",
    "mutagen.mp3",
    "mutagen.mp4",
    "mutagen.aiff",
    "mutagen.ogg",
    "mutagen.oggvorbis",
    "mutagen.oggopus",
    "mutagen.asf",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PIL",
    "PIL.Image",
]
hidden_imports += collect_submodules("mutagen")
hidden_imports += collect_submodules("pyloudnorm")

# 3. Application Assets & Datas
datas = [
    (os.path.join(project_root, "packaging", "assets"), "assets"),
]
datas += av_datas
datas += pyloudnorm_datas

binaries = [] + av_binaries

# 4. Runtime Hook
rthook_path = os.path.join(project_root, "packaging", "rthook_qt.py")
runtime_hooks = [rthook_path] if os.path.isfile(rthook_path) else []

# 5. Analysis
a = Analysis(
    [os.path.join(project_root, "run.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# App icon selection based on OS
if sys.platform == "darwin":
    icon_file = os.path.join(project_root, "packaging", "assets", "icon.icns")
else:
    icon_file = os.path.join(project_root, "packaging", "assets", "icon.ico")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioScope",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if os.path.isfile(icon_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AudioScope",
)

# 6. macOS Application Bundle Configuration
if sys.platform == "darwin":
    # Universal audio formats for macOS "Open With..." and dock drag-and-drop
    audio_extensions = [
        "wav", "bwf", "aif", "aiff", "flac", "alac", "mp3", "ogg", "opus",
        "m4a", "aac", "wma", "caf", "ac3", "dsf", "dff"
    ]
    doc_types = [
        {
            "CFBundleTypeName": f"{ext.upper()} Audio File",
            "CFBundleTypeRole": "Viewer",
            "CFBundleTypeExtensions": [ext],
            "CFBundleTypeIconFile": "icon.icns",
            "LSHandlerRank": "Alternate",
        }
        for ext in audio_extensions
    ]

    info_plist = {
        "CFBundleName": "AudioScope",
        "CFBundleDisplayName": "AudioScope",
        "CFBundleIdentifier": "com.audioscope.analyzer",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "NSSupportsAutomaticGraphicsSwitching": True,
        "LSMinimumSystemVersion": "12.0",
        "CFBundleDocumentTypes": doc_types,
        "NSHumanReadableCopyright": "Copyright © 2026 AudioScope Project. MIT License.",
    }

    app = BUNDLE(
        coll,
        name="AudioScope.app",
        icon=icon_file,
        bundle_identifier="com.audioscope.analyzer",
        info_plist=info_plist,
    )
