import os
import sys
import ctypes
from pathlib import Path


base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for folder in (base / "PySide6", base / "shiboken6", base):
    if folder.exists():
        try:
            os.add_dll_directory(str(folder))
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")

for library in (
    base / "shiboken6" / "shiboken6.abi3.dll",
    base / "PySide6" / "Qt6Core.dll",
    base / "PySide6" / "Qt6Gui.dll",
    base / "PySide6" / "Qt6Widgets.dll",
    base / "PySide6" / "pyside6.abi3.dll",
):
    if library.exists():
        try:
            ctypes.WinDLL(str(library))
        except OSError:
            pass
