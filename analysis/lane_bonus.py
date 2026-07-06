"""Lane Bonus V1 — Convert Lolalytics matchup delta to a -5~+5 bonus."""

from typing import Dict, List, Optional
from analysis.lolalytics_client import LolalyticsClient
from analysis.role_inference_engine import RoleInferenceEngine


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
        matchup = client.get_matchup(champion, enemy_lane_champion, lane=lane)
        if matchup is None:
            return {"lane_bonus": 0, "lane_reason": ""}
        delta = matchup.get("delta", 0.0)
        bonus = _delta_to_bonus(delta)
        reason = _bonus_to_reason(bonus)
        return {"lane_bonus": bonus, "lane_reason": reason}
    except Exception:
        return {"lane_bonus": 0, "lane_reason": ""}

