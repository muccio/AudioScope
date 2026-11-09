"""Runtime hook for AudioScope PyInstaller bundle.

Configures Qt platform plugin paths and PyAV dynamic library resolution
when executing inside a frozen standalone bundle.
"""

import os
import sys

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    # Resolve Qt plugins directory inside frozen bundle
    plugin_dirs = [
        os.path.join(bundle_dir, "PySide6", "plugins"),
        os.path.join(bundle_dir, "plugins"),
        os.path.join(bundle_dir, "PySide6", "Qt", "plugins"),
    ]
    for pdir in plugin_dirs:
        if os.path.isdir(pdir):
            os.environ["QT_PLUGIN_PATH"] = pdir
            break

    # Add dynamic library paths to system search PATH / DYLD_LIBRARY_PATH
    av_lib_candidates = [
        os.path.join(bundle_dir, "av.libs"),
        os.path.join(bundle_dir, "av"),
        os.path.join(bundle_dir, "numpy.libs"),
        os.path.join(bundle_dir, "scipy.libs"),
    ]
    for lib_dir in av_lib_candidates:
        if os.path.isdir(lib_dir):
            if sys.platform == "win32":
                os.environ["PATH"] = lib_dir + os.path.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(lib_dir)
                    except Exception:
                        pass
            elif sys.platform == "darwin":
                dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
                os.environ["DYLD_LIBRARY_PATH"] = lib_dir + (":" + dyld if dyld else "")
