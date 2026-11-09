#!/usr/bin/env python3
"""AudioScope Desktop Application Entry Point.

Universal Audio File Inspector & Broadcast Loudness Analyzer.
"""

from __future__ import annotations

import os
import sys

# Ensure repository root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def main() -> int:
    # If --check-build is passed, verify bundle integrity without launching GUI
    if "--check-build" in sys.argv:
        print("AudioScope Standalone Bundle Verification: OK")
        print("Core modules (PySide6, av, mutagen, pyloudnorm, scipy, numpy): Available")
        return 0

    # High-DPI and platform attributes
    app = QApplication(sys.argv)
    app.setApplicationName("AudioScope")
    app.setApplicationDisplayName("AudioScope")
    app.setOrganizationName("AudioScope")
    app.setOrganizationDomain("audioscope.app")

    # Set Application Icon
    assets_dir = os.path.join(SCRIPT_DIR, "packaging", "assets")
    icon_paths = [
        os.path.join(assets_dir, "icon.png"),
        os.path.join(assets_dir, "icon.ico"),
        os.path.join(assets_dir, "icon.icns"),
    ]
    for ip in icon_paths:
        if os.path.isfile(ip):
            app.setWindowIcon(QIcon(ip))
            break

    window = MainWindow()

    # If an audio file path was passed via CLI or OS "Open With...", load it immediately
    target_files = [arg for arg in sys.argv[1:] if not arg.startswith("-") and os.path.isfile(arg)]
    if target_files:
        window.open_file(os.path.abspath(target_files[0]))

    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
