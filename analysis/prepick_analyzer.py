import sys, json
from utils.champion_names import champion_display_name

class PrepickAnalyzer:
    def __init__(self):
        # Build search index
        self._all_champs = set()
        try:
            from core.role_filter import RoleFilter
            rf = RoleFilter()
            for role in ["Top","Jungle","Mid","ADC","Support"]:
                self._all_champs.update(rf.get_candidates(role))
        except:
            self._all_champs = set()

    def search(self, query: str, max_results=8) -> list:
        q = query.strip().lower()
        if not q: return []
        results = []
        for ch in self._all_champs:
            cn = champion_display_name(ch)
            if q in ch.lower() or q in cn.lower():
                results.append(ch)
        return sorted(results)[:max_results]

    def cn(self, ch): return champion_display_name(ch)

    def analyze(self, champ: str, ally_picks, enemy_picks, target_role, pick_slot=0) -> dict:
        from core.recommendation_engine_v3 import RecommendationEngine
        eng = RecommendationEngine()
        recs = eng.recommend(ally_picks=ally_picks, enemy_picks=enemy_picks,
                             target_role=target_role, pick_slot=pick_slot, top_n=15)

        # Find our champ in results
        entry = None
        rank = 0
        for i, r in enumerate(recs, 1):
            if r["champion"] == champ:
                entry = r; rank = i; break

        if not entry:
            return {"score": 0, "grade": "?", "rank": 0, "pros": [], "cons": [],
                    "recommendation": "未在推荐榜中", "summary": "该英雄不在推荐列表中",
                    "champion_cn": self.cn(champ)}

        score = entry["final_score"]
        if score >= 90: grade = "S"
        elif score >= 80: grade = "A"
        elif score >= 70: grade = "B"
        elif score >= 60: grade = "C"
        else: grade = "D"

        if grade in ("S","A"): rec_text = "推荐选择"
        elif grade == "B": rec_text = "可以选择"
        elif grade == "C": rec_text = "谨慎选择"
        else: rec_text = "不推荐"

        # Pros from tactical + reasons
        pros = []
        tac = entry.get("tactical", {})
        for r in (tac.get("reasons", []) + tac.get("strengths", [])):
            if r not in pros: pros.append(r)

        # Cons: check team needs
        cons = []
        try:
            from core.recommendation_engine import TeamAnalyzer
            ta = TeamAnalyzer()
            analysis = ta.analyze(ally_picks=ally_picks, enemy_picks=enemy_picks)
            ally_scores = analysis["ally"]
            cd = ta._get_champion(champ).get("tags", [])

            needs = {
                ("frontline", 4): ("tank","frontline","bruiser"),
                ("engage", 3): ("engage",),
                ("peel", 4): ("peel","support","shield"),
            }
            for (dim, threshold), tags in needs.items():
                if ally_scores.get(dim, 10) < threshold and not any(t in cd for t in tags):
                    dim_cn = {"frontline":"己方缺前排","engage":"己方缺开团","peel":"己方缺保护"}
                    cons.append(dim_cn.get(dim, ""))

            # Enemy counters
            enemy_tags = []
            for en in enemy_picks:
                enemy_tags.extend(ta._get_champion(en).get("tags", []))
            if enemy_tags.count("cc") + enemy_tags.count("engage") >= 3:
                cons.append("敌方控制较多")

            # Meta warning
            if entry.get("meta_score", 100) < 60:
                cons.append("当前版本表现一般")
        except: pass

        pros = pros[:4]; cons = cons[:4]

        summary_parts = []
        if pros: summary_parts.append("优势:" + pros[0])
        if cons: summary_parts.append("风险:" + cons[0])
        summary = "；".join(summary_parts) if summary_parts else "综合评估"

        return {
            "score": score, "grade": grade, "rank": rank,
            "pros": pros, "cons": cons,
            "recommendation": rec_text, "summary": summary,
            "champion_cn": self.cn(champ)
        }

