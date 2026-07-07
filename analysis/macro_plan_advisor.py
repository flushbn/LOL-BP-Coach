from __future__ import annotations

from typing import Any


LANE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "BOT": "下路",
    "ADC": "下路",
    "SUPPORT": "辅助",
}

SIDE_BY_LANE = {
    "TOP": "上半区",
    "MID": "中路",
    "BOT": "下半区",
    "JUNGLE": "野区",
}


class MacroPlanAdvisor:
    """根据路线强弱生成前中期资源与节奏计划。

    V1 只读取已有分析结果，不调用推荐引擎，也不改变英雄推荐排序。
    """

    def build_plan(self, lane_state: dict[str, Any], bilateral: dict[str, Any] | None = None) -> dict:
        lanes = [lane for lane in lane_state.get("lanes", []) if isinstance(lane, dict)]
        bilateral = bilateral or {}

        main_lanes = self._lanes_by_priority(lanes, {"主攻路"})
        protect_lanes = self._lanes_by_priority(lanes, {"保护路", "防守路"})
        opportunity_lanes = self._lanes_by_priority(lanes, {"机会路"})
        weak_lanes = self._lanes_by_state(lanes, {"小劣", "劣势"})

        primary_lane = self._pick_primary_lane(main_lanes, opportunity_lanes, lanes)
        primary_side = SIDE_BY_LANE.get(primary_lane.get("lane", ""), "中路") if primary_lane else "中路"
        weak_side = self._pick_weak_side(protect_lanes, weak_lanes)

        jungle_lane = self._find_lane(lanes, "JUNGLE")
        jungle_state = jungle_lane.get("state", "") if jungle_lane else ""

        objective_plan = self._objective_plan(primary_side, main_lanes, protect_lanes, bilateral)
        early_plan = self._early_plan(primary_lane, primary_side, weak_side, jungle_state)
        mid_plan = self._mid_plan(primary_side, main_lanes, protect_lanes, bilateral)
        risk_alerts = self._risk_alerts(protect_lanes, weak_lanes, bilateral)

        summary = self._summary(primary_lane, primary_side, weak_side, objective_plan)

        return {
            "primary_side": primary_side,
            "primary_lane": self._lane_label(primary_lane) if primary_lane else "",
            "strong_lanes": [self._lane_label(lane) for lane in main_lanes + opportunity_lanes],
            "protect_lanes": [self._lane_label(lane) for lane in protect_lanes],
            "weak_lanes": [self._lane_label(lane) for lane in weak_lanes],
            "jungle_path": self._jungle_path(primary_side, jungle_state),
            "first_5_min": early_plan,
            "minute_5_14": mid_plan,
            "objectives": objective_plan,
            "risk_alerts": risk_alerts,
            "summary": summary,
        }

    def _pick_primary_lane(self, main_lanes: list[dict], opportunity_lanes: list[dict], lanes: list[dict]) -> dict | None:
        candidates = main_lanes or opportunity_lanes
        if candidates:
            return sorted(candidates, key=self._lane_weight, reverse=True)[0]
        non_jungle = [lane for lane in lanes if lane.get("lane") != "JUNGLE"]
        if not non_jungle:
            return None
        return sorted(non_jungle, key=self._lane_weight, reverse=True)[0]

    def _pick_weak_side(self, protect_lanes: list[dict], weak_lanes: list[dict]) -> str:
        candidates = protect_lanes or weak_lanes
        if not candidates:
            return ""
        lane = sorted(candidates, key=self._defense_weight, reverse=True)[0]
        return SIDE_BY_LANE.get(lane.get("lane", ""), lane.get("label", ""))

    def _objective_plan(
        self,
        primary_side: str,
        main_lanes: list[dict],
        protect_lanes: list[dict],
        bilateral: dict[str, Any],
    ) -> list[str]:
        objectives: list[str] = []
        has_bot = any(lane.get("lane") == "BOT" for lane in main_lanes)
        has_top = any(lane.get("lane") == "TOP" for lane in main_lanes)
        protect_top = any(lane.get("lane") == "TOP" for lane in protect_lanes)

        if primary_side == "下半区" or has_bot:
            objectives.append("优先布置小龙视野，利用下路线权控第一条小龙")
        if primary_side == "上半区" or has_top:
            objectives.append("优先控上河道，8分钟前后争夺先锋或逼上路塔皮")
        if primary_side == "中路":
            objectives.append("先控中路线权，再根据河道视野转小龙或先锋")
        if protect_top and not has_top:
            objectives.append("上路以防守眼和反蹲为主，不为低击杀率路线强行换节奏")

        comparison = bilateral.get("comparison", {}) or {}
        if comparison.get("lategame") in ("enemy_advantage", "enemy_big_advantage"):
            objectives.append("敌方后期更强，15-25分钟要主动争夺先锋、小龙和外塔")
        elif comparison.get("lategame") in ("ally_advantage", "ally_big_advantage"):
            objectives.append("己方后期更稳，前期可接受换资源，避免无视野硬接团")

        return self._dedupe(objectives)[:5]

    def _early_plan(self, primary_lane: dict | None, primary_side: str, weak_side: str, jungle_state: str) -> list[str]:
        plans: list[str] = []
        if primary_lane:
            lane_label = self._lane_label(primary_lane)
            if primary_lane.get("priority") == "防守路":
                plans.append(f"前3级不要硬抓{lane_label}，优先做反蹲和河道眼")
            else:
                plans.append(f"前3级观察{lane_label}兵线，线权稳定后再主动支援")
        if jungle_state in ("大优", "小优"):
            plans.append("打野前期可以主动控河蟹，压缩敌方打野活动空间")
        elif jungle_state in ("小劣", "劣势"):
            plans.append("打野前期避免硬拼，优先避战刷野并保护弱侧入口")
        if weak_side:
            plans.append(f"{weak_side}不要贪线，先保证防守眼位和召唤师技能")
        if primary_side == "下半区":
            plans.append("下半区提前落位，避免第一条小龙前被敌方抢视野")
        elif primary_side == "上半区":
            plans.append("上半区提前控河道草，准备先锋前的第一波视野")
        return self._dedupe(plans)[:4]

    def _mid_plan(
        self,
        primary_side: str,
        main_lanes: list[dict],
        protect_lanes: list[dict],
        bilateral: dict[str, Any],
    ) -> list[str]:
        plans: list[str] = []
        if main_lanes:
            plans.append("5-14分钟围绕主攻路推线后转河道，扩大塔皮和资源收益")
        if protect_lanes:
            labels = "、".join(self._lane_label(lane) for lane in protect_lanes[:2])
            plans.append(f"{labels}以反蹲为主，目标是阻止敌方滚雪球，不是强行击杀")
        if primary_side == "下半区":
            plans.append("小龙刷新前30秒集合下河道，优先排眼再开龙")
        elif primary_side == "上半区":
            plans.append("先锋刷新前30秒集合上河道，利用线权先占位置")

        comparison = bilateral.get("comparison", {}) or {}
        if comparison.get("engage") in ("ally_advantage", "ally_big_advantage"):
            plans.append("己方开团更强，资源点可主动逼团")
        if comparison.get("dps") in ("enemy_advantage", "enemy_big_advantage"):
            plans.append("敌方持续输出更强，团战避免拉长，优先秒后排或先拿资源撤退")
        return self._dedupe(plans)[:5]

    def _risk_alerts(self, protect_lanes: list[dict], weak_lanes: list[dict], bilateral: dict[str, Any]) -> list[str]:
        alerts: list[str] = []
        for lane in (protect_lanes + weak_lanes)[:3]:
            alerts.append(f"{self._lane_label(lane)}存在被针对风险，注意反蹲和河道视野")
        comparison = bilateral.get("comparison", {}) or {}
        if comparison.get("burst") in ("enemy_advantage", "enemy_big_advantage"):
            alerts.append("敌方爆发更高，脆皮不要无视野先进入河道")
        if comparison.get("frontline") in ("enemy_advantage", "enemy_big_advantage"):
            alerts.append("敌方前排更硬，避免正面拖成长时间团战")
        return self._dedupe(alerts)[:4]

    def _summary(self, primary_lane: dict | None, primary_side: str, weak_side: str, objectives: list[str]) -> list[str]:
        summary: list[str] = []
        if primary_lane:
            summary.append(f"主节奏围绕{self._lane_label(primary_lane)}和{primary_side}展开。")
        if weak_side:
            summary.append(f"{weak_side}更适合稳住与反蹲，不建议强行投入过多资源。")
        if objectives:
            summary.append(objectives[0])
        return summary[:3]

    def _jungle_path(self, primary_side: str, jungle_state: str) -> str:
        if primary_side == "下半区":
            base = "建议刷野路线向下半区收束，优先保证下河道视野与小龙节奏"
        elif primary_side == "上半区":
            base = "建议刷野路线向上半区收束，优先保证上河道视野与先锋节奏"
        else:
            base = "建议围绕中路线权控双河道，根据资源刷新决定转向"

        if jungle_state in ("小劣", "劣势"):
            return base + "；但前期避免强入侵，先防守换资源"
        if jungle_state in ("小优", "大优"):
            return base + "；打野强势时可以提前入侵布深眼"
        return base

    def _lanes_by_priority(self, lanes: list[dict], priorities: set[str]) -> list[dict]:
        return [lane for lane in lanes if lane.get("priority") in priorities]

    def _lanes_by_state(self, lanes: list[dict], states: set[str]) -> list[dict]:
        return [lane for lane in lanes if lane.get("state") in states and lane.get("lane") != "JUNGLE"]

    def _find_lane(self, lanes: list[dict], lane_id: str) -> dict | None:
        for lane in lanes:
            if lane.get("lane") == lane_id:
                return lane
        return None

    def _lane_weight(self, lane: dict) -> float:
        score = float(lane.get("score", 0) or 0)
        kill_bonus = {"高": 3, "中": 1.5, "低": 0}.get(lane.get("kill_potential"), 0)
        lane_bonus = {"BOT": 1.2, "MID": 1.0, "TOP": 0.8, "JUNGLE": 0.5}.get(lane.get("lane"), 0)
        return score + kill_bonus + lane_bonus

    def _defense_weight(self, lane: dict) -> float:
        score = abs(float(lane.get("score", 0) or 0))
        defense_bonus = {"高": 3, "中": 1.5, "低": 0}.get(lane.get("defense_value"), 0)
        return score + defense_bonus

    def _lane_label(self, lane: dict) -> str:
        return lane.get("label") or LANE_LABELS.get(lane.get("lane"), lane.get("lane", ""))

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result
