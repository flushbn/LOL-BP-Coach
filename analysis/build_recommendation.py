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

AD_TAGS = {"marksman", "ad", "fighter", "assassin"}
AP_TAGS = {"mage", "ap", "enchanter"}
TANK_TAGS = {"tank", "frontline"}


class BuildRecommendationEngine:
    def __init__(self, client: LolalyticsClient | None = None):
        self.client = client or LolalyticsClient()
        self.champion_data = self._load_json(ROOT / "champion_data.json")

    def recommend(self, champion: str, role: str = "", enemy_team: list[str] | None = None) -> dict[str, Any]:
        key = champion_key(champion)
        lane = ROLE_TO_LANE.get(str(role or "").upper(), str(role or "").lower())
        enemy_team = enemy_team or []
        item_paths = self.client.get_item_paths(key, lane=lane, tier="emerald") or {}
        online_builds = [] if item_paths else (self.client.get_builds(key, lane=lane, tier="emerald") or [])

        core_build = self._core_from_item_paths(item_paths, key)
        scored_builds = self._score_core_builds(online_builds, key)
        seen = {tuple(row.get("items", [])) for row in core_build}
        core_build.extend(row for row in scored_builds if tuple(row.get("items", [])) not in seen)
        core_build = core_build[:3]
        if not core_build:
            core_build = self._fallback_core_build(key)

        situational = self._situational_items(key, enemy_team)
        starting_items = item_paths.get("starting_items", []) if isinstance(item_paths, dict) else []
        item_path = self._format_item_path(item_paths)

        return {
            "champion": key,
            "role": role,
            "starting_items": [item.get("name", "") for item in starting_items if item.get("name")],
            "core_build": core_build,
            "item_path": item_path,
            "situational": situational,
            "source": "lolalytics" if online_builds else "local_fallback",
        }

    def _core_from_item_paths(self, item_paths: dict, champion: str) -> list[dict]:
        if not isinstance(item_paths, dict):
            return []
        core_items = item_paths.get("core_build", []) or []
        names = [item.get("name", "") for item in core_items if item.get("name")]
        if not names:
            return []
        winrates = [self._safe_float(item.get("winrate"), 0.0) for item in core_items if item.get("winrate") is not None]
        games_values = [int(item.get("games", 0) or 0) for item in core_items]
        games = max(games_values) if games_values else 0
        winrate = max(winrates) if winrates else None
        sample_score = self._sample_score(games)
        fit_bonus = self._tag_fit_bonus(champion, names)
        score = (winrate or 50.0) * 0.5 + sample_score * 0.2 + fit_bonus * 0.1
        return [{
            "items": names[:3],
            "winrate": round(winrate, 2) if winrate else None,
            "pickrate": None,
            "games": games,
            "build_score": round(score, 2),
            "reason": "Lolalytics 当前版本核心三件套",
        }]

    def _score_core_builds(self, builds: list[dict], champion: str) -> list[dict]:
        rows = []
        for build in builds:
            items = [item for item in build.get("items", []) if item]
            if not items:
                continue
            winrate = self._safe_float(build.get("winrate"), 50.0)
            pickrate = self._safe_float(build.get("pickrate"), 0.0)
            games = int(build.get("games", 0) or 0)
            sample_score = self._sample_score(games)
            situational_bonus = self._tag_fit_bonus(champion, items)
            score = winrate * 0.5 + pickrate * 0.2 + sample_score * 0.2 + situational_bonus * 0.1
            if games and games < 500:
                score *= 0.82
            rows.append({
                "items": items[:3],
                "winrate": round(winrate, 2) if winrate else None,
                "pickrate": round(pickrate, 2) if pickrate else None,
                "games": games,
                "build_score": round(score, 2),
                "reason": "高胜率常规方案" if games >= 1000 else "样本偏少，已降权参考",
            })
        rows.sort(key=lambda item: (item["build_score"], item.get("games", 0)), reverse=True)
        return rows[:3]

    def _format_item_path(self, item_paths: dict) -> dict:
        if not isinstance(item_paths, dict):
            return {}
        return {
            "first_item": self._names(item_paths.get("core_build", [])[:1]),
            "second_item": self._names(item_paths.get("core_build", [])[1:2]),
            "third_item": self._names(item_paths.get("core_build", [])[2:3]),
            "item_4_options": self._names(item_paths.get("item_4_options", [])[:3]),
            "item_5_options": self._names(item_paths.get("item_5_options", [])[:3]),
            "item_6_options": self._names(item_paths.get("item_6_options", [])[:3]),
        }

    def _situational_items(self, champion: str, enemy_team: list[str]) -> list[dict]:
        profile = self._enemy_damage_profile(enemy_team)
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        rows: list[dict] = []
        if profile["ad"] >= 3:
            rows.append({
                "condition": "enemy_ad_high",
                "items": ["Thornmail", "Frozen Heart", "Randuin's Omen"] if self._is_tank(tags) else ["Plated Steelcaps", "Death's Dance", "Guardian Angel"],
                "reason": "敌方物理伤害偏多，护甲装备优先",
            })
        if profile["ap"] >= 3:
            rows.append({
                "condition": "enemy_ap_high",
                "items": ["Kaenic Rookern", "Force of Nature", "Spirit Visage"] if self._is_tank(tags) else ["Mercury's Treads", "Maw of Malmortius", "Wit's End"],
                "reason": "敌方法术伤害偏多，魔抗装备优先",
            })
        if profile["burst"] >= 2:
            rows.append({
                "condition": "enemy_burst_high",
                "items": ["Zhonya's Hourglass", "Sterak's Gage", "Guardian Angel"],
                "reason": "敌方爆发较高，优先生存与容错",
            })
        if not rows:
            rows.append({
                "condition": "standard",
                "items": self._standard_situational(tags),
                "reason": "敌方伤害结构均衡，按常规核心装过渡",
            })
        return rows[:3]

    def _fallback_core_build(self, champion: str) -> list[dict]:
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        if self._is_tank(tags):
            items = ["Sunfire Aegis", "Thornmail", "Kaenic Rookern"]
        elif "marksman" in tags or "dps" in tags:
            items = ["Infinity Edge", "Rapid Firecannon", "Lord Dominik's Regards"]
        elif "mage" in tags or "ap" in tags:
            items = ["Luden's Companion", "Shadowflame", "Rabadon's Deathcap"]
        elif "assassin" in tags:
            items = ["Youmuu's Ghostblade", "The Collector", "Serylda's Grudge"]
        elif "support" in tags or "enchanter" in tags:
            items = ["Moonstone Renewer", "Redemption", "Mikael's Blessing"]
        else:
            items = ["Trinity Force", "Sterak's Gage", "Death's Dance"]
        return [{
            "items": items,
            "winrate": None,
            "pickrate": None,
            "games": 0,
            "build_score": 50.0,
            "reason": "本地定位兜底方案",
        }]

    def _enemy_damage_profile(self, enemy_team: list[str]) -> dict[str, int]:
        profile = {"ad": 0, "ap": 0, "burst": 0}
        for enemy in enemy_team:
            tags = set(self.champion_data.get(champion_key(enemy), {}).get("tags", []))
            if tags.intersection(AD_TAGS):
                profile["ad"] += 1
            if tags.intersection(AP_TAGS):
                profile["ap"] += 1
            if "burst" in tags or "assassin" in tags:
                profile["burst"] += 1
        return profile

    def _tag_fit_bonus(self, champion: str, items: list[str]) -> float:
        tags = set(self.champion_data.get(champion, {}).get("tags", []))
        text = " ".join(items).lower()
        bonus = 50.0
        if self._is_tank(tags) and any(word in text for word in ("sunfire", "thornmail", "frozen", "kaenic", "randuin")):
            bonus += 20
        if ("marksman" in tags or "dps" in tags) and any(word in text for word in ("infinity", "rapid", "dominik", "kraken")):
            bonus += 20
        if ("mage" in tags or "ap" in tags) and any(word in text for word in ("luden", "shadowflame", "rabadon", "zhonya")):
            bonus += 20
        if "assassin" in tags and any(word in text for word in ("youmuu", "collector", "serylda", "opportunity")):
            bonus += 20
        return min(100.0, bonus)

    @staticmethod
    def _sample_score(games: int) -> float:
        if games > 50000: return 100
        if games > 20000: return 85
        if games > 10000: return 70
        if games > 5000: return 60
        if games > 1000: return 55
        return 45

    @staticmethod
    def _safe_float(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _names(items: list[dict]) -> list[str]:
        return [item.get("name", "") for item in items if item.get("name")]

    @staticmethod
    def _is_tank(tags: set[str]) -> bool:
        return bool(tags.intersection(TANK_TAGS))

    @staticmethod
    def _standard_situational(tags: set[str]) -> list[str]:
        if tags.intersection(TANK_TAGS):
            return ["Thornmail", "Kaenic Rookern", "Jak'Sho, The Protean"]
        if "marksman" in tags:
            return ["Guardian Angel", "Lord Dominik's Regards", "Mercurial Scimitar"]
        if "mage" in tags or "ap" in tags:
            return ["Zhonya's Hourglass", "Void Staff", "Banshee's Veil"]
        return ["Guardian Angel", "Death's Dance", "Maw of Malmortius"]

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}
