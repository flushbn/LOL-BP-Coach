import sys, json
from core.recommendation_engine import TeamAnalyzer
from typing import Dict, List

class TeamGradeAnalyzer:
    def __init__(self):
        self.ta = TeamAnalyzer()

    def _score_to_grade(self, s: int) -> str:
        # s is 0-10 from TeamAnalyzer
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

    def grade(self, analysis: dict) -> dict:
        dims = ["frontline","engage","peel","cc","damage","scaling"]
        # Map from TeamAnalyzer output keys
        key_map = {
            "frontline": "frontline",
            "engage": "engage",
            "peel": "peel",
            "poke": "poke",
            "burst": "burst",
            "dps": "dps",
            "teamfight": "teamfight",
            "pick": "pick",
            "splitpush": "splitpush",
            "earlygame": "earlygame",
            "lategame": "lategame"
        }
        # For the coach panel, use 6 key dimensions
        dim_config = [
            ("frontline", "前排"),
            ("engage", "开团"),
            ("peel", "保护"),
            ("burst", "爆发"),
            ("dps", "持续输出"),
            ("lategame", "后期")
        ]
        result = {}
        for key, label in dim_config:
            raw = analysis.get(key, 0)
            if isinstance(raw, (int, float)):
                result[key] = {
                    "score": int(raw),
                    "grade": self._score_to_grade(int(raw)),
                    "label": label
                }
        return result

    def __call__(self, analysis: dict) -> dict:
        return self.grade(analysis)

