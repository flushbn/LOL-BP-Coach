import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.recommendation_engine import TeamAnalyzer
from core.counter_analyzer import CounterAnalyzer
from core.meta_analyzer import MetaAnalyzer
from analysis.mechanic_analyzer import MechanicAnalyzer
from core.meta_filter import MetaFilter
from core.role_filter import RoleFilter
from analysis.lolalytics_client import LolalyticsClient
from analysis.lane_bonus import find_enemy_lane_champion, get_lane_bonus
from analysis.personalized_recommender import get_comfort_bonus
from analysis.data_trust_layer import get_composite_trust_weight, get_sources_confidence
from analysis.patch_notes_engine import PatchNotesEngine
from utils.champion_names import champion_display_name


class RecommendationEngine:
    """V2 engine with refined scoring: Counter*0.35 + Meta*0.35 + Role*0.20 + Synergy*0.10."""

    def __init__(self, viability_threshold: int = 50, use_counter_v2: bool = False, use_synergy_v2: bool = False):
        self.team = TeamAnalyzer()
        self.counter = CounterAnalyzer(use_v2=use_counter_v2)
        self.meta = MetaAnalyzer()
        self.meta_filter = MetaFilter(viability_threshold)
        self._use_synergy_v2 = use_synergy_v2
        self.role_filter = RoleFilter()

        # Load role_data.json for RoleScore
        self._role_data: Dict[str, Dict[str, int]] = {}
        # Synergy V2 data
        self._synergy_v2: Dict[str, Dict[str, float]] = {}
        self._synergy_v2_absolute = False
        self._synergy_path = self._resolve_synergy_path()
        if self._synergy_path.exists():
            with open(self._synergy_path, "r", encoding="utf-8") as _f:
                _raw_synergy = json.load(_f)
            self._synergy_v2 = self._normalize_synergy_schema(_raw_synergy)
            if "champions" in _raw_synergy:
                self._synergy_v2_absolute = True
                self._use_synergy_v2 = True
        role_path = PROJECT_ROOT / "data" / "role_data.json"
        if role_path.exists():
            with open(role_path, "r", encoding="utf-8") as f:
                self._role_data = json.load(f)
        # V6: Bot Lane Pair Data
        self._botlane_pairs = {}
        blp_path = PROJECT_ROOT / "data" / "botlane_pair_data.json"
        if blp_path.exists():
            with open(blp_path, "r", encoding="utf-8") as _f:
                self._botlane_pairs = json.load(_f)

        # V6: Jungle-Support archetype data
        self._jg_sup_data = {}
        jsd_path = PROJECT_ROOT / "data" / "jungle_support_data.json"
        if jsd_path.exists():
            with open(jsd_path, "r", encoding="utf-8") as _f:
                self._jg_sup_data = json.load(_f)
        self._carry_jg = {"Kindred","Graves","Nidalee","Karthus","MasterYi","BelVeth","Lillia","Evelynn","KhaZix","Rengar","Shaco","Talon","Ekko","Diana"}
        self._frontline_jg = {"Sejuani","Maokai","Zac","Amumu","Rammus","Sion","Nunu","Poppy","Vi","JarvanIV","XinZhao","Volibear","Udyr"}
        self._engage_sup = {"Leona","Nautilus","Rell","Alistar","Blitzcrank","Thresh","Pyke","Rakan","Galio"}
        self._lolalytics_client = LolalyticsClient()
        self._patch_notes = PatchNotesEngine()


        # Display-only Chinese names. Internal champion keys remain English.

    def _resolve_synergy_path(self) -> Path:
        data_dir = PROJECT_ROOT / "data"
        patch_file = data_dir / "patch_version.json"
        try:
            if patch_file.exists():
                patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
                if patch:
                    patch_path = data_dir / str(patch) / "synergy_data.json"
                    if patch_path.exists():
                        return patch_path
        except Exception:
            pass
        return data_dir / "synergy_data_v2.json"

    def _normalize_synergy_schema(self, data: Dict) -> Dict[str, Dict[str, float]]:
        if "champions" not in data:
            return data
        converted: Dict[str, Dict[str, float]] = {}
        for champion, partners in data.get("champions", {}).items():
            for partner, payload in partners.items():
                converted.setdefault(champion, {})[partner] = float(payload.get("synergy_score", 50) or 50)
        return converted

    # --- Normalization ---
    def _norm(self, score: int, max_possible: int) -> int:
        if max_possible <= 0:
            return 50
        return min(100, max(0, round(score / max_possible * 100)))

    # --- TeamCompScore ---
    def _teamcomp_score(self, ally_scores: Dict[str, int]) -> int:
        dims_w = {"frontline": 2, "engage": 2, "peel": 2, "poke": 1, "burst": 1, "dps": 1, "teamfight": 2}
        raw = sum(ally_scores.get(d, 0) * w for d, w in dims_w.items())
        return self._norm(raw, sum(10 * w for w in dims_w.values()))

    # --- RoleScore (NEW) ---
    def _role_score(self, champion: str, target_role: str) -> int:
        if not target_role:
            return 100
        pos_map = {"Top": "TOP", "Jungle": "JUNGLE", "Mid": "MIDDLE",
                   "ADC": "BOTTOM", "Support": "UTILITY"}
        riot_pos = pos_map.get(target_role, "")
        if not riot_pos:
            return 50
        roles = self._role_data.get(champion, {})
        pct = roles.get(riot_pos, 0)
        if pct >= 70:
            return 100
        if pct >= 50:
            return 85
        if pct >= 30:
            return 70
        if pct >= 10:
            return 50
        return 0

    # --- MetaScore (refined) ---
    def _meta_score(self, champion: str) -> int:
        details = self.meta.get_details(champion)
        if not details:
            return 50
        wr = details.get("win_rate", 0)
        pr = details.get("pick_rate", 0)
        picks = details.get("picks", 0)
        # Penalize low-sample champs (fewer than 50 picks = less reliable)
        sample_penalty = 0
        # Normalize: wr ~45-60%, pr ~1-20%
        wr_score = self._norm(round(wr * 2), 120)  # wr*2, cap at 60% = 100
        pr_score = self._norm(round(pr * 5), 100)  # pr*5, cap at 20% = 100
        meta = round(wr_score * 0.5 + pr_score * 0.3 + self.meta.get_viability(champion) * 0.2)
        return min(100, max(0, meta))

    # --- Main ranking ---
    def rank(
        self,
        ally_picks: List[str],
        enemy_picks: List[str],
        target_role: Optional[str] = None,
        bans: Optional[List[str]] = None,
        top_n: int = 10,
        pick_slot: int = 0,
    ) -> List[Tuple[str, int, Dict[str, float]]]:
        all_counter = self.counter.analyze(enemy_picks)
        max_ctr = max(all_counter.values()) if all_counter else 1

        excluded = set(ally_picks)
        if bans:
            excluded.update(bans)

        # Role filtering
        if target_role:
            candidates = set(self.role_filter.get_candidates(target_role))
        else:
            candidates = set(all_counter.keys())

        _lane_enemy = find_enemy_lane_champion(enemy_picks, target_role or "", self._role_data) if target_role else None
        _ROLE_TO_BONUS = {"TOP":"TOP","JUNGLE":"JUNGLE","MID":"MID","BOTTOM":"BOTTOM","UTILITY":"UTILITY"}
        results = []
        for champ in list(candidates):
            if champ in excluded:
                continue
            if not self.meta_filter.is_viable(champ):
                continue

            ctr_raw = all_counter.get(champ, 0)
            ctr_score = self._norm(ctr_raw, max_ctr)

            # V3.5: Counter Compression (reduce counter domination)
            ctr_score = 50 + round(ctr_score * 0.5)

            # V2: refined MetaScore
            meta_score = self._meta_score(champ)

            # V2: RoleScore
            role_score = self._role_score(champ, target_role) if target_role else 100

            # TeamCompScore
            simulated = ally_picks + [champ]
            analysis = self.team.analyze(ally_picks=simulated, enemy_picks=enemy_picks)
            tc_score = self._teamcomp_score(analysis["ally"])

            # V6: Comp fit bonus - boost champs that fix team deficits
            ally_missing_orig = self.team._detect_missing(ally_picks)
            champ_tags = self.team._get_champion(champ).get("tags", [])
            comp_fit_bonus = 0
            dim_map = {"frontline": ["tank","frontline","bruiser"], "engage": ["engage"], "cc": ["cc","control"], "ap": ["ap","mage"], "peel": ["peel","support"]}
            for deficit in ally_missing_orig:
                needed_tags = dim_map.get(deficit, [])
                for tag in needed_tags:
                    if tag in champ_tags:
                        comp_fit_bonus += 5
                        break
            comp_fit_bonus = min(comp_fit_bonus, 10)

            # V5: Synergy V2
            if self._use_synergy_v2 and self._synergy_v2:
                ally_syn_scores = []
                for ally_champ in ally_picks:
                    pair_scores = self._synergy_v2.get(champ, {})
                    score = pair_scores.get(ally_champ, 0)
                    if score:
                        ally_syn_scores.append(score)
                if self._synergy_v2_absolute:
                    syn_score = round(sum(ally_syn_scores) / max(len(ally_syn_scores), 1)) if ally_syn_scores else 50
                else:
                    syn_score = 50 + round(sum(ally_syn_scores) / max(len(ally_syn_scores), 1))
                syn_score = max(0, min(100, syn_score))
            else:
                syn_score = 50  # Future SynergyAnalyzer

            # V3.5: Viability Penalty
            details = self.meta.get_details(champ)
            viability = details.get("viability", 50) if details else 50
            if viability < 40:
                viability_penalty = 20
            elif viability < 50:
                viability_penalty = 10
            else:
                viability_penalty = 0

            # V5.5: Mechanic Layer

            mechanic_bonus = MechanicAnalyzer.get_bonus(champ, enemy_picks)

            # V6: Bot Lane Pair Bonus
            botlane_bonus = 0
            if target_role in ("ADC", "Support") and self._botlane_pairs:
                ally_bot = None
                ally_sup = None
                for a in ally_picks:
                    rd = self._role_data.get(a, {})
                    if rd.get("BOTTOM", 0) > rd.get("UTILITY", 0):
                        ally_bot = a
                    elif rd.get("UTILITY", 0) > rd.get("BOTTOM", 0):
                        ally_sup = a
                if target_role == "ADC" and ally_sup:
                    pair = self._botlane_pairs.get(champ, {}).get(ally_sup, None)
                    if pair and pair["win_rate"] >= 50:
                        botlane_bonus = min(5, int(pair["win_rate"] - 48))
                elif target_role == "Support" and ally_bot:
                    pair = self._botlane_pairs.get(ally_bot, {}).get(champ, None)
                    if pair and pair["win_rate"] >= 50:
                        botlane_bonus = min(5, int(pair["win_rate"] - 48))

            # V6: Jungle-Support synergy bonus
            jg_sup_bonus = 0
            if target_role == "Support":
                ally_jg = None
                for a in ally_picks:
                    rd = self._role_data.get(a, {})
                    jg_pct = rd.get("JUNGLE", 0)
                    top_pct = rd.get("TOP", 0)
                    mid_pct = rd.get("MIDDLE", 0)
                    if jg_pct > top_pct and jg_pct > mid_pct:
                        ally_jg = a
                        break
                if ally_jg:
                    if ally_jg in self._carry_jg and champ in self._engage_sup:
                        jg_sup_bonus = 3
                    elif ally_jg in self._frontline_jg:
                        if champ in {"Lulu","Janna","Nami","Soraka","Milio","Sona","Yuumi","Karma","Seraphine"}:
                            jg_sup_bonus = 2

                        # V8: Draft Order Bonus
            draft_bonus = 0
            draft_reason = ""
            if pick_slot is not None and pick_slot > 0:
                from analysis.draft_state_analyzer import DraftStateAnalyzer
                dsa = DraftStateAnalyzer()
                ds = dsa.analyze(len(ally_picks), len(enemy_picks))
                draft_bonus = dsa.get_draft_score(champ, ds)
                if draft_bonus != 0:
                    from core.recommendation_engine import TeamAnalyzer
                    draft_reason = dsa.get_draft_reason(champ, ds)

            # V6: Total bonus cap
            v6_bonus = min(botlane_bonus + jg_sup_bonus, 8)

            # V2 formula + V3.5 adjustments + V5.5 mechanic
            _lane_info = get_lane_bonus(champ, _ROLE_TO_BONUS.get(target_role,""), _lane_enemy, self._lolalytics_client) if _lane_enemy else {"lane_bonus":0,"lane_reason":""}
            _comfort_info = get_comfort_bonus(champ)
            _patch_reason = self._patch_notes.get_champion_patch_reason(champ)
            data_trust_weight = get_composite_trust_weight()
            raw_final = round(ctr_score * 0.35 + meta_score * 0.35 + role_score * 0.20 + syn_score * 0.10 - viability_penalty + mechanic_bonus + comp_fit_bonus + v6_bonus + draft_bonus + _lane_info["lane_bonus"] + _comfort_info["comfort_bonus"])
            final = round(raw_final * data_trust_weight)

            results.append((champ, final, {
                "raw_final_score": raw_final,
                "data_trust_weight": data_trust_weight,
                "data_sources_confidence": get_sources_confidence(),
                "draft_reason": draft_reason,
                "lane_bonus": _lane_info.get("lane_bonus", 0),
                "lane_reason": _lane_info.get("lane_reason", ""),
                "comfort_bonus": _comfort_info.get("comfort_bonus", 0),
                "comfort_reason": _comfort_info.get("comfort_reason", ""),
                "patch_reason": _patch_reason,
                "counter": ctr_score,
                "meta": meta_score,
                "role": role_score,
                "synergy": syn_score,
                "team_comp": tc_score,
                "mechanic_bonus": mechanic_bonus,
                "comp_fit": comp_fit_bonus,
                "v6_bonus": v6_bonus,
                "draft_bonus": draft_bonus,
            }))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]

    # --- Recommend ---
    def recommend(
        self,
        ally_picks: List[str],
        enemy_picks: List[str],
        target_role: Optional[str] = None,
        bans: Optional[List[str]] = None,
        top_n: int = 5,
        pick_slot: int = 0,
    ) -> List[Dict]:
        ranked = self.rank(ally_picks, enemy_picks, target_role, bans, top_n * 3, pick_slot)
        try:
            from analysis.tactical_analyzer import TacticalAnalyzer
            _get_tactical = lambda: TacticalAnalyzer()
        except:
            _get_tactical = lambda: None
        seen = set()
        picks = []

        for champ, score, bd in ranked:
            if champ in seen or champ in ally_picks:
                continue
            seen.add(champ)

            champ_roles = self.role_filter.get_roles(champ)
            reasons = []
            if bd.get("counter", 0) >= 80:
                reasons.append("强力克制敌方阵容")
            if bd.get("meta", 0) >= 80:
                reasons.append("当前版本热门英雄")
            if bd.get("role", 0) >= 90:
                reasons.append("主流位置英雄")
            if bd.get("synergy", 0) >= 70:
                reasons.append("与己方阵容配合优秀")
            details = self.meta.get_details(champ)
            if details and details.get("viability", 0) >= 60:
                reasons.append("高强度稳定选择")
            mechanic_bonus = bd.get("mechanic_bonus", 0)
            if mechanic_bonus >= 3:
                reasons.append("特殊机制适合当前阵容")
            comp_fit = bd.get("comp_fit", 0)
            if comp_fit >= 5:
                reasons.append("补足阵容缺陷")
                reasons.append("综合推荐")
                comfort_txt = bd.get("comfort_reason", "")
                if comfort_txt:
                    reasons.append(comfort_txt)

            patch_reason = bd.get("patch_reason", "")
            if patch_reason:
                reasons.append(patch_reason)

            cn_name = champion_display_name(champ)
            ta = _get_tactical(); tac = ta.analyze(ally_picks, enemy_picks, champ) if ta else {"reasons":[],"strengths":[],"warnings":[]}
            picks.append({
                "champion": champ,
                "champion_cn": cn_name,
                "role": champ_roles,
                "final_score": score,
                "raw_final_score": bd.get("raw_final_score", score),
                "data_trust_weight": bd.get("data_trust_weight", 1.0),
                "data_sources_confidence": bd.get("data_sources_confidence", {}),
                "counter_score": bd.get("counter", 0),
                "meta_score": bd.get("meta", 0),
                "role_score": bd.get("role", 0),
                "synergy_score": bd.get("synergy", 0),
                "teamcomp_score": bd.get("team_comp", 0),
                "mechanic_bonus": bd.get("mechanic_bonus", 0),
                "comp_fit_bonus": bd.get("comp_fit", 0),
                "v6_bonus": bd.get("v6_bonus", 0),
                "draft_bonus": bd.get("draft_bonus", 0),
                "draft_reason": bd.get("draft_reason", ""),
                "lane_bonus": bd.get("lane_bonus", 0),
                "lane_reason": bd.get("lane_reason", ""),
                "comfort_bonus": bd.get("comfort_bonus", 0),
                "comfort_reason": bd.get("comfort_reason", ""),
                "patch_reason": bd.get("patch_reason", ""),
                "breakdown": bd,
                "reasons": reasons,
                "tactical": tac,
            })
            if len(picks) >= top_n:
                break
        return picks

