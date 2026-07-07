"""双边阵容分析 (Team Comparison V1).

分析己方和敌方阵容的6个维度评分，
支持双方对比和战术建议。

使用 recommendation_engine.TeamAnalyzer 底层引擎。
"""
from recommendation_engine import TeamAnalyzer
from typing import Dict, List, Optional


class BilateralTeamAnalyzer:
    """分析己方和敌方阵容的6个维度，提供双方对比。"""

    # 6个核心维度
    DIMENSIONS = ["frontline", "engage", "peel", "burst", "dps", "lategame"]

    def __init__(self):
        self._ta = TeamAnalyzer()

    def _score_to_grade(self, s: int) -> str:
        if s >= 9: return "S"
        if s >= 8: return "A+"
        if s >= 7: return "A"
        if s >= 6: return "A-"
        if s >= 5: return "B+"
        if s >= 4: return "B"
        if s >= 3: return "B-"
        if s >= 2: return "C+"
        if s >= 1: return "C"
        return "D"

    def _build_grades(self, analysis: dict) -> Dict[str, str]:
        """从 TeamAnalyzer 输出构建等级字典。"""
        grades = {}
        for dim in self.DIMENSIONS:
            raw = analysis.get(dim, 0)
            if isinstance(raw, (int, float)):
                grades[dim] = self._score_to_grade(int(raw))
        return grades

    def _compute_comparison(self, ally_grades: Dict[str, str],
                            enemy_grades: Dict[str, str]) -> Dict[str, str]:
        """比较双方评分，输出 human readable 对比结果。"""
        # 等级转分数用于比较
        grade_order = {"D":0,"C":1,"C+":2,"B-":3,"B":4,"B+":5,"A-":6,"A":7,"A+":8,"S":9}
        comparison = {}
        for dim in self.DIMENSIONS:
            a_val = grade_order.get(ally_grades.get(dim, "D"), 0)
            e_val = grade_order.get(enemy_grades.get(dim, "D"), 0)
            diff = a_val - e_val
            if diff >= 3:
                comparison[dim] = "ally_big_advantage"
            elif diff >= 1:
                comparison[dim] = "ally_advantage"
            elif diff <= -3:
                comparison[dim] = "enemy_big_advantage"
            elif diff <= -1:
                comparison[dim] = "enemy_advantage"
            else:
                comparison[dim] = "even"
        return comparison

    def analyze(self, ally_picks: List[str],
                enemy_picks: List[str]) -> Dict:
        """分析双方阵容，返回己方/敌方评分、对比和原始分数。

        Returns:
            {
                "ally": {dim: grade_str, ...},
                "enemy": {dim: grade_str, ...},
                "comparison": {dim: "ally_advantage"|"enemy_advantage"|"even", ...},
                "ally_scores": {dim: int_score, ...},
                "enemy_scores": {dim: int_score, ...},
            }
        """
        try:
            result = self._ta.analyze(ally_picks=ally_picks, enemy_picks=enemy_picks)
            ally_analysis = result.get("ally", {})
            enemy_analysis = result.get("enemy", {})

            ally_grades = self._build_grades(ally_analysis)
            enemy_grades = self._build_grades(enemy_analysis)
            comparison = self._compute_comparison(ally_grades, enemy_grades)

            return {
                "ally": ally_grades,
                "enemy": enemy_grades,
                "comparison": comparison,
                "ally_scores": {k: ally_analysis.get(k, 0) for k in self.DIMENSIONS},
                "enemy_scores": {k: enemy_analysis.get(k, 0) for k in self.DIMENSIONS},
            }
        except Exception:
            return {
                "ally": {}, "enemy": {}, "comparison": {},
                "ally_scores": {}, "enemy_scores": {},
            }
