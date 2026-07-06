"""Lane Recommendation V2.1

Role Gate + improved scoring formula.
Filters out off-role champions using Riot match data.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from analysis.lolalytics_client import LolalyticsClient
from analysis.role_inference_engine import RoleInferenceEngine


class LaneRecommendation:
    """Lane pick recommendation powered by Lolalytics matchup data."""

    # (champion_data.json role, role_data.json key, lolalytics lane)
    ROLE_MAP = {
        "Top":     ("top",     "TOP",     "top"),
        "Jungle":  ("jungle",  "JUNGLE",  "jungle"),
        "Mid":     ("mid",     "MIDDLE",  "middle"),
        "ADC":     ("adc",     "BOTTOM",  "bottom"),
        "Support": ("support", "UTILITY", "support"),
        "TOP":     ("top",     "TOP",     "top"),
        "JUNGLE":  ("jungle",  "JUNGLE",  "jungle"),
        "MID":     ("mid",     "MIDDLE",  "middle"),
        "SUPPORT": ("support", "UTILITY", "support"),
    }

    ROLE_GATE_MIN = 70

    def __init__(self, client: Optional[LolalyticsClient] = None, max_workers: int = 8):
        self.client = client or LolalyticsClient()
        self.role_inference = RoleInferenceEngine()
        self.max_workers = max_workers
        base = Path(__file__).resolve().parent

        # champion -> roles mapping
        with open(base.parent / "champion_data.json", encoding="utf-8") as f:
            self._champion_data = json.load(f)

        # role_score: per-champion role distribution from Riot API
        with open(base.parent / "data" / "role_data.json", encoding="utf-8") as f:
            self._role_data = json.load(f)

        # viability_score: global champion viability
        with open(base.parent / "data" / "meta_data.json", encoding="utf-8") as f:
            self._meta_data = json.load(f)

    # ---- Score helpers ----

    @staticmethod
    def _matchup_score(delta: float) -> float:
        """Normalize delta to 0-100 scale."""
        return max(0.0, min(100.0, round(50.0 + delta * 5.0, 1)))

    @staticmethod
    def _sample_score(games: int) -> float:
        if games > 50000:
            return 100.0
        elif games > 20000:
            return 85.0
        elif games > 10000:
            return 70.0
        elif games > 5000:
            return 60.0
        else:
            return 50.0

    # ---- Data lookups ----

    def _get_role_score(self, champion: str, role_key: str) -> float:
        entry = self._role_data.get(champion, {})
        return float(entry.get(role_key, 0))

    def _get_viability_score(self, champion: str) -> float:
        entry = self._meta_data.get(champion, {})
        v = entry.get("viability")
        return float(v) if v is not None else 50.0

    def _get_candidates(self, role: str) -> List[str]:
        """Return sorted champions that can play the given role (per champion_data.json)."""
        entry = self.ROLE_MAP.get(role)
        if not entry:
            return []
        data_role, _, _ = entry
        result = []
        for champ, info in self._champion_data.items():
            roles = info.get("roles", [])
            if any(r.lower() == data_role for r in roles):
                result.append(champ)
        return sorted(result)

    # ---- Scoring ----

    def _v1_lane_score(self, delta: float, games: int) -> float:
        """Original V2 scoring (for comparison)."""
        return round(self._matchup_score(delta) * 0.8 + self._sample_score(games) * 0.2, 1)

    def _v21_lane_score(self, delta: float, role_score: float, viability_score: float) -> float:
        """V2.1 scoring with role + viability."""
        ms = self._matchup_score(delta)
        return round(ms * 0.6 + role_score * 0.2 + viability_score * 0.2, 1)

    # ---- Fetch one ----

    def _fetch_one(self, champ: str, enemy: str, lane: str,
                   role_key: str) -> Optional[dict]:
        try:
            matchup = self.client.get_matchup(champ, enemy, lane=lane)
            if matchup is None:
                return None
            delta = matchup.get("delta", 0.0)
            games = matchup.get("games", 0)
            role_score = self._get_role_score(champ, role_key)
            viability_score = self._get_viability_score(champ)

            return {
                "champion": champ,
                "delta": delta,
                "games": games,
                "role_score": role_score,
                "viability_score": viability_score,
                "v1_score": self._v1_lane_score(delta, games),
                "v21_score": self._v21_lane_score(delta, role_score, viability_score),
            }
        except Exception:
            return None

    # ---- Public API ----

    def get_recommendations(
        self,
        role: str,
        enemy_lane_champion: str,
        top_n: int = 5,
        use_role_gate: bool = True,
        use_v21: bool = True,
    ) -> List[dict]:
        """Get TopN lane picks against a specific enemy champion.

        Args:
            role: Target role (Top, Jungle, Mid, ADC, Support)
            enemy_lane_champion: Enemy champion name (English)
            top_n: Number of recommendations
            use_role_gate: Filter out champions with role_score < 70
            use_v21: Use V2.1 formula; otherwise use V2 formula

        Returns:
            List of {champion, lane_score, delta, games, role_score, viability_score}
        """
        entry = self.ROLE_MAP.get(role)
        if not entry:
            return []
        _, role_key, lane = entry

        candidates = self._get_candidates(role)
        scored = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for champ in candidates:
                if champ.lower() == enemy_lane_champion.lower():
                    continue
                future = pool.submit(self._fetch_one, champ, enemy_lane_champion,
                                     lane, role_key)
                futures[future] = champ

            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    continue

                # Role Gate
                if use_role_gate and result["role_score"] < self.ROLE_GATE_MIN:
                    continue

                score_field = "v21_score" if use_v21 else "v1_score"
                result["lane_score"] = result[score_field]
                scored.append(result)

        scored.sort(key=lambda x: (-x["lane_score"], -x["games"]))

        # Strip internal fields for public output
        out = []
        for r in scored[:top_n]:
            out.append({
                "champion": r["champion"],
                "lane_score": r["lane_score"],
                "delta": r["delta"],
                "games": r["games"],
                "role_score": r["role_score"],
                "viability_score": r["viability_score"],
            })
        return out

    def get_recommendations_for_draft(
        self,
        role: str,
        enemy_picks: list[str],
        top_n: int = 5,
    ) -> dict:
        """Infer enemy lane opponent, then return lane recommendations."""
        inferred = self.role_inference.infer_enemy_lane(enemy_picks, role)
        if not inferred:
            return {
                "opponent": "",
                "opponent_role": role,
                "opponent_probability": 0.0,
                "role_inference": self.role_inference.infer_roles(enemy_picks),
                "recommendations": [],
            }

        recommendations = self.get_recommendations(
            role=role,
            enemy_lane_champion=inferred["champion"],
            top_n=top_n,
        )
        for item in recommendations:
            item["opponent"] = inferred["champion"]
            item["opponent_role"] = inferred["role"]
            item["opponent_probability"] = inferred["probability"]

        return {
            "opponent": inferred["champion"],
            "opponent_role": inferred["role"],
            "opponent_probability": inferred["probability"],
            "role_inference": inferred["all"],
            "recommendations": recommendations,
        }

    def compare(
        self,
        role: str,
        enemy_lane_champion: str,
        top_n: int = 20,
    ) -> dict:
        """Return before/after results for comparison reporting."""
        before = self.get_recommendations(role, enemy_lane_champion,
                                          top_n=top_n, use_role_gate=False, use_v21=False)
        after = self.get_recommendations(role, enemy_lane_champion,
                                         top_n=top_n, use_role_gate=True, use_v21=True)
        return {"before": before, "after": after}

