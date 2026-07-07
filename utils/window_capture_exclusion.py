from __future__ import annotations

import ctypes
import os


WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def exclude_window_from_capture(hwnd: int) -> bool:
    """Ask Windows to hide a top-level window from screen capture.

    This is best-effort. It works on modern Windows builds; older builds fall
    back to monitor-only protection. Non-Windows platforms simply return False.
    """
    if os.name != "nt" or not hwnd:
        return False

    user32 = ctypes.windll.user32
    for affinity in (WDA_EXCLUDEFROMCAPTURE, WDA_MONITOR):
        try:
            if user32.SetWindowDisplayAffinity(int(hwnd), affinity):
                return True
        except Exception:
            continue
    return False

