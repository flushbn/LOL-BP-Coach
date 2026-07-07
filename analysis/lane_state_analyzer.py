from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.lane_bonus import _local_matchup
from utils.champion_names import champion_display_name

try:
    from recommendation_engine import TeamAnalyzer
except Exception:
    from core.recommendation_engine import TeamAnalyzer


ROOT = Path(__file__).resolve().parent.parent
ROLE_DATA_PATH = ROOT / "data" / "role_data.json"

ROLE_KEYS = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MID": "MIDDLE",
    "ADC": "BOTTOM",
    "SUPPORT": "UTILITY",
}

ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "BOT": "下路",
    "ADC": "下路",
    "SUPPORT": "辅助",
}


class LaneStateAnalyzer:
    """路线强弱分析器。

    这个模块刻意把“线权优势”和“值得抓”拆开：
    坦克英雄即使对线优势，也可能更适合反蹲、保护和控视野，而不是硬抓。
    """

    def __init__(self):
        self._role_data = self._load_role_data()
        self._team = TeamAnalyzer()

    def analyze(
        self,
        ally_picks: list[str],
        enemy_picks: list[str],
        role_inference: dict[str, Any] | None = None,
    ) -> dict:
        ally_roles = self._assign_roles(ally_picks)
        enemy_roles = self._assign_roles(enemy_picks, role_inference=role_inference)

        lanes: list[dict] = []
        for lane in ("TOP", "JUNGLE", "MID", "BOT"):
            if lane == "JUNGLE":
                item = self._analyze_jungle(ally_roles, enemy_roles)
            elif lane == "BOT":
                item = self._analyze_bot_lane(ally_roles, enemy_roles)
            else:
                item = self._analyze_solo_lane(lane, ally_roles, enemy_roles)
            if item:
                lanes.append(item)

        return {
            "lanes": lanes,
            "summary": self._build_summary(lanes),
            "ally_roles": ally_roles,
            "enemy_roles": enemy_roles,
        }

    def _analyze_solo_lane(self, lane: str, ally_roles: dict, enemy_roles: dict) -> dict | None:
        ally = ally_roles.get(lane)
        enemy = enemy_roles.get(lane)
        if not ally and not enemy:
            return None

        ally_champs = [ally] if ally else []
        enemy_champs = [enemy] if enemy else []
        delta = self._matchup_delta(ally, enemy, lane) if ally and enemy else 0.0
        kill_score = self._kill_potential_score(ally_champs, enemy_champs)
        defense_score = self._defense_value_score(ally_champs, enemy_champs)
        priority, jungle_action = self._priority(delta, kill_score, defense_score)

        return self._lane_payload(
            lane=lane,
            ally=" + ".join(ally_champs),
            enemy=" + ".join(enemy_champs),
            score=delta,
            kill_score=kill_score,
            defense_score=defense_score,
            priority=priority,
            jungle_action=jungle_action,
            reason=self._reason(lane, delta, kill_score, defense_score, ally_champs, enemy_champs),
        )

    def _analyze_bot_lane(self, ally_roles: dict, enemy_roles: dict) -> dict | None:
        ally = [champ for champ in (ally_roles.get("ADC"), ally_roles.get("SUPPORT")) if champ]
        enemy = [champ for champ in (enemy_roles.get("ADC"), enemy_roles.get("SUPPORT")) if champ]
        if not ally and not enemy:
            return None

        deltas = []
        if ally_roles.get("ADC") and enemy_roles.get("ADC"):
            deltas.append(self._matchup_delta(ally_roles["ADC"], enemy_roles["ADC"], "ADC"))
        if ally_roles.get("SUPPORT") and enemy_roles.get("SUPPORT"):
            deltas.append(self._matchup_delta(ally_roles["SUPPORT"], enemy_roles["SUPPORT"], "SUPPORT"))
        delta = sum(deltas) / len(deltas) if deltas else 0.0

        kill_score = self._kill_potential_score(ally, enemy)
        defense_score = self._defense_value_score(ally, enemy)
        priority, jungle_action = self._priority(delta, kill_score, defense_score)

        return self._lane_payload(
            lane="BOT",
            ally=" + ".join(ally),
            enemy=" + ".join(enemy),
            score=delta,
            kill_score=kill_score,
            defense_score=defense_score,
            priority=priority,
            jungle_action=jungle_action,
            reason=self._reason("BOT", delta, kill_score, defense_score, ally, enemy),
        )

    def _analyze_jungle(self, ally_roles: dict, enemy_roles: dict) -> dict | None:
        ally = ally_roles.get("JUNGLE")
        enemy = enemy_roles.get("JUNGLE")
        if not ally and not enemy:
            return None

        ally_dims = self._combined_dims([ally] if ally else [])
        enemy_dims = self._combined_dims([enemy] if enemy else [])
        score = (
            ally_dims.get("earlygame", 0)
            + ally_dims.get("mobility", 0) * 0.5
            + ally_dims.get("pick", 0) * 0.5
            - enemy_dims.get("earlygame", 0)
            - enemy_dims.get("mobility", 0) * 0.5
            - enemy_dims.get("pick", 0) * 0.5
        )

        if score >= 2:
            priority = "控资源路"
            action = "打野节奏占优，优先控河道、反野和入侵视野"
        elif score <= -2:
            priority = "防守路"
            action = "避免野区硬碰硬，优先反蹲、换资源和保护弱侧"
        else:
            priority = "控资源路"
            action = "根据线上状态选择先手支援或控小龙/先锋"

        return self._lane_payload(
            lane="JUNGLE",
            ally=ally or "",
            enemy=enemy or "",
            score=score,
            kill_score=(ally_dims.get("pick", 0) + ally_dims.get("engage", 0)) / 2,
            defense_score=(enemy_dims.get("pick", 0) + enemy_dims.get("earlygame", 0)) / 2,
            priority=priority,
            jungle_action=action,
            reason="打野位主要看前期节奏、机动性和抓人能力，不按普通对线处理。",
        )

    def _lane_payload(
        self,
        lane: str,
        ally: str,
        enemy: str,
        score: float,
        kill_score: float,
        defense_score: float,
        priority: str,
        jungle_action: str,
        reason: str,
    ) -> dict:
        return {
            "lane": lane,
            "label": ROLE_LABELS.get(lane, lane),
            "ally": ally,
            "enemy": enemy,
            "ally_display": self._display_pair(ally),
            "enemy_display": self._display_pair(enemy),
            "score": round(score, 1),
            "state": self._lane_state(score),
            "kill_potential": self._level(kill_score),
            "defense_value": self._level(defense_score),
            "priority": priority,
            "jungle_action": jungle_action,
            "reason": reason,
            "advice": f"{priority}：{jungle_action}",
        }

    def _assign_roles(self, picks: list[str], role_inference: dict[str, Any] | None = None) -> dict:
        assigned: dict[str, str] = {}
        used: set[str] = set()

        if role_inference:
            inferred = []
            for champ in picks:
                probs = role_inference.get(champ, {})
                if not isinstance(probs, dict):
                    continue
                for role, probability in probs.items():
                    normalized = self._normalize_role(role)
                    if normalized:
                        inferred.append((float(probability or 0), normalized, champ))
            for _, role, champ in sorted(inferred, reverse=True):
                if role not in assigned and champ not in used:
                    assigned[role] = champ
                    used.add(champ)

        for role in ("JUNGLE", "ADC", "SUPPORT", "MID", "TOP"):
            if role in assigned:
                continue
            best = ""
            best_score = 0
            for champ in picks:
                if champ in used:
                    continue
                score = self._role_score(champ, role)
                if score > best_score:
                    best = champ
                    best_score = score
            if best and best_score >= 10:
                assigned[role] = best
                used.add(best)
        return assigned

    def _matchup_delta(self, ally: str, enemy: str, role: str) -> float:
        matchup = _local_matchup(ally, enemy, role)
        if not matchup:
            return 0.0
        try:
            return float(matchup.get("delta", 0) or 0)
        except Exception:
            return 0.0

    def _kill_potential_score(self, ally: list[str], enemy: list[str]) -> float:
        ally_dims = self._combined_dims(ally)
        enemy_dims = self._combined_dims(enemy)
        raw = (
            ally_dims.get("cc", 0) * 0.8
            + ally_dims.get("engage", 0) * 0.8
            + ally_dims.get("burst", 0) * 0.7
            + ally_dims.get("pick", 0) * 0.8
            + ally_dims.get("earlygame", 0) * 0.5
            - enemy_dims.get("mobility", 0) * 0.5
            - enemy_dims.get("frontline", 0) * 0.4
        )
        if self._all_tank_or_low_burst(ally):
            raw -= 2.0
        score = self._clamp(raw / max(1, len(ally)), 0, 10)
        if len(ally) == 1 and self._is_solo_tank_low_burst(ally[0]):
            tags = self._tags(ally[0])
            cap = 4.5 if "fighter" in tags else 3.5
            score = min(score, cap)
        return score

    def _defense_value_score(self, ally: list[str], enemy: list[str]) -> float:
        ally_dims = self._combined_dims(ally)
        enemy_dims = self._combined_dims(enemy)
        raw = (
            enemy_dims.get("burst", 0) * 0.7
            + enemy_dims.get("pick", 0) * 0.7
            + enemy_dims.get("earlygame", 0) * 0.5
            + enemy_dims.get("splitpush", 0) * 0.4
            - ally_dims.get("frontline", 0) * 0.3
            - ally_dims.get("mobility", 0) * 0.3
        )
        return self._clamp(raw / max(1, len(enemy)), 0, 10)

    def _combined_dims(self, champions: list[str]) -> dict[str, float]:
        combined: dict[str, float] = {}
        for champ in champions:
            if not champ:
                continue
            dims = self._team._compute_champion_dimensions(champ)
            tags = self._tags(champ)
            if "cc" in tags:
                dims["cc"] = max(dims.get("cc", 0), 7)
            for key, value in dims.items():
                combined[key] = combined.get(key, 0) + float(value)
        return combined

    def _priority(self, delta: float, kill_score: float, defense_score: float) -> tuple[str, str]:
        if delta >= 1 and kill_score >= 6:
            return "主攻路", "可以主动抓，优先扩大线权和塔皮优势"
        if delta >= 1 and kill_score < 4:
            return "防守路", "不建议硬抓，优先反蹲、控视野，防止对方发育"
        if delta <= -2 and defense_score >= 5:
            return "保护路", "需要防止敌方滚雪球，优先反蹲和补防河道"
        if delta <= -2 and defense_score < 5:
            return "放养路", "不宜投入过多资源，优先换资源和帮助强侧"
        if kill_score >= 6:
            return "机会路", "有控制或爆发窗口时可以短线出手"
        return "发育路", "以稳定发育、河道视野和资源交换为主"

    def _reason(
        self,
        lane: str,
        delta: float,
        kill_score: float,
        defense_score: float,
        ally: list[str],
        enemy: list[str],
    ) -> str:
        ally_name = " + ".join(champion_display_name(champ) for champ in ally) or "未知"
        enemy_name = " + ".join(champion_display_name(champ) for champ in enemy) or "未知"
        kill = self._level(kill_score)
        defense = self._level(defense_score)
        if delta >= 1 and kill == "低":
            return f"{ally_name} 对 {enemy_name} 有线权优势，但击杀潜力低，更适合防守反蹲。"
        if delta >= 1:
            return f"{ally_name} 对 {enemy_name} 线权占优，可以围绕该路扩大优势。"
        if delta <= -1 and defense in ("中", "高"):
            return f"{ally_name} 对 {enemy_name} 压力较大，需要注意防抓和河道视野。"
        if kill == "高":
            return f"{ally_name} 对 {enemy_name} 对线接近，但控制/爆发足，有击杀窗口。"
        return f"{ally_name} 对 {enemy_name} 接近均势，优先稳定发育。"

    def _role_score(self, champion: str, role: str) -> int:
        role_key = ROLE_KEYS.get(role)
        if not role_key:
            return 0
        return int((self._role_data.get(champion, {}) or {}).get(role_key, 0) or 0)

    def _tags(self, champion: str) -> set[str]:
        return set(self._team._get_champion(champion).get("tags", []))

    def _all_tank_or_low_burst(self, champions: list[str]) -> bool:
        if not champions:
            return False
        has_tank = False
        for champ in champions:
            tags = self._tags(champ)
            if "burst" in tags or "assassin" in tags or "marksman" in tags:
                return False
            if "tank" in tags or "frontline" in tags:
                has_tank = True
        return has_tank

    def _is_solo_tank_low_burst(self, champion: str) -> bool:
        tags = self._tags(champion)
        if "tank" not in tags and "frontline" not in tags:
            return False
        if "burst" in tags or "assassin" in tags or "marksman" in tags:
            return False
        return True

    def _build_summary(self, lanes: list[dict]) -> list[str]:
        summary: list[str] = []
        main = [lane for lane in lanes if lane.get("priority") == "主攻路"]
        protect = [lane for lane in lanes if lane.get("priority") in ("保护路", "防守路")]
        opportunity = [lane for lane in lanes if lane.get("priority") == "机会路"]

        if main:
            summary.append("优先围绕 " + "、".join(item["label"] for item in main[:2]) + " 扩大优势。")
        if protect:
            summary.append("重点关注 " + "、".join(item["label"] for item in protect[:2]) + " 的反蹲与视野。")
        if opportunity:
            summary.append("机会路有控制/爆发窗口，适合短线支援，不建议长期蹲守。")
        if not summary and lanes:
            summary.append("各路线接近均势，建议优先控河道视野并根据资源刷新调整节奏。")
        return summary[:3]

    @staticmethod
    def _lane_state(score: float) -> str:
        if score >= 5:
            return "大优"
        if score >= 1:
            return "小优"
        if score > -1:
            return "均势"
        if score > -3:
            return "小劣"
        return "劣势"

    @staticmethod
    def _level(score: float) -> str:
        if score >= 6:
            return "高"
        if score >= 3:
            return "中"
        return "低"

    @staticmethod
    def _normalize_role(role: str) -> str:
        mapping = {
            "TOP": "TOP",
            "JUNGLE": "JUNGLE",
            "MID": "MID",
            "MIDDLE": "MID",
            "ADC": "ADC",
            "BOTTOM": "ADC",
            "BOT": "ADC",
            "SUPPORT": "SUPPORT",
            "UTILITY": "SUPPORT",
        }
        return mapping.get(str(role or "").upper(), "")

    @staticmethod
    def _display_pair(text: str) -> str:
        if not text:
            return ""
        return " + ".join(champion_display_name(part.strip()) for part in text.split("+") if part.strip())

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    @staticmethod
    def _load_role_data() -> dict:
        try:
            return json.loads(ROLE_DATA_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
