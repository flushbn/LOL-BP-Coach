import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TacticalAnalyzer:
    def __init__(self):
        # Load champion tags from champion_data.json
        self._cd = {}
        try:
            with open(ROOT / "champion_data.json","r",encoding="utf-8") as f:
                self._cd = json.load(f)
        except: pass
        # Load tactical rules
        self._tr = {}
        try:
            with open(ROOT / "data" / "tactical_rules.json","r",encoding="utf-8") as f:
                self._tr = json.load(f)
        except: self._tr = {}
        # Tag groups for classification
        self._frontline_tags = {"frontline","tank","bruiser"}
        self._engage_tags = {"engage","initiator"}
        self._peel_tags = {"peel","disengage","support","shield","heal"}
        self._damage_tags = {"dps","assassin","burst","mage","ap"}
        self._antidash_tags = {"antidash","cc"}
        self._teamfight_tags = {"teamfight","aoe","wombo"}
        self._assassin_tags = {"assassin","dive"}

    def _tags(self, champ):
        cd_entry = self._cd.get(champ,{})
        cd_tags = set(cd_entry.get("tags",[]))
        tr_tags = set(self._tr.get(champ,{}).get("tags",[]))
        return cd_tags | tr_tags

    def _has(self, champ, group):
        return bool(self._tags(champ) & group)

    def _team_score(self, ally_picks, dim):
        from core.recommendation_engine import TeamAnalyzer
        try:
            ta = TeamAnalyzer()
            a = ta.analyze(ally_picks=ally_picks, enemy_picks=[])
            return a["ally"].get(dim, 10)
        except: return 10

    def _count_enemy(self, enemy_picks, group):
        return sum(1 for e in enemy_picks if self._has(e, group))

    def analyze(self, ally_picks, enemy_picks, champ) -> dict:
        reasons = []
        strengths = []
        warnings = []

        # Part C: Team needs
        frontline = self._team_score(ally_picks, "frontline")
        engage = self._team_score(ally_picks, "engage")
        peel = self._team_score(ally_picks, "peel")
        burst = self._team_score(ally_picks, "burst")
        dps = self._team_score(ally_picks, "dps")

        if frontline < 6 and self._has(champ, self._frontline_tags):
            reasons.append("补充阵容前排")
        if engage < 6 and self._has(champ, self._engage_tags):
            reasons.append("提供稳定开团能力")
        if peel < 6 and self._has(champ, self._peel_tags):
            reasons.append("增强后排保护")
        damage = (burst + dps) / 2
        if damage < 6 and self._has(champ, self._damage_tags):
            reasons.append("补充阵容输出")

        # Part D: Enemy comp
        enemy_tanks = self._count_enemy(enemy_picks, {"tank","frontline","bruiser"})
        enemy_dashers = self._count_enemy(enemy_picks, {"dash","assassin","dive","engage"})
        enemy_mages = self._count_enemy(enemy_picks, {"ap","mage"})
        enemy_squish = self._count_enemy(enemy_picks, {"marksman","assassin","mage"})

        if enemy_tanks >= 2 and self._has(champ, self._teamfight_tags):
            reasons.append("擅长对抗多前排阵容")
        if enemy_dashers >= 2 and self._has(champ, self._antidash_tags):
            reasons.append("克制高机动阵容")
        if enemy_mages >= 3 and self._has(champ, {"anti-ap","tank"}):
            reasons.append("对抗法系阵容效果优秀")
        if enemy_squish >= 3 and self._has(champ, self._assassin_tags):
            reasons.append("容易切入敌方后排")

        # Part E: Hero strengths
        if self._has(champ, {"frontline","tank"}):
            strengths.append("前排质量可靠")
        if self._has(champ, {"engage"}):
            strengths.append("开团能力优秀")
        if self._has(champ, {"peel","disengage","shield"}):
            strengths.append("保护能力出色")
        if self._has(champ, {"dps","sustained"}):
            strengths.append("持续输出能力强")
        if self._has(champ, {"burst","assassin"}):
            strengths.append("爆发伤害突出")
        if self._has(champ, {"poke"}):
            strengths.append("远程消耗能力优秀")
        if self._has(champ, {"splitpush","duelist"}):
            strengths.append("单带分推能力强")

        # Part F: Special mechanics
        from analysis.mechanic_analyzer import MechanicAnalyzer
        mb = MechanicAnalyzer.get_bonus(champ, enemy_picks)
        if mb >= 3:
            reasons.append("特殊机制适合当前阵容")

        return {
            "reasons": reasons[:4],
            "strengths": strengths[:3],
            "warnings": warnings[:2]
        }

