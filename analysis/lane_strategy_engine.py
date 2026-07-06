from __future__ import annotations

from utils.champion_names import champion_display_name


class LaneStrategyEngine:
    def build_plan(self, champion: str, state: dict, champion_data: dict) -> list[str]:
        enemy = state.get("inferred_lane_opponent") or ""
        enemy_cn = champion_display_name(enemy)
        tags = set(champion_data.get(champion, {}).get("tags", []))

        lines: list[str] = []
        if enemy:
            lines.append(f"优先围绕与 {enemy_cn} 的对位来评估换血和支援。")
        if "poke" in tags or "mage" in tags:
            lines.append("利用技能距离消耗，先保证兵线主动权。")
        if "assassin" in tags:
            lines.append("前期避免无意义换血，关键等级后寻找击杀窗口。")
        if "tank" in tags or "frontline" in tags:
            lines.append("稳住前期发育，团战承担开团和吸收伤害职责。")
        if "engage" in tags:
            lines.append("保留关键控制技能，围绕资源团主动找开团角度。")
        if not lines:
            lines.append("根据敌方阵容选择稳健发育或主动换血。")
        return lines[:4]


