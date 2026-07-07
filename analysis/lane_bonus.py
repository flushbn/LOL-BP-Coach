"""Lane Bonus V1 — Convert Lolalytics matchup delta to a -5~+5 bonus."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from analysis.lolalytics_client import LolalyticsClient
from analysis.role_inference_engine import RoleInferenceEngine

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
_LOCAL_COUNTER_CACHE: Optional[dict] = None

# Role name → role_data.json key
_ROLE_TO_KEY = {
    "Top": "TOP",
    "TOP": "TOP",
    "Jungle": "JUNGLE",
    "JUNGLE": "JUNGLE",
    "Mid": "MIDDLE",
    "MID": "MIDDLE",
    "ADC": "BOTTOM",
    "BOTTOM": "BOTTOM",
    "Support": "UTILITY",
    "UTILITY": "UTILITY",
}

# Role name → Lolalytics lane name
_ROLE_TO_LANE = {
    "Top": "top",
    "TOP": "top",
    "Jungle": "jungle",
    "JUNGLE": "jungle",
    "Mid": "middle",
    "MID": "middle",
    "ADC": "bottom",
    "BOTTOM": "bottom",
    "Support": "support",
    "UTILITY": "support",
}

_ROLE_TO_COUNTER_ROLE = {
    "Top": "TOP",
    "TOP": "TOP",
    "Jungle": "JUNGLE",
    "JUNGLE": "JUNGLE",
    "Mid": "MID",
    "MID": "MID",
    "MIDDLE": "MID",
    "ADC": "ADC",
    "BOTTOM": "ADC",
    "Support": "SUPPORT",
    "SUPPORT": "SUPPORT",
    "UTILITY": "SUPPORT",
}


def _load_local_counter_data() -> dict:
    global _LOCAL_COUNTER_CACHE
    if _LOCAL_COUNTER_CACHE is not None:
        return _LOCAL_COUNTER_CACHE

    patch = None
    patch_file = DATA_DIR / "patch_version.json"
    try:
        if patch_file.exists():
            patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
    except Exception:
        patch = None

    candidates = []
    if patch:
        candidates.append(DATA_DIR / str(patch) / "counter_data.json")
    candidates.append(DATA_DIR / "counter_data.json")

    for path in candidates:
        try:
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                _LOCAL_COUNTER_CACHE = raw.get("champions", raw)
                return _LOCAL_COUNTER_CACHE
        except Exception:
            continue
    _LOCAL_COUNTER_CACHE = {}
    return _LOCAL_COUNTER_CACHE


def _lookup_key(data: dict, name: str) -> Optional[str]:
    if not name:
        return None
    if name in data:
        return name
    lowered = name.lower()
    for key in data:
        if key.lower() == lowered:
            return key
    return None


def _local_matchup(champion: str, opponent: str, role: str) -> Optional[dict]:
    data = _load_local_counter_data()
    champion_key = _lookup_key(data, champion)
    if not champion_key:
        return None

    opponents = data.get(champion_key, {}) or {}
    opponent_key = _lookup_key(opponents, opponent)
    if not opponent_key:
        return None

    payload = opponents.get(opponent_key)
    if not isinstance(payload, dict):
        return None

    expected_role = _ROLE_TO_COUNTER_ROLE.get(role)
    payload_role = str(payload.get("role", "")).upper()
    if expected_role and payload_role and payload_role != expected_role:
        return None

    delta = payload.get("winrate_delta", payload.get("delta"))
    if delta is None:
        return None
    return {
        "champion": champion_key,
        "opponent": opponent_key,
        "delta": float(delta),
        "games": int(payload.get("games", 0) or 0),
        "source": "local_counter_data",
    }


def find_enemy_lane_champion(
    enemy_picks: List[str],
    target_role: str,
    role_data: Dict[str, Dict[str, int]],
    min_score: int = 20,
) -> Optional[str]:
    """Find the enemy champion most likely in the target lane."""
    try:
        inferred = RoleInferenceEngine().infer_enemy_lane(enemy_picks, target_role, min_probability=0.12)
        if inferred:
            return inferred.get("champion")
    except Exception:
        pass

    rk = _ROLE_TO_KEY.get(target_role)
    if not rk or not enemy_picks:
        return None
    best = None
    best_score = 0
    for e in enemy_picks:
        es = role_data.get(e, {}).get(rk, 0)
        if es > best_score:
            best_score = es
            best = e
    if best and best_score >= min_score:
        return best
    return None


def _delta_to_bonus(delta: float) -> int:
    if delta >= 5.0:
        return 5
    elif delta >= 3.0:
        return 3
    elif delta >= 1.0:
        return 1
    elif delta > -1.0:
        return 0
    elif delta > -3.0:
        return -1
    elif delta > -5.0:
        return -3
    else:
        return -5


def _bonus_to_reason(bonus: int) -> str:
    return {
        5: "强势克制敌方对位",
        3: "对位优势",
        1: "对位略优",
        0: "对位均势",
        -1: "对位略劣",
        -3: "对位劣势",
        -5: "被敌方明显克制",
    }.get(bonus, "")


def get_lane_bonus(
    champion: str,
    role: str,
    enemy_lane_champion: Optional[str],
    client: Optional[LolalyticsClient] = None,
) -> dict:
    """Get lane matchup bonus (-5 to +5) and reason for a champion."""
    if not enemy_lane_champion:
        return {"lane_bonus": 0, "lane_reason": ""}
    if champion.lower() == enemy_lane_champion.lower():
        return {"lane_bonus": 0, "lane_reason": ""}

    lane = _ROLE_TO_LANE.get(role, "top")
    own_client = False
    if client is None:
        client = LolalyticsClient()
        own_client = True

    try:
        matchup = _local_matchup(champion, enemy_lane_champion, role)
        if matchup is None:
            matchup = client.get_matchup(champion, enemy_lane_champion, lane=lane)
        if matchup is None:
            return {"lane_bonus": 0, "lane_reason": ""}
        delta = matchup.get("delta", 0.0)
        bonus = _delta_to_bonus(delta)
        reason = _bonus_to_reason(bonus)
        return {"lane_bonus": bonus, "lane_reason": reason}
    except Exception:
        return {"lane_bonus": 0, "lane_reason": ""}
