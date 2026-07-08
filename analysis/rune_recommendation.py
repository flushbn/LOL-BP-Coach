from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.lolalytics_client import LolalyticsClient
from utils.champion_assets import champion_key


ROOT = Path(__file__).resolve().parent.parent
ROLE_TO_LANE = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "middle",
    "MIDDLE": "middle",
    "ADC": "bottom",
    "BOTTOM": "bottom",
    "SUPPORT": "support",
    "UTILITY": "support",
}


class RuneRecommendationEngine:
    def __init__(self, client: LolalyticsClient | None = None):
        self.client = client or LolalyticsClient()
        self.champion_data = self._load_json(ROOT / "champion_data.json")

    def recommend(self, champion: str, role: str = "", enemy_team: list[str] | None = None) -> dict[str, Any]:
        key = champion_key(champion)
        lane = ROLE_TO_LANE.get(str(role or "").upper(), str(role or "").lower())
        rows = self.client.get_runes(key, lane=lane, tier="emerald") or []
        if rows:
            row = rows[0]
            return {
                "primary": row.get("primary") or self._infer_tree(row.get("keystone") or row.get("name", "")),
                "keystone": row.get("keystone") or row.get("name", ""),
                "runes": row.get("runes", []),
                "secondary_tree": row.get("secondary_tree", ""),
                "secondary": row.get("secondary", []),
                "stat_shards": row.get("stat_shards") or self._stat_shards(key, role),
                "winrate": row.get("winrate"),
                "pickrate": row.get("pickrate"),
                "games": row.get("games", 0),
                "reason": self._reason(key, row.get("keystone") or row.get("name", "")),
                "source": "lolalytics",
            }
        return self._fallback(key)

    def _fallback(self, champion: str) -> dict[str, Any]:
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        if "tank" in tags or "frontline" in tags:
            return {"primary": "Resolve", "keystone": "Grasp of the Undying", "runes": ["Grasp of the Undying", "Demolish", "Bone Plating", "Overgrowth"], "secondary_tree": "Inspiration", "secondary": ["Magical Footwear", "Cosmic Insight"], "stat_shards": self._stat_shards(champion, ""), "reason": "适合近战换血和边线抗压", "source": "local_fallback"}
        if "assassin" in tags:
            return {"primary": "Domination", "keystone": "Electrocute", "runes": ["Electrocute", "Sudden Impact", "Grisly Mementos", "Treasure Hunter"], "secondary_tree": "Precision", "secondary": ["Triumph", "Coup de Grace"], "stat_shards": self._stat_shards(champion, ""), "reason": "强化爆发和游走滚雪球", "source": "local_fallback"}
        if "marksman" in tags or "dps" in tags:
            return {"primary": "Precision", "keystone": "Lethal Tempo", "runes": ["Lethal Tempo", "Presence of Mind", "Legend: Alacrity", "Cut Down"], "secondary_tree": "Inspiration", "secondary": ["Magical Footwear", "Biscuit Delivery"], "stat_shards": self._stat_shards(champion, ""), "reason": "提升持续输出能力", "source": "local_fallback"}
        if "mage" in tags or "ap" in tags:
            return {"primary": "Sorcery", "keystone": "Arcane Comet", "runes": ["Arcane Comet", "Manaflow Band", "Transcendence", "Scorch"], "secondary_tree": "Domination", "secondary": ["Taste of Blood", "Ultimate Hunter"], "stat_shards": self._stat_shards(champion, ""), "reason": "增强消耗和线上压制", "source": "local_fallback"}
        if "support" in tags or "enchanter" in tags:
            return {"primary": "Sorcery", "keystone": "Summon Aery", "runes": ["Summon Aery", "Manaflow Band", "Transcendence", "Scorch"], "secondary_tree": "Resolve", "secondary": ["Bone Plating", "Revitalize"], "stat_shards": self._stat_shards(champion, ""), "reason": "适合保护和消耗型辅助", "source": "local_fallback"}
        return {"primary": "Precision", "keystone": "Conqueror", "runes": ["Conqueror", "Triumph", "Legend: Alacrity", "Last Stand"], "secondary_tree": "Resolve", "secondary": ["Bone Plating", "Overgrowth"], "stat_shards": self._stat_shards(champion, ""), "reason": "通用持续作战方案", "source": "local_fallback"}

    def _reason(self, champion: str, keystone: str) -> str:
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        if keystone == "Grasp of the Undying":
            return "适合近战换血和边线抗压"
        if keystone in ("Conqueror", "Lethal Tempo"):
            return "适合持续作战和团战输出"
        if keystone in ("Electrocute", "Dark Harvest"):
            return "适合爆发击杀和滚雪球"
        if keystone in ("Summon Aery", "Arcane Comet"):
            return "适合消耗、保护或法术压制"
        if "jungle" in tags:
            return "适合当前版本常规打野节奏"
        return "当前版本常用符文组合"

    @staticmethod
    def _infer_tree(rune_name: str) -> str:
        if rune_name in {"Grasp of the Undying", "Aftershock", "Guardian"}:
            return "Resolve"
        if rune_name in {"Conqueror", "Lethal Tempo", "Press the Attack", "Fleet Footwork"}:
            return "Precision"
        if rune_name in {"Electrocute", "Dark Harvest", "Hail of Blades"}:
            return "Domination"
        if rune_name in {"Summon Aery", "Arcane Comet", "Phase Rush", "Deathfire Touch"}:
            return "Sorcery"
        return ""

    def _stat_shards(self, champion: str, role: str = "") -> list[str]:
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        normalized_role = str(role or "").upper()
        if "marksman" in tags or "dps" in tags:
            return ["Attack Speed", "Adaptive Force", "Health Scaling"]
        if "jungle" in tags or normalized_role == "JUNGLE":
            return ["Attack Speed", "Adaptive Force", "Health Scaling"]
        if "tank" in tags or "frontline" in tags or "support" in tags:
            return ["Ability Haste", "Move Speed", "Health Scaling"]
        if "mage" in tags or "ap" in tags:
            return ["Ability Haste", "Adaptive Force", "Health Scaling"]
        return ["Adaptive Force", "Adaptive Force", "Health Scaling"]

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}
