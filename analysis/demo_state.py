from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.coach_advisor import CoachAdvisor
from analysis.lane_recommendation import LaneRecommendation
from analysis.lane_state_analyzer import LaneStateAnalyzer
from analysis.role_inference_engine import RoleInferenceEngine
from analysis.team_analyzer import BilateralTeamAnalyzer
from recommendation_engine_v3 import RecommendationEngine


LIVE_STATE_PATH = ROOT / "data" / "live_state.json"
LIVE_DRAFT_PATH = ROOT / "data" / "live_draft.json"

DEMO_ALLY = ["Malphite", "LeeSin", "Ahri", "Jhin", "Leona"]
DEMO_ENEMY = ["Yasuo", "JarvanIV", "Zed", "Kaisa", "Nautilus"]
DEMO_BANS = ["Darius", "Draven", "Milio", "Lulu", "Poppy", "Akali"]
DEMO_ROLE = "TOP"


def build_demo_state() -> dict:
    """Build a complete draft state for UI testing."""
    now = int(time.time())
    ally = list(DEMO_ALLY)
    enemy = list(DEMO_ENEMY)
    bans = list(DEMO_BANS)
    role = DEMO_ROLE

    recommendations = _build_recommendations(ally, enemy, bans, role)
    role_inference = _build_role_inference(enemy)
    lane_recommendations, inferred_lane_opponent = _build_lane_recommendations(role, enemy)
    coach = _build_coach(ally, enemy, role_inference)

    return {
        "timestamp": now,
        "role": role,
        "target_role": role,
        "ally": ally,
        "enemy": enemy,
        "bans": bans,
        "recommendations": recommendations,
        "lane_recommendations": lane_recommendations,
        "role_inference": role_inference,
        "inferred_lane_opponent": inferred_lane_opponent,
        "coach": coach,
        "prepick": {},
        "recognition": {
            "phase": "demo",
            "message": "演示阵容已载入",
            "ally_count": len(ally),
            "enemy_count": len(enemy),
            "ban_count": len(bans),
            "last_scan_at": now,
            "recommendation_status": "ready",
        },
    }


def write_demo_state() -> dict:
    state = build_demo_state()
    LIVE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    LIVE_STATE_PATH.write_text(payload, encoding="utf-8")
    LIVE_DRAFT_PATH.write_text(payload, encoding="utf-8")
    return state


def _build_recommendations(ally: list[str], enemy: list[str], bans: list[str], role: str) -> list[dict]:
    try:
        engine = RecommendationEngine()
        excluded = list(dict.fromkeys(ally + enemy + bans))
        return engine.recommend(
            ally_picks=ally,
            enemy_picks=enemy,
            bans=excluded,
            target_role=role,
            top_n=10,
        )
    except Exception:
        return [
            {
                "champion": "Rammus",
                "champion_cn": "拉莫斯",
                "final_score": 82,
                "lane_bonus": 3,
                "comfort_bonus": 0,
                "reasons": ["演示数据", "克制物理突进"],
                "data_sources_confidence": {"meta": "high", "counter": "high", "synergy": "low"},
            },
            {
                "champion": "Ornn",
                "champion_cn": "奥恩",
                "final_score": 79,
                "lane_bonus": 1,
                "comfort_bonus": 0,
                "reasons": ["演示数据", "补充前排和开团"],
                "data_sources_confidence": {"meta": "high", "counter": "high", "synergy": "low"},
            },
        ]


def _build_role_inference(enemy: list[str]) -> dict:
    try:
        return RoleInferenceEngine().infer_roles(enemy)
    except Exception:
        return {
            "Yasuo": {"MID": 0.65, "TOP": 0.25, "ADC": 0.10},
            "JarvanIV": {"JUNGLE": 0.95},
            "Zed": {"MID": 0.95},
            "Kaisa": {"ADC": 0.98},
            "Nautilus": {"SUPPORT": 0.95},
        }


def _build_lane_recommendations(role: str, enemy: list[str]) -> tuple[list[dict], str]:
    try:
        bundle = LaneRecommendation().get_recommendations_for_draft(
            role=role,
            enemy_picks=enemy,
            top_n=10,
        )
        return bundle.get("recommendations", []) or [], bundle.get("opponent", "") or ""
    except Exception:
        return [
            {"champion": "Malphite", "opponent": "Yasuo", "lane_score": 89, "delta": 4.7, "games": 42000},
            {"champion": "Rammus", "opponent": "Yasuo", "lane_score": 86, "delta": 4.1, "games": 18000},
            {"champion": "Poppy", "opponent": "Yasuo", "lane_score": 84, "delta": 3.8, "games": 22000},
        ], "Yasuo"


def _build_coach(ally: list[str], enemy: list[str], role_inference: dict) -> dict:
    try:
        bilateral = BilateralTeamAnalyzer().analyze(ally_picks=ally, enemy_picks=enemy)
        ally_grades = {
            key: {"score": bilateral.get("ally_scores", {}).get(key, 0)}
            for key in ["frontline", "engage", "peel", "burst", "dps", "lategame"]
        }
        combined = CoachAdvisor().combined_advise(ally_grades, bilateral)
        lane_state = LaneStateAnalyzer().analyze(
            ally_picks=ally,
            enemy_picks=enemy,
            role_inference=role_inference,
        )
        dim_map = {
            "frontline": "frontline",
            "engage": "engage",
            "peel": "protect",
            "burst": "burst",
            "dps": "dps",
            "lategame": "late",
        }
        return {
            "ally": {label: bilateral.get("ally", {}).get(key, "") for key, label in dim_map.items()},
            "enemy": {label: bilateral.get("enemy", {}).get(key, "") for key, label in dim_map.items()},
            "comparison": bilateral.get("comparison", {}),
            "advice": "\n".join(combined.get("advice", [])[:5]),
            "lane_state": lane_state,
        }
    except Exception:
        return {
            "ally": {"frontline": "A", "engage": "A", "protect": "B", "burst": "B", "dps": "A", "late": "B"},
            "enemy": {"frontline": "B", "engage": "A", "protect": "B", "burst": "A", "dps": "A", "late": "B"},
            "comparison": {},
            "advice": "中路与下路可主动找机会\n上路优先反蹲，防止亚索发育",
            "lane_state": LaneStateAnalyzer().analyze(ally, enemy, role_inference),
        }


if __name__ == "__main__":
    write_demo_state()
    print(f"Demo state written: {LIVE_STATE_PATH}")
