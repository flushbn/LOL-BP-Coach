"""Lane Bonus V1 — Convert Lolalytics matchup delta to a -5~+5 bonus."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from analysis.lolalytics_client import LolalyticsClient
from analysis.role_inference_engine import RoleInferenceEngine
from utils.champion_names import canonical_champion_key

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
                _LOCAL_COUNTER_CACHE = {
                    "champions": raw.get("champions", raw),
                    "role_matchups": raw.get("role_matchups", {}),
                }
                return _LOCAL_COUNTER_CACHE
        except Exception:
            continue
    _LOCAL_COUNTER_CACHE = {}
    return _LOCAL_COUNTER_CACHE


def _lookup_key(data: dict, name: str) -> Optional[str]:
    name = canonical_champion_key(name)
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
    expected_role = _ROLE_TO_COUNTER_ROLE.get(role)
    role_matchups = data.get("role_matchups", {}) if isinstance(data, dict) else {}
    role_data = role_matchups.get(expected_role, {}) if expected_role else {}
    source_data = role_data or data.get("champions", data)
    champion_key = _lookup_key(source_data, champion)
    if not champion_key:
        return None

    opponents = source_data.get(champion_key, {}) or {}
    opponent_key = _lookup_key(opponents, opponent)
    if not opponent_key:
        return None

    payload = opponents.get(opponent_key)
    if not isinstance(payload, dict):
        return None

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


def _sample_confidence(games: int) -> float:
    if games <= 0:
        return 0.4
    if games < 500:
        return 0.4 + games / 500 * 0.4
    if games < 1500:
        return 0.8
    return 1.0


def _delta_to_bonus(delta: float, games: int = 0) -> int:
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


def _apply_sample_confidence(bonus: int, games: int) -> int:
    if bonus == 0 or games >= 500:
        return bonus
    adjusted = round(abs(bonus) * _sample_confidence(games))
    return (1 if bonus > 0 else -1) * max(1, adjusted)


def _bonus_to_reason(bonus: int) -> str:
    return {
        5: "强势克制敌方对位",
        4: "强势对位优势",
        3: "对位优势",
        2: "对位优势",
        1: "对位略优",
        0: "对位均势",
        -1: "对位略劣",
        -2: "对位劣势",
        -3: "对位劣势",
        -4: "明显对位劣势",
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
        games = int(matchup.get("games", 0) or 0)
        bonus = _apply_sample_confidence(_delta_to_bonus(delta, games), games)
        reason = _bonus_to_reason(bonus)
        if games < 500 and reason:
            reason = f"{reason}（样本待验证）"
        return {"lane_bonus": bonus, "lane_reason": reason}
    except Exception:
        return {"lane_bonus": 0, "lane_reason": ""}
