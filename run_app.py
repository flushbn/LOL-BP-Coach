from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from ui_v2.main_window import MainWindow


EMPTY_STATE = {
    "timestamp": 0,
    "role": "",
    "target_role": "",
    "ally": [],
    "enemy": [],
    "bans": [],
    "recommendations": [],
    "lane_recommendations": [],
    "role_inference": {},
    "inferred_lane_opponent": "",
    "coach": {},
    "prepick": {},
}


def ensure_runtime_files() -> None:
    for folder in ("data", "data/cache", "logs", "config"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    for name in ("live_state.json", "live_draft.json"):
        path = ROOT / "data" / name
        if not path.exists():
            path.write_text(json.dumps(EMPTY_STATE, ensure_ascii=False, indent=2), encoding="utf-8")

    defaults = {
        "match_sessions.json": [],
        "player_profile.json": {},
    }
    for name, payload in defaults.items():
        path = ROOT / "data" / name
        if not path.exists():
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ensure_runtime_files()
    app = QApplication(sys.argv)
    app.setApplicationName("LOL BP Coach")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
