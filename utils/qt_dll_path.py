import os
import sys
from pathlib import Path


base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
for folder in (base / "PySide6", base / "shiboken6", base):
    if folder.exists():
        try:
            os.add_dll_directory(str(folder))
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
