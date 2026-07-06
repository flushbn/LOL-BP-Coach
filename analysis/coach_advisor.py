"""战术顾问 V2 (Team Comparison V1).

双边战术分析：
1. 己方单边评估（保留）
2. 敌方单边评估（新增）
3. 双方对比战术建议（新增）
"""
from typing import List, Dict, Optional

class CoachAdvisor:
    """战术顾问 - 支持单边和双边建议。"""

    def __init__(self):
        # 单边规则（保持兼容）
        self._advice_rules = [
            ("frontline", lambda s: s < 3, "阵容缺少可靠前排", 3),
            ("frontline", lambda s: s <= 1, "前排极度不足，对线团战均将劣势", 5),
            ("frontline", lambda s: s >= 7, "前排质量优秀，团战站位优势", 2),
            ("engage", lambda s: s < 2, "缺少稳定开团手段", 3),
            ("engage", lambda s: s <= 0, "完全无开团能力，建议补充先手英雄", 5),
            ("engage", lambda s: s >= 7, "开团能力极强，主动团战优势", 2),
            ("peel", lambda s: s < 3, "后排保护能力不足", 3),
            ("peel", lambda s: s <= 1, "后排完全暴露，刺客阵容容易切入", 5),
            ("peel", lambda s: s >= 7, "保护能力出色，后排生存优秀", 1),
            ("burst", lambda s: s >= 7, "爆发伤害极高，适合快速击杀", 2),
            ("burst", lambda s: s < 2, "爆发能力偏低，缺少瞬间击杀手段", 3),
            ("dps", lambda s: s >= 7, "持续输出能力强，打坦优秀", 2),
            ("dps", lambda s: s < 2, "持续输出严重不足", 4),
            ("lategame", lambda s: s >= 7, "后期团战能力优秀", 1),
            ("lategame", lambda s: s >= 5, "后期团战有竞争力", 1),
            ("lategame", lambda s: s < 3, "后期强度偏低，建议速战速决", 3),
        ]

        # 新增双边对比规则
        self._bilateral_rules = [
            # 场景1: 我方中期强，敌方后期强
            ("ally_early_vs_enemy_late", lambda b: (
                self._dim(b, "ally_scores", "earlygame", 6)
                and self._dim(b, "enemy_scores", "lategame", 6)
            ), "建议在15-25分钟主动争夺资源，避免拖入后期", 5),

            # 场景2: 我方后期强，敌方后期弱
            ("ally_late_vs_enemy_weak_late", lambda b: (
                self._dim(b, "ally_scores", "lategame", 6)
                and self._dim(b, "enemy_scores", "lategame", 4)
            ), "后期团战优势明显，前期稳发育即可", 4),

            # 场景3: 我方团战强，敌方单带强
            ("ally_teamfight_vs_enemy_split", lambda b: (
                self._dim(b, "ally_scores", "teamfight", 6)
                and self._dim(b, "enemy_scores", "splitpush", 6)
            ), "建议抱团推进，避免边路单独接战", 5),

            # 场景4: 敌方前排不足
            ("enemy_weak_frontline", lambda b: (
                self._dim(b, "enemy_scores", "frontline", 3)
            ), "团战优先集火后排，敌方前排难以抵挡", 4),

            # 场景5: 敌方缺开团
            ("enemy_weak_engage", lambda b: (
                self._dim(b, "enemy_scores", "engage", 2)
            ), "控制视野并逼团，敌方主动开团能力有限", 4),

            # 场景6: 我方开团强
            ("ally_strong_engage", lambda b: (
                self._dim(b, "ally_scores", "engage", 7)
                and not self._dim(b, "enemy_scores", "peel", 6)
            ), "我方开团优势，主动寻找机会先手开团", 3),

            # 场景7: 敌方多刺客（我方保护弱）
            ("enemy_assassin_vs_weak_peel", lambda b: (
                self._dim(b, "enemy_scores", "burst", 7)
                and self._dim(b, "ally_scores", "peel", 4)
            ), "后排注意站位，优先保护关键输出位", 4),

            # 场景8: 双方都后期强
            ("both_strong_late", lambda b: (
                self._dim(b, "ally_scores", "lategame", 6)
                and self._dim(b, "enemy_scores", "lategame", 6)
            ), "后期团战关键，建议早做准备争夺龙魂", 3),

            # 场景9: 我方前排优势
            ("ally_frontline_advantage", lambda b: (
                self._dim(b, "ally_scores", "frontline", 7)
                and self._dim(b, "enemy_scores", "frontline", 4)
            ), "前排优势明显，团战站位可以更加激进", 3),

            # 场景10: 对方DPS不足
            ("enemy_weak_dps", lambda b: (
                self._dim(b, "enemy_scores", "dps", 4)
            ), "对方持续输出能力弱，团战可考虑拖长战斗时间", 3),
        ]

    @staticmethod
    def _dim(b: dict, side: str, key: str, threshold: int) -> bool:
        """检查某侧某维度的分数是否达到阈值。"""
        scores = b.get(side, {})
        val = scores.get(key, 0)
        return isinstance(val, (int, float)) and val >= threshold

    def advise(self, grades: dict) -> List[str]:
        """单边建议（保持接口兼容）。"""
        candidates = []
        for dim, cond, msg, priority in self._advice_rules:
            entry = grades.get(dim)
            if entry and cond(entry.get("score", 0)):
                candidates.append((priority, msg))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in candidates[:5]]

    def bilateral_advise(self, bilateral: dict) -> List[str]:
        """双边战术建议。

        Args:
            bilateral: BilateralTeamAnalyzer.analyze() 的返回值
        """
        candidates = []
        for rule_id, cond, msg, priority in self._bilateral_rules:
            try:
                if cond(bilateral):
                    candidates.append((priority, msg))
            except Exception:
                continue
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in candidates[:5]]

    def combined_advise(self, ally_grades: dict,
                        bilateral: dict) -> dict:
        """综合建议：单边 + 双边。

        Returns:
            {"ally": [...], "enemy": [...], "advice": [...]}
        """
        ally_advice = self.advise(ally_grades)
        bilateral_advice = self.bilateral_advise(bilateral)
        # 合并，去重，按优先级排序
        seen = set()
        combined = []
        # 先双边，再单边
        for msg in bilateral_advice + ally_advice:
            if msg not in seen:
                seen.add(msg)
                combined.append(msg)
        return {
            "ally": ally_advice,
            "bilateral": bilateral_advice,
            "advice": combined[:5],
        }

