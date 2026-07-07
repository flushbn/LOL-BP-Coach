"""LoL BP Assistant — Desktop App Entry Point (Release V1)"""
import sys, os
from pathlib import Path

# Ensure project root is on path
if getattr(sys, "frozen", False):
    BASE = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "core"))

# Init crash handler
from utils.crash_handler import init_crash_log
init_crash_log(BASE / "logs" / "crash.log")

# Init resource manager
from utils.resource_manager import ResourceManager
rm = ResourceManager(BASE)

# Try to seed cache from bundled seed data
try:
    seeded = rm.seed_cache("data/cache_seed")
    if seeded:
        print(f"Seeded {seeded} cache files")
except:
    pass

from PySide6.QtWidgets import QApplication, QMessageBox
from ui_v2.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LoL BP Assistant")

    # First-run welcome
    try:
        first_run = not (rm.data("live_draft.json").exists())
        if first_run:
            # Create initial state
            rm.write_json({
                "timestamp": 0,
                "role": "",
                "ally": [],
                "enemy": [],
                "bans": [],
                "recommendations": [],
                "lane_recommendations": [],
                "coach": {},
                "prepick": {}
            }, "live_draft.json")
    except:
        pass

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--recognize":
        from lol_bp_screenshot import recommend_loop

        recommend_loop(sys.argv[2] if len(sys.argv) > 2 else "")
        sys.exit(0)

    main()
