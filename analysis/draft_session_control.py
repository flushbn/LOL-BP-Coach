from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LIVE_STATE_PATH = DATA_DIR / "live_state.json"
LIVE_DRAFT_PATH = DATA_DIR / "live_draft.json"
CONTROL_PATH = DATA_DIR / "draft_session_control.json"

EMPTY_STATE: dict[str, Any] = {
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
    "recognition": {
        "phase": "waiting",
        "message": "等待识别",
        "recommendation_status": "waiting",
        "ally_count": 0,
        "enemy_count": 0,
        "ban_count": 0,
        "last_scan_at": 0,
    },
}


def read_control() -> dict[str, Any]:
    try:
        if not CONTROL_PATH.exists():
            return _default_control()
        data = json.loads(CONTROL_PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return _default_control()
        control = _default_control()
        control.update(data)
        return control
    except Exception:
        return _default_control()


def is_paused() -> bool:
    return bool(read_control().get("paused"))


def pause_state(state: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    frozen = dict(state or {})
    recognition = dict(frozen.get("recognition", {}) or {})
    recognition.update(
        {
            "phase": "paused",
            "message": "推荐结果已定格",
            "recommendation_status": "paused",
            "last_scan_at": now,
        }
    )
    frozen["recognition"] = recognition
    frozen["timestamp"] = now
    frozen["session_control"] = {
        "paused": True,
        "paused_at": now,
        "session_id": read_control().get("session_id"),
    }

    control = read_control()
    control.update(
        {
            "paused": True,
            "paused_at": now,
            "frozen_state": frozen,
        }
    )
    _write_json(CONTROL_PATH, control)
    write_live_state(frozen, force=True)
    return frozen


def resume_updates() -> dict[str, Any]:
    now = int(time.time())
    control = read_control()
    control.update({"paused": False, "resumed_at": now})
    _write_json(CONTROL_PATH, control)

    state = read_live_state()
    state["timestamp"] = now
    state["session_control"] = {
        "paused": False,
        "resumed_at": now,
        "session_id": control.get("session_id"),
    }
    recognition = dict(state.get("recognition", {}) or {})
    recognition.update(
        {
            "phase": "resumed",
            "message": "已继续刷新，等待下一次识别结果",
            "recommendation_status": "waiting",
            "last_scan_at": now,
        }
    )
    state["recognition"] = recognition
    write_live_state(state, force=True)
    return state


def start_new_game(role: str = "") -> dict[str, Any]:
    now = int(time.time())
    session_id = str(now)
    control = _default_control()
    control.update(
        {
            "paused": False,
            "session_id": session_id,
            "started_at": now,
            "previous_frozen_state": read_control().get("frozen_state", {}),
        }
    )
    _write_json(CONTROL_PATH, control)

    state = dict(EMPTY_STATE)
    state.update(
        {
            "timestamp": now,
            "role": role or "",
            "target_role": role or "",
            "session_control": {
                "paused": False,
                "session_id": session_id,
                "started_at": now,
            },
            "recognition": {
                "phase": "new_game",
                "message": "新的一局已开始，等待识别 BP",
                "recommendation_status": "waiting",
                "ally_count": 0,
                "enemy_count": 0,
                "ban_count": 0,
                "last_scan_at": now,
            },
        }
    )
    write_live_state(state, force=True)
    return state


def read_live_state() -> dict[str, Any]:
    try:
        if LIVE_STATE_PATH.exists():
            data = json.loads(LIVE_STATE_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                state = dict(EMPTY_STATE)
                state.update(data)
                return state
    except Exception:
        pass
    return dict(EMPTY_STATE)


def write_live_state(state: dict[str, Any], force: bool = False) -> bool:
    if not force and is_paused():
        return False
    payload = json.dumps(state, ensure_ascii=False)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_STATE_PATH.write_text(payload, encoding="utf-8")
    LIVE_DRAFT_PATH.write_text(payload, encoding="utf-8")
    return True


def _default_control() -> dict[str, Any]:
    return {
        "paused": False,
        "session_id": "",
        "paused_at": 0,
        "resumed_at": 0,
        "started_at": 0,
        "frozen_state": {},
    }


def _write_json(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
