from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.build_recommendation import BuildRecommendationEngine
from analysis.data_patch_manager import DataPatchManager
from analysis.lane_strategy_engine import LaneStrategyEngine
from analysis.lolalytics_client import LolalyticsClient
from analysis.rune_recommendation import RuneRecommendationEngine
from utils.champion_assets import champion_key
from utils.champion_names import champion_display_name


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "MIDDLE": "中路",
    "ADC": "射手",
    "BOTTOM": "射手",
    "SUPPORT": "辅助",
    "UTILITY": "辅助",
}
ROLE_TO_LANE = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "middle",
    "ADC": "bottom",
    "SUPPORT": "support",
}
CHAMPION_ROLE_MAP = {
    "top": "TOP",
    "jungle": "JUNGLE",
    "mid": "MID",
    "adc": "ADC",
    "support": "SUPPORT",
}
ROLE_DATA_MAP = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}


class HeroDetailContextBuilder:
    def __init__(self):
        patch = DataPatchManager().get_current_patch()
        self.patch = patch if patch != "unknown" else "16.13"
        self.meta_path = DATA_DIR / self.patch / "meta_data.json"
        self.counter_path = DATA_DIR / self.patch / "counter_data.json"
        self.synergy_path = DATA_DIR / self.patch / "synergy_data.json"
        self.meta = self._load_json(self.meta_path)
        self.counter = self._load_json(self.counter_path)
        self.synergy = self._load_json(self.synergy_path)
        self.champion_data = self._load_json(ROOT / "champion_data.json")
        self.role_data = self._load_json(DATA_DIR / "role_data.json")
        self.lane_strategy = LaneStrategyEngine()
        self.lolalytics = LolalyticsClient(patch=self.patch)
        self.build_engine = BuildRecommendationEngine(self.lolalytics)
        self.rune_engine = RuneRecommendationEngine(self.lolalytics)

    def build(
        self,
        champion: str,
        current_state: dict | None = None,
        recommendation: dict | None = None,
        include_loadout: bool = False,
        include_online: bool = True,
        loadout_payload: dict | None = None,
    ) -> dict[str, Any]:
        key = champion_key(champion)
        state = current_state or {}
        rec = recommendation or {}
        roles = self._roles(key, include_online=include_online)
        selected_role = self._selected_role(state, roles)
        best_role_payload = self._best_meta_payload(key, include_online=include_online)
        enemy_team = [champion_key(item) for item in state.get("enemy", []) or [] if champion_key(item)]
        rune_recommendation = None
        build_recommendation = {}
        if loadout_payload and not loadout_payload.get("error"):
            rune_recommendation = loadout_payload.get("rune")
            build_recommendation = loadout_payload.get("build", {}) or {}
        elif include_loadout:
            rune_recommendation = self.rune_engine.recommend(key, selected_role, enemy_team)
            build_recommendation = self.build_engine.recommend(key, selected_role, enemy_team)

        context = {
            "champion": key,
            "champion_cn": champion_display_name(key),
            "patch": self.patch,
            "roles": [ROLE_LABELS.get(role, role) for role in roles],
            "meta": best_role_payload,
            "recommendation": rec,
            "runes": [rune_recommendation] if rune_recommendation else [],
            "builds": build_recommendation.get("core_build", []) if build_recommendation else [],
            "build_recommendation": build_recommendation,
            "lane_plan": self.lane_strategy.build_plan(key, state, self.champion_data),
            "power_spikes": self._power_spikes(key, best_role_payload),
            "counters": self._counter_summary(key, roles, include_online=include_online),
            "synergies": self._synergy_summary(key, state),
            "quick_mode": not include_online and not include_loadout and not loadout_payload,
        }
        return context

    def _selected_role(self, state: dict, roles: list[str]) -> str:
        role = state.get("role") or state.get("target_role") or ""
        role = str(role).upper()
        if role:
            return role
        return roles[0] if roles else ""

    def _roles(self, champion: str, include_online: bool = True) -> list[str]:
        roles = self.champion_data.get(champion, {}).get("roles", [])
        result = []
        for role in roles:
            normalized = {
                "top": "TOP",
                "jungle": "JUNGLE",
                "mid": "MID",
                "adc": "ADC",
                "support": "SUPPORT",
            }.get(str(role).lower())
            if normalized:
                result.append(normalized)
        if result:
            return result

        role_payloads = self._meta_roles(champion, include_online=include_online)
        return list(role_payloads.keys())[:3]

    def _best_meta_payload(self, champion: str, include_online: bool = True) -> dict:
        roles = self._meta_roles(champion, include_online=include_online)
        if not roles:
            return {}
        return max(
            roles.values(),
            key=lambda item: (self._safe_float(item.get("games", 0)), self._safe_float(item.get("pickrate", 0))),
        )

    def _meta_roles(self, champion: str, include_online: bool = True) -> dict[str, dict]:
        if "champions" in self.meta:
            roles = self.meta.get("champions", {}).get(champion, {}).get("roles", {})
            if roles:
                return roles
            return self._fetch_live_meta_roles(champion) if include_online else {}
        result = {}
        for role, role_data in self.meta.get("roles", {}).items():
            if champion in role_data:
                result[role] = role_data[champion]
        if result:
            return result
        return self._fetch_live_meta_roles(champion) if include_online else {}

    def _runes(self, champion: str, roles: list[str]) -> list[dict]:
        tags = set(self._champion_payload(champion).get("tags", []))
        if "tank" in tags or "frontline" in tags:
            return [{"primary": "坚决", "keystone": "不灭之握", "secondary": "启迪"}]
        if "assassin" in tags:
            return [{"primary": "主宰", "keystone": "电刑", "secondary": "精密"}]
        if "marksman" in tags or "dps" in tags:
            return [{"primary": "精密", "keystone": "致命节奏", "secondary": "启迪"}]
        if "mage" in tags or "ap" in tags:
            return [{"primary": "巫术", "keystone": "奥术彗星", "secondary": "启迪"}]
        if "support" in tags:
            return [{"primary": "巫术", "keystone": "艾黎", "secondary": "坚决"}]
        return [{"primary": "精密", "keystone": "征服者", "secondary": "坚决"}]

    def _builds(self, champion: str, roles: list[str]) -> list[dict]:
        tags = set(self._champion_payload(champion).get("tags", []))
        if "tank" in tags or "frontline" in tags:
            items = ["日炎圣盾", "荆棘之甲", "自然之力"]
        elif "marksman" in tags:
            items = ["无尽之刃", "疾射火炮", "多米尼克领主的致意"]
        elif "mage" in tags or "ap" in tags:
            items = ["卢登的伙伴", "影焰", "灭世者的死亡之帽"]
        elif "assassin" in tags:
            items = ["幽梦之灵", "收集者", "赛瑞尔达的怨恨"]
        elif "support" in tags:
            items = ["月石再生器", "救赎", "米凯尔的祝福"]
        else:
            items = ["三相之力", "斯特拉克的挑战护手", "死亡之舞"]
        return [{"items": items, "note": "基于英雄定位的本地推荐"}]

    def _power_spikes(self, champion: str, meta_payload: dict) -> list[str]:
        tags = set(self._champion_payload(champion).get("tags", []))
        spikes = []
        if "early_game" in tags or "assassin" in tags:
            spikes.append("3-6级：具备第一波主动权。")
        if "engage" in tags or "frontline" in tags:
            spikes.append("6级后：开团和小规模团战能力提升。")
        if "dps" in tags or "marksman" in tags:
            spikes.append("两件套后：持续输出明显成型。")
        if "scaling" in tags or float(meta_payload.get("pickrate", 0) or 0) >= 5:
            spikes.append("中后期：团战容错和输出空间更重要。")
        return spikes or ["一件套后进入稳定作战期。", "中期资源团决定节奏。"]

    def _counter_summary(
        self,
        champion: str,
        roles: list[str] | None = None,
        include_online: bool = True,
    ) -> list[str]:
        pairs = self.counter.get("champions", {}).get(champion, {})
        if not pairs and include_online:
            pairs = self._fetch_live_counters(champion, roles or self._candidate_roles(champion))
        if not pairs:
            return ["暂无本地克制数据，完整对位数据可在已选英雄页后台加载后查看。"]
        rows = sorted(
            pairs.items(),
            key=lambda item: self._safe_float(item[1].get("winrate_delta", item[1].get("delta", 0))),
            reverse=True,
        )
        best = rows[:3]
        worst = sorted(
            pairs.items(),
            key=lambda item: self._safe_float(item[1].get("winrate_delta", item[1].get("delta", 0))),
        )[:2]
        result = []
        for enemy, payload in best:
            delta = self._safe_float(payload.get("winrate_delta", payload.get("delta", 0)))
            score = self._safe_float(payload.get("counter_score", 50))
            result.append(f"优势对位：{champion_display_name(enemy)}（{delta:+.1f}% / 克制分 {score:.1f}）")
        for enemy, payload in worst:
            delta = self._safe_float(payload.get("winrate_delta", payload.get("delta", 0)))
            score = self._safe_float(payload.get("counter_score", 50))
            if delta < -0.5:
                result.append(f"需要小心：{champion_display_name(enemy)}（{delta:+.1f}% / 克制分 {score:.1f}）")
        return result[:5]

    def _synergy_summary(self, champion: str, state: dict | None = None) -> list[str]:
        pairs = self.synergy.get("champions", {}).get(champion, {})
        if not pairs:
            return self._infer_synergy_summary(champion, state or {})
        rows = sorted(
            pairs.items(),
            key=lambda item: self._safe_float(item[1].get("synergy_score", 50)),
            reverse=True,
        )[:3]
        return [
            f"{champion_display_name(ally)}：协同分 {round(self._safe_float(payload.get('synergy_score', 50)), 1)}"
            for ally, payload in rows
        ]

    def _fetch_live_counters(self, champion: str, roles: list[str]) -> dict:
        client = LolalyticsClient(patch=self.patch)
        result: dict[str, dict] = {}
        preferred_roles = self._preferred_roles(champion, roles)
        for role in preferred_roles[:2]:
            lane = ROLE_TO_LANE.get(role)
            if not lane:
                continue
            rows = client.get_counters(champion, lane=lane, tier="emerald") or []
            for row in rows:
                enemy = champion_key(row.get("champion", ""))
                if not enemy or enemy == champion:
                    continue
                delta = self._safe_float(row.get("delta", 0))
                result[enemy] = {
                    "role": role,
                    "winrate_delta": round(delta, 2),
                    "counter_score": round(max(0.0, min(100.0, 50.0 + delta * 5.0)), 2),
                    "games": int(row.get("games", 0) or 0),
                    "source": "lolalytics_live_on_demand",
                }
            if result:
                break
            result.update(self._fetch_matchup_counter_fallback(client, champion, role, lane))
            if result:
                break
        if result:
            self._upsert_counter(champion, result)
        return result

    def _fetch_matchup_counter_fallback(
        self,
        client: LolalyticsClient,
        champion: str,
        role: str,
        lane: str,
    ) -> dict:
        result: dict[str, dict] = {}
        for enemy in self._counter_opponent_pool(champion, role)[:10]:
            matchup = client.get_matchup(champion, enemy, lane=lane, tier="emerald")
            if not matchup:
                continue
            delta = self._safe_float(matchup.get("delta", 0))
            games = int(matchup.get("games", 0) or 0)
            result[enemy] = {
                "role": role,
                "winrate_delta": round(delta, 2),
                "counter_score": round(max(0.0, min(100.0, 50.0 + delta * 5.0)), 2),
                "games": games,
                "source": "lolalytics_matchup_on_demand",
            }
        return result

    def _counter_opponent_pool(self, champion: str, role: str) -> list[str]:
        role_pool = self.meta.get("roles", {}).get(role, {})
        rows = sorted(
            role_pool.items(),
            key=lambda item: (
                self._safe_float(item[1].get("games", 0)),
                self._safe_float(item[1].get("pickrate", 0)),
            ),
            reverse=True,
        )
        return [enemy for enemy, _ in rows if enemy != champion]

    def _preferred_roles(self, champion: str, roles: list[str]) -> list[str]:
        meta_roles = self._meta_roles(champion)
        if meta_roles:
            ordered = sorted(
                meta_roles.items(),
                key=lambda item: (
                    self._safe_float(item[1].get("games", 0)),
                    self._safe_float(item[1].get("pickrate", 0)),
                ),
                reverse=True,
            )
            return [role for role, _ in ordered]
        return roles or self._candidate_roles(champion)

    def _infer_synergy_summary(self, champion: str, state: dict) -> list[str]:
        candidates = self._synergy_candidates(champion, state)
        scored = []
        for ally in candidates:
            if ally == champion:
                continue
            score, reason = self._tag_synergy(champion, ally)
            if score <= 52:
                continue
            scored.append((ally, score + self._meta_bonus(ally), reason))
        scored.sort(key=lambda item: item[1], reverse=True)
        rows = scored[:3]
        if not rows:
            return ["暂无协同数据"]
        inferred_pairs = {
            ally: {
                "synergy_score": round(score, 2),
                "sample": "tag_inferred",
                "reason": reason,
            }
            for ally, score, reason in rows
        }
        self._upsert_synergy(champion, inferred_pairs)
        return [
            f"{champion_display_name(ally)}：{reason}（协同 {round(score, 1)}，标签推断）"
            for ally, score, reason in rows
        ]

    def _synergy_candidates(self, champion: str, state: dict) -> list[str]:
        state_allies = [
            champion_key(item)
            for item in state.get("ally", [])
            if champion_key(item) and champion_key(item) != champion
        ]
        if state_allies:
            return state_allies

        roles = set(self._candidate_roles(champion))
        preferred = {
            "TOP": ["JUNGLE", "MID", "ADC", "SUPPORT"],
            "JUNGLE": ["MID", "SUPPORT", "TOP", "ADC"],
            "MID": ["JUNGLE", "SUPPORT", "TOP", "ADC"],
            "ADC": ["SUPPORT", "JUNGLE", "MID"],
            "SUPPORT": ["ADC", "JUNGLE", "MID"],
        }
        target_roles: list[str] = []
        for role in roles:
            target_roles.extend(preferred.get(role, []))
        target_roles = list(dict.fromkeys(target_roles or ["JUNGLE", "MID", "SUPPORT", "ADC", "TOP"]))

        candidates: list[str] = []
        for role in target_roles:
            for ally in self.meta.get("roles", {}).get(role, {}).keys():
                if ally != champion:
                    candidates.append(ally)
        for ally, payload in self.champion_data.items():
            ally_roles = {
                CHAMPION_ROLE_MAP.get(str(role).lower())
                for role in payload.get("roles", [])
            }
            if ally != champion and ally_roles.intersection(target_roles):
                candidates.append(ally)
        return list(dict.fromkeys(candidates))

    def _tag_synergy(self, champion: str, ally: str) -> tuple[float, str]:
        tags = set(self._champion_payload(champion).get("tags", []))
        ally_tags = set(self._champion_payload(ally).get("tags", []))
        score = 50.0
        reasons: list[tuple[float, str]] = []

        if self._has_any(tags, "engage", "frontline", "tank", "cc") and self._has_any(ally_tags, "burst", "mage", "assassin", "dps", "marksman"):
            reasons.append((10, "先手控制 + 输出跟进"))
        if self._has_any(ally_tags, "engage", "frontline", "tank", "cc") and self._has_any(tags, "burst", "mage", "assassin", "dps", "marksman"):
            reasons.append((10, "控制链 + 爆发衔接"))
        if self._has_any(tags, "frontline", "tank", "fighter") and self._has_any(ally_tags, "marksman", "dps", "scaling"):
            reasons.append((8, "前排吸收 + 后排持续输出"))
        if self._has_any(ally_tags, "frontline", "tank", "fighter") and self._has_any(tags, "marksman", "dps", "scaling"):
            reasons.append((8, "前排保护 + 持续输出"))
        if self._has_any(tags, "support", "protect", "peel") and self._has_any(ally_tags, "marksman", "dps", "assassin"):
            reasons.append((7, "保护核心 + 输出空间"))
        if self._has_any(ally_tags, "support", "protect", "peel") and self._has_any(tags, "marksman", "dps", "assassin"):
            reasons.append((7, "保护核心 + 输出空间"))
        if ("ap" in tags and "ad" in ally_tags) or ("ad" in tags and "ap" in ally_tags):
            reasons.append((5, "伤害类型互补"))
        if self._has_any(tags, "engage", "assassin", "fighter") and self._has_any(ally_tags, "engage", "assassin", "fighter"):
            reasons.append((4, "进场节奏一致"))

        if not reasons:
            return score, "阵容标签一般"
        score += sum(value for value, _ in reasons)
        best_reason = max(reasons, key=lambda item: item[0])[1]
        return min(score, 78.0), best_reason

    def _meta_bonus(self, champion: str) -> float:
        payload = self.meta.get("champions", {}).get(champion, {})
        return min(4.0, self._safe_float(payload.get("best_meta_score", 0)) / 15.0)

    def _upsert_counter(self, champion: str, pairs: dict[str, dict]):
        self.counter.setdefault("patch", self.patch)
        self.counter.setdefault("source", "lolalytics_live_on_demand")
        self.counter.setdefault("champions", {})
        self.counter["champions"][champion] = pairs
        self.counter_path.parent.mkdir(parents=True, exist_ok=True)
        self.counter_path.write_text(json.dumps(self.counter, ensure_ascii=False, indent=2), encoding="utf-8")

    def _upsert_synergy(self, champion: str, pairs: dict[str, dict]):
        self.synergy.setdefault("patch", self.patch)
        self.synergy.setdefault("source", "tag_inferred_on_demand")
        self.synergy.setdefault("champions", {})
        self.synergy["champions"][champion] = pairs
        self.synergy_path.parent.mkdir(parents=True, exist_ok=True)
        self.synergy_path.write_text(json.dumps(self.synergy, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _has_any(tags: set[str], *names: str) -> bool:
        return any(name in tags for name in names)

    def _champion_payload(self, champion: str) -> dict:
        aliases = {
            "FiddleSticks": "Fiddlesticks",
            "Fiddlesticks": "Fiddlesticks",
        }
        return self.champion_data.get(champion) or self.champion_data.get(aliases.get(champion, champion), {})


    def _fetch_live_meta_roles(self, champion: str) -> dict[str, dict]:
        roles = self._candidate_roles(champion)
        client = LolalyticsClient(patch=self.patch)
        result: dict[str, dict] = {}
        for role in roles:
            lane = ROLE_TO_LANE.get(role)
            if not lane:
                continue
            stats = client.get_champion_stats(champion, lane=lane, tier="emerald")
            if not stats:
                continue
            entry = self._meta_entry_from_stats(champion, role, stats)
            result[role] = entry
        if result:
            self._upsert_meta(champion, result)
        return result

    def _candidate_roles(self, champion: str) -> list[str]:
        roles: set[str] = set()
        for role in self.champion_data.get(champion, {}).get("roles", []):
            mapped = CHAMPION_ROLE_MAP.get(str(role).lower())
            if mapped:
                roles.add(mapped)
        for riot_role, pct in self.role_data.get(champion, {}).items():
            mapped = ROLE_DATA_MAP.get(riot_role)
            if mapped and float(pct or 0) >= 10:
                roles.add(mapped)
        if not roles:
            roles.add("MID")
        return sorted(roles)

    def _meta_entry_from_stats(self, champion: str, role: str, stats: dict) -> dict:
        winrate = float(stats.get("winrate", 50.0) or 50.0)
        pickrate = float(stats.get("pickrate", 0.0) or 0.0)
        banrate = float(stats.get("banrate", 0.0) or 0.0)
        games = int(stats.get("games", 0) or 0)
        meta_score = max(0.0, min(100.0, winrate * 0.5 + pickrate * 0.3 + banrate * 0.2))
        return {
            "winrate": round(winrate, 2),
            "pickrate": round(pickrate, 2),
            "banrate": round(banrate, 2),
            "tier": stats.get("tier", "Unknown"),
            "rank": stats.get("rank", 0),
            "games": games,
            "sample_confidence": 1.0 if games >= 1500 else 0.75 if games >= 500 else 0.25 if games else 0.0,
            "meta_score": round(meta_score, 2),
            "champion": champion,
            "display_name": champion,
            "role": role,
            "source": "lolalytics_live_on_demand",
        }

    def _upsert_meta(self, champion: str, role_entries: dict[str, dict]):
        self.meta.setdefault("patch", self.patch)
        self.meta.setdefault("source", "lolalytics_live_full")
        self.meta.setdefault("tier", "emerald")
        self.meta.setdefault("roles", {})
        self.meta.setdefault("champions", {})
        for role, entry in role_entries.items():
            self.meta.setdefault("roles", {}).setdefault(role, {})[champion] = entry
        champ_entry = self.meta.setdefault("champions", {}).setdefault(
            champion,
            {"roles": {}, "best_role": next(iter(role_entries.keys())), "best_meta_score": -1},
        )
        for role, entry in role_entries.items():
            champ_entry.setdefault("roles", {})[role] = entry
            if entry.get("meta_score", 0) >= champ_entry.get("best_meta_score", -1):
                champ_entry["best_role"] = role
                champ_entry["best_meta_score"] = entry.get("meta_score", 0)
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")


    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0
