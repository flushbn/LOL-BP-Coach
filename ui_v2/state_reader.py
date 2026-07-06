"""Read the single UI state source: data/live_state.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
LIVE_STATE_PATH = ROOT / "data" / "live_state.json"

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
}


def read_state() -> dict[str, Any]:
    try:
        if not LIVE_STATE_PATH.exists():
            return dict(EMPTY_STATE)
        raw = LIVE_STATE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return dict(EMPTY_STATE)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(EMPTY_STATE)
        state = dict(EMPTY_STATE)
        state.update(data)
        state["role"] = state.get("role") or state.get("target_role", "")
        return state
    except Exception:
        return dict(EMPTY_STATE)

